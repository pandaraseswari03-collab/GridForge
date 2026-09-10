"""
GridForge - Contingency Analysis
================================

File:
    core/analysis/contingency.py

Purpose:
    Public analysis-level facade for contingency studies.

Scope:
    - N-1 contingency analysis
    - N-k contingency architecture
    - Non-destructive outage simulation
    - Power-flow based post-contingency assessment
    - Voltage and thermal violation detection
    - Study-level result aggregation

Architecture
------------

    Authoritative Network
            |
            v
    ContingencyAnalysis
            |
            +---- isolated case Network
            |          |
            |          v
            |    PowerFlowStudyConfiguration
            |          |
            |          v
            |    PowerFlowPreparation
            |          |
            |          v
            |    PowerFlowAnalysis
            |          |
            |          v
            |    core/solver/power_flow/
            |
            v
    ContingencyResult

IMPORTANT STATE-ISOLATION CONTRACT
----------------------------------

The Network supplied to ContingencyAnalysis is authoritative.

A contingency study MUST NOT modify it.

Every contingency case therefore operates on a completely
isolated deep copy of the authoritative Network.

Outage status is applied only to the copied case Network.

PowerFlowPreparation and PowerFlowAnalysis operate only on the
isolated case Network and its prepared numerical contracts.

The authoritative Network is never passed to:

    - set_element_status()
    - PowerFlowAnalysis
    - contingency-case numerical execution

Numerical mathematics remains outside this module.

Copyright © 2026 Subhendu Mishra
All Rights Reserved.
Proprietary and confidential.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import isfinite
from typing import Any, Iterable, List, Optional, Sequence, Tuple
import copy

from core.analysis.power_flow import PowerFlowAnalysis
from core.network.endpoint import resolve_terminal_bus
from core.solver.power_flow.preparation import PowerFlowPreparation
from core.solver.power_flow.study_configuration import PowerFlowStudyConfiguration


@dataclass
class ContingencyViolation:
    """Single post-contingency engineering violation."""

    category: str
    element_id: Any
    value: Optional[float] = None
    limit: Optional[float] = None
    severity: Optional[float] = None


@dataclass
class ContingencyCaseResult:
    """Result for one contingency case."""

    case_id: str
    outages: Tuple[Any, ...]
    success: bool = False
    converged: bool = False
    power_flow_result: Any = None
    violations: List[ContingencyViolation] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ContingencyResult:
    """Complete contingency-study result."""

    cases: List[ContingencyCaseResult] = field(default_factory=list)
    success: bool = False
    converged: bool = False
    critical_cases: List[str] = field(default_factory=list)
    critical_violations: List[ContingencyViolation] = field(default_factory=list)

    @property
    def failed_cases(self) -> List[ContingencyCaseResult]:
        return [case for case in self.cases if not case.success]

    @property
    def violated_cases(self) -> List[ContingencyCaseResult]:
        return [case for case in self.cases if case.success and case.violations]


class ContingencyAnalysis:
    """Public facade for N-1 / N-k contingency studies."""

    def __init__(
        self,
        network: Any,
        power_flow_configuration: Optional[PowerFlowStudyConfiguration] = None,
    ) -> None:
        self.network = network
        self.power_flow_configuration = power_flow_configuration
        self._validate_network()
        if power_flow_configuration is not None and not isinstance(power_flow_configuration, PowerFlowStudyConfiguration):
            raise TypeError("power_flow_configuration must be PowerFlowStudyConfiguration.")
        self._prepared_cases: List[Tuple[Any, ...]] = []
        self._result: Optional[ContingencyResult] = None

    def run(
        self,
        elements: Optional[Sequence[Any]] = None,
        *,
        contingency_type: str = "N-1",
        element_types: Optional[Sequence[str]] = None,
        power_flow_options: Optional[Any] = None,
        voltage_min: float = 0.95,
        voltage_max: float = 1.05,
        thermal_limit: float = 100.0,
    ) -> ContingencyResult:
        self._validate_limits(voltage_min=voltage_min, voltage_max=voltage_max, thermal_limit=thermal_limit)
        if self.power_flow_configuration is None:
            raise ValueError("ContingencyAnalysis requires a PowerFlowStudyConfiguration to execute power-flow based contingency cases.")
        cases = self.prepare(elements=elements, contingency_type=contingency_type, element_types=element_types)
        case_results = [
            self._run_case(
                outages=outages,
                power_flow_options=power_flow_options,
                voltage_min=voltage_min,
                voltage_max=voltage_max,
                thermal_limit=thermal_limit,
            )
            for outages in cases
        ]
        result = self.post_process(case_results)
        self._result = result
        return result

    def prepare(
        self,
        *,
        elements: Optional[Sequence[Any]] = None,
        contingency_type: str = "N-1",
        element_types: Optional[Sequence[str]] = None,
    ) -> List[Tuple[Any, ...]]:
        k = self._parse_contingency_order(contingency_type)
        candidates = self._get_candidates(elements=elements, element_types=element_types)
        if len(candidates) < k:
            raise ValueError(f"N-{k} contingency analysis requires at least {k} candidate elements; only {len(candidates)} are available.")
        cases = list(combinations(candidates, k))
        self._prepared_cases = cases
        return cases

    def _run_case(
        self,
        *,
        outages: Tuple[Any, ...],
        power_flow_options: Optional[Any],
        voltage_min: float,
        voltage_max: float,
        thermal_limit: float,
    ) -> ContingencyCaseResult:
        case_result = ContingencyCaseResult(case_id=self._make_case_id(outages), outages=outages)
        try:
            case_network = self._create_outage_case(outages)
            prepared = PowerFlowPreparation(case_network, self.power_flow_configuration).prepare()
            power_flow = PowerFlowAnalysis(
                prepared.input,
                prepared.ybus,
                options=power_flow_options,
                prepared=prepared,
            )
            power_flow_result = power_flow.solve()
            case_result.power_flow_result = power_flow_result
            case_result.converged = self._result_converged(power_flow_result)
            case_result.success = True
            case_result.violations = self._detect_violations(
                case_network,
                power_flow_result,
                voltage_min=voltage_min,
                voltage_max=voltage_max,
                thermal_limit=thermal_limit,
            )
        except Exception as exc:
            case_result.success = False
            case_result.converged = False
            case_result.error = f"{type(exc).__name__}: {exc}"
        return case_result

    def _create_outage_case(self, outages: Tuple[Any, ...]) -> Any:
        case_network = copy.deepcopy(self.network)
        for element_id in outages:
            element = self._find_element(case_network, element_id)
            if element is None:
                raise KeyError(f"Contingency element {element_id!r} was not found in the isolated case Network.")
            if self._is_bus(element):
                element.in_service = False
                self._disable_connected_equipment(case_network, element)
            else:
                self._set_in_service(element, False)
        return case_network

    @staticmethod
    def _is_bus(element: Any) -> bool:
        return type(element).__name__.lower() == "bus"

    @staticmethod
    def _set_in_service(element: Any, in_service: bool) -> None:
        if not hasattr(element, "in_service"):
            raise TypeError(f"Contingency element {element!r} has no in_service state.")
        element.in_service = bool(in_service)

    @classmethod
    def _disable_connected_equipment(cls, network: Any, bus: Any) -> None:
        for collection in (network.lines, network.transformers, network.generators, network.loads, network.shunts):
            for element in collection:
                if cls._element_connected_to_bus(element, bus):
                    cls._set_in_service(element, False)

    @staticmethod
    def _element_connected_to_bus(element: Any, bus: Any) -> bool:
        terminals = getattr(element, "terminals", None)
        if terminals is None:
            terminal = getattr(element, "terminal", None)
            terminals = (terminal,) if terminal is not None else ()
        for terminal in terminals:
            if terminal is None:
                continue
            try:
                resolved_bus = resolve_terminal_bus(terminal)
            except (TypeError, ValueError):
                continue
            if resolved_bus is bus:
                return True
            resolved_bus_id = getattr(resolved_bus, "id", None)
            bus_id = getattr(bus, "id", None)
            if resolved_bus_id is not None and resolved_bus_id == bus_id:
                return True
        return False

    def _get_candidates(
        self,
        *,
        elements: Optional[Sequence[Any]],
        element_types: Optional[Sequence[str]],
    ) -> List[Any]:
        normalized_types = self._normalize_element_types(element_types)
        available: List[Any] = []
        collections = (
            ("bus", self.network.buses),
            ("line", self.network.lines),
            ("transformer", self.network.transformers),
            ("generator", self.network.generators),
            ("load", self.network.loads),
            ("shunt", self.network.shunts),
        )
        for element_type, collection in collections:
            if normalized_types is not None and element_type not in normalized_types:
                continue
            for element in collection:
                if getattr(element, "in_service", True):
                    available.append(element.id)
        if elements is None:
            return available
        requested = list(elements)
        try:
            unique_requested = set(requested)
        except TypeError as exc:
            raise ValueError("Contingency element IDs must be hashable.") from exc
        if len(requested) != len(unique_requested):
            raise ValueError("Duplicate contingency element IDs are not permitted.")
        missing = [element_id for element_id in requested if element_id not in available]
        if missing:
            raise KeyError(f"Unknown or out-of-service contingency element(s): {missing}")
        return requested

    @staticmethod
    def _normalize_element_types(element_types: Optional[Sequence[str]]) -> Optional[set[str]]:
        if element_types is None:
            return None
        normalized = {str(item).strip().lower() for item in element_types}
        valid_types = {"bus", "line", "transformer", "generator", "load", "shunt"}
        invalid = normalized - valid_types
        if invalid:
            raise ValueError(f"Unsupported contingency element type(s): {sorted(invalid)}")
        if not normalized:
            raise ValueError("element_types cannot be empty.")
        return normalized

    @staticmethod
    def _parse_contingency_order(contingency_type: str) -> int:
        normalized = str(contingency_type).strip().upper().replace(" ", "")
        if not normalized.startswith("N-"):
            raise ValueError("Unsupported contingency type. Use 'N-1' or 'N-k', for example 'N-2'.")
        try:
            k = int(normalized[2:])
        except ValueError as exc:
            raise ValueError(f"Invalid contingency type: {contingency_type!r}.") from exc
        if k < 1:
            raise ValueError("Contingency order must be at least 1.")
        return k

    @staticmethod
    def _find_element(network: Any, element_id: Any) -> Optional[Any]:
        for collection in (network.buses, network.lines, network.transformers, network.generators, network.loads, network.shunts):
            for element in collection:
                if element.id == element_id:
                    return element
        return None

    def post_process(self, cases: Iterable[ContingencyCaseResult]) -> ContingencyResult:
        result = ContingencyResult(cases=list(cases))
        if not result.cases:
            return result
        result.success = all(case.success for case in result.cases)
        result.converged = all(case.success and case.converged for case in result.cases)
        for case in result.cases:
            if case.violations:
                result.critical_cases.append(case.case_id)
                result.critical_violations.extend(case.violations)
        return result

    def _detect_violations(
        self,
        network: Any,
        power_flow_result: Any,
        *,
        voltage_min: float,
        voltage_max: float,
        thermal_limit: float,
    ) -> List[ContingencyViolation]:
        violations: List[ContingencyViolation] = []
        voltage = self._extract_result_value(power_flow_result, "voltage_magnitudes")
        bus_results = self._extract_result_value(power_flow_result, "bus_results")
        if bus_results:
            for bus_id, record in bus_results.items():
                value = record.get("voltage_magnitude")
                if value is None:
                    value = record.get("voltage_pu")
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue
                if not isfinite(numeric_value):
                    continue
                if numeric_value < voltage_min:
                    violations.append(ContingencyViolation("voltage_low", bus_id, numeric_value, voltage_min, voltage_min - numeric_value))
                elif numeric_value > voltage_max:
                    violations.append(ContingencyViolation("voltage_high", bus_id, numeric_value, voltage_max, numeric_value - voltage_max))
        elif voltage is not None:
            buses = {str(bus.id): bus for bus in network.buses}
            ids = tuple(str(bus.id) for bus in network.buses)
            for index, value in enumerate(voltage):
                if index >= len(ids):
                    break
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue
                if not isfinite(numeric_value):
                    continue
                bus_id = ids[index]
                if numeric_value < voltage_min:
                    violations.append(ContingencyViolation("voltage_low", buses.get(bus_id, bus_id).id if bus_id in buses else bus_id, numeric_value, voltage_min, voltage_min - numeric_value))
                elif numeric_value > voltage_max:
                    violations.append(ContingencyViolation("voltage_high", buses.get(bus_id, bus_id).id if bus_id in buses else bus_id, numeric_value, voltage_max, numeric_value - voltage_max))

        branch_results = self._extract_result_value(power_flow_result, "branch_results")
        if branch_results is not None:
            violations.extend(self._detect_engineering_loading_violations(branch_results, "thermal", thermal_limit))

        transformer_results = self._extract_result_value(power_flow_result, "transformer_results")
        if transformer_results is not None:
            violations.extend(self._detect_engineering_loading_violations(transformer_results, "transformer_thermal", thermal_limit))
        return violations

    @staticmethod
    def _detect_engineering_loading_violations(results: Any, category: str, default_limit: float) -> List[ContingencyViolation]:
        violations: List[ContingencyViolation] = []
        for element_id, record in results.items():
            loading = record.get("loading_percent")
            if loading is None:
                continue
            try:
                value = float(loading)
            except (TypeError, ValueError):
                continue
            if not isfinite(value):
                continue
            limit_percent = 100.0 if record.get("limit_mva") is not None else float(default_limit)
            within_limit = record.get("within_limit")
            violated = within_limit is False or (within_limit is None and value > limit_percent)
            if violated:
                violations.append(
                    ContingencyViolation(
                        category=category,
                        element_id=element_id,
                        value=value,
                        limit=limit_percent,
                        severity=value - limit_percent,
                    )
                )
        return violations

    @staticmethod
    def _extract_result_value(result: Any, name: str) -> Any:
        if result is None:
            return None
        if isinstance(result, dict):
            return result.get(name)
        return getattr(result, name, None)

    @classmethod
    def _result_converged(cls, result: Any) -> bool:
        value = cls._extract_result_value(result, "converged")
        if value is None:
            value = cls._extract_result_value(result, "success")
        return bool(value)

    @staticmethod
    def _make_case_id(outages: Tuple[Any, ...]) -> str:
        return "N-{}:{}".format(len(outages), "+".join(str(item) for item in outages))

    @staticmethod
    def _validate_limits(*, voltage_min: float, voltage_max: float, thermal_limit: float) -> None:
        try:
            v_min = float(voltage_min)
            v_max = float(voltage_max)
            thermal = float(thermal_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("Voltage and thermal limits must be numeric.") from exc
        if not (isfinite(v_min) and isfinite(v_max) and isfinite(thermal)):
            raise ValueError("Voltage and thermal limits must be finite.")
        if v_min < 0.0:
            raise ValueError("voltage_min cannot be negative.")
        if v_max <= v_min:
            raise ValueError("voltage_max must be greater than voltage_min.")
        if thermal < 0.0:
            raise ValueError("thermal_limit cannot be negative.")

    def _validate_network(self) -> None:
        if self.network is None:
            raise ValueError("Contingency Analysis requires a valid Network.")
        required = ("buses", "lines", "transformers", "generators", "loads", "shunts")
        for attribute in required:
            if not hasattr(self.network, attribute):
                raise ValueError(f"Network is missing required attribute or method '{attribute}'.")
        if len(self.network.buses) == 0:
            raise ValueError("Contingency Analysis requires at least one bus.")

    @property
    def result(self) -> Optional[ContingencyResult]:
        return self._result


__all__ = ["ContingencyAnalysis", "ContingencyResult", "ContingencyCaseResult", "ContingencyViolation"]
