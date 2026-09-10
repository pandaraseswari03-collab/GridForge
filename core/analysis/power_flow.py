"""Analysis-level orchestration for prepared numerical Power Flow studies."""

from __future__ import annotations

from typing import Any, Iterable, Optional
from dataclasses import replace

from core.analysis.power_flow_configuration import PowerFlowStudyConfiguration
from core.analysis.power_flow_preparation import PreparedPowerFlow, PowerFlowPreparation
from core.solver.power_flow.input import PowerFlowInput
from core.solver.power_flow.nr_solver import NewtonRaphsonSolver
from core.solver.power_flow.result import PowerFlowResult
from core.analysis.power_flow_result_conversion import EngineeringPowerFlowResult, PowerFlowResultConverter


class PowerFlowAnalysis:
    """Coordinate preparation, numerical Power Flow execution, and engineering evaluation."""

    def __init__(self, input_data: PowerFlowInput, ybus, options: Optional[object] = None, *, prepared: PreparedPowerFlow | None = None) -> None:
        if not isinstance(input_data, PowerFlowInput):
            raise TypeError("input_data must be PowerFlowInput.")
        if ybus is None:
            raise ValueError("Power Flow requires a prepared YBus.")
        if getattr(ybus, "shape", None) != (input_data.bus_count, input_data.bus_count):
            raise ValueError("Prepared YBus dimension does not match PowerFlowInput.")
        if not hasattr(ybus, "bus_ids") or tuple(ybus.bus_ids) != input_data.bus_ids:
            raise ValueError("Prepared YBus ordering does not match PowerFlowInput.")
        if prepared is not None:
            if not isinstance(prepared, PreparedPowerFlow):
                raise TypeError("prepared must be a PreparedPowerFlow instance.")
            if prepared.input is not input_data or prepared.ybus is not ybus:
                raise ValueError("Prepared Power Flow must own the supplied input and YBus.")
        if options is None:
            from core.solver.power_flow.solver_options import SolverOptions
            options = SolverOptions()
        self.input = input_data
        self.Ybus = ybus
        self.prepared = prepared
        self.options = options
        self.solver = NewtonRaphsonSolver(input_data, ybus, options)
        self._result: PowerFlowResult | None = None

    @classmethod
    def from_prepared(cls, prepared: PreparedPowerFlow, options: Optional[object] = None) -> "PowerFlowAnalysis":
        if not isinstance(prepared, PreparedPowerFlow):
            raise TypeError("prepared must be a PreparedPowerFlow instance.")
        return cls(prepared.input, prepared.ybus, options, prepared=prepared)

    @classmethod
    def from_network(cls, network: Any, power_flow_configuration: PowerFlowStudyConfiguration, options: Optional[object] = None) -> "PowerFlowAnalysis":
        prepared = PowerFlowPreparation.prepare(network, power_flow_configuration)
        return cls.from_prepared(prepared, options)

    def solve(self) -> PowerFlowResult:
        """Solve numerically, then enrich the same immutable result contract when prepared data is available."""
        numerical = self.solver.solve()
        if self.prepared is not None and numerical.success:
            engineering = PowerFlowResultConverter.to_engineering(numerical, prepared=self.prepared)
            self._result = engineering.numerical_result
        else:
            self._result = numerical
        return self._result

    def to_engineering_result(self, buses: Iterable[Any] | None = None) -> EngineeringPowerFlowResult:
        if self._result is None:
            raise RuntimeError("Power Flow must be solved before converting its result.")
        if self.prepared is None:
            raise RuntimeError("Power Flow engineering conversion requires the prepared snapshot.")
        return PowerFlowResultConverter.to_engineering(self._result, buses, prepared=self.prepared)

    @property
    def result(self) -> PowerFlowResult | None:
        return self._result


__all__ = ["PowerFlowAnalysis", "EngineeringPowerFlowResult", "PowerFlowResultConverter"]
