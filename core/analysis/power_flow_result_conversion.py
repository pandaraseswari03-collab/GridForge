"""Convert solved PU Power Flow state into immutable engineering results."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from core.base.per_unit import PerUnitSystem
from core.solver.power_flow.result import PowerFlowResult
from core.analysis.line_flow import LineFlowCalculator
from core.analysis.transformer_flow import TransformerFlowCalculator


@dataclass(frozen=True, slots=True)
class EngineeringPowerFlowBusResult:
    bus_id: str
    voltage_pu: float
    voltage_kv: float
    angle_rad: float
    angle_deg: float


@dataclass(frozen=True, slots=True)
class EngineeringElementResult:
    element_id: str
    from_bus_id: str
    to_bus_id: str
    current_from_a: float
    current_to_a: float
    p_from_mw: float
    q_from_mvar: float
    mva_from: float
    p_to_mw: float
    q_to_mvar: float
    mva_to: float
    loss_p_mw: float
    loss_q_mvar: float
    limit_mva: float | None
    loading_percent: float | None
    within_limit: bool | None


@dataclass(frozen=True, slots=True)
class EngineeringPowerFlowResult:
    """Immutable engineering view retained for compatibility and reporting."""

    numerical_result: PowerFlowResult
    buses: tuple[EngineeringPowerFlowBusResult, ...]
    branch_results: Mapping[str, EngineeringElementResult]
    transformer_results: Mapping[str, EngineeringElementResult]


class PowerFlowResultConverter:
    """Build the one authoritative PowerFlowResult engineering payload."""

    @staticmethod
    def to_engineering(
        result: PowerFlowResult,
        buses: Iterable[Any] | None = None,
        *,
        prepared: Any | None = None,
    ) -> EngineeringPowerFlowResult:
        if not isinstance(result, PowerFlowResult):
            raise TypeError("result must be a PowerFlowResult instance.")
        if prepared is None:
            raise ValueError("prepared Power Flow snapshot is required for engineering result evaluation.")

        bus_sequence = tuple(buses) if buses is not None else ()
        bus_results = PowerFlowResultConverter._bus_results(result, prepared, bus_sequence)
        Vm = result.voltage_magnitudes
        Va = result.voltage_angles
        per_unit = PerUnitSystem(prepared.base_mva)

        line_flows = LineFlowCalculator.from_prepared(prepared).calculate_all(
            _complex_voltage(Vm, Va)
        )
        transformer_flows = TransformerFlowCalculator.from_prepared(prepared).calculate(Vm, Va)

        branch_results = {
            branch_id: PowerFlowResultConverter._element_result(
                flow,
                prepared,
                per_unit,
                is_transformer=False,
            )
            for branch_id, flow in line_flows.items()
        }
        transformer_results = {
            element_id: PowerFlowResultConverter._element_result(
                flow,
                prepared,
                per_unit,
                is_transformer=True,
            )
            for element_id, flow in transformer_flows.items()
        }

        enriched = PowerFlowResult(
            success=result.success,
            iterations=result.iterations,
            error=result.error,
            pv_to_pq=tuple(dict(item) for item in result.pv_to_pq),
            history=result.history,
            message=result.message,
            voltage_magnitudes=result.voltage_magnitudes,
            voltage_angles=result.voltage_angles,
            branch_results={key: _as_mapping(value) for key, value in branch_results.items()},
            transformer_results={key: _as_mapping(value) for key, value in transformer_results.items()},
            bus_results={key: _as_mapping(value) for key, value in bus_results.items()},
        )

        return EngineeringPowerFlowResult(
            numerical_result=enriched,
            buses=tuple(bus_results.values()),
            branch_results=MappingProxyType(branch_results),
            transformer_results=MappingProxyType(transformer_results),
        )

    @staticmethod
    def _bus_results(result: PowerFlowResult, prepared: Any, buses: tuple[Any, ...]) -> dict[str, EngineeringPowerFlowBusResult]:
        if len(result.voltage_magnitudes) != len(prepared.bus_ids) or len(result.voltage_angles) != len(prepared.bus_ids):
            raise ValueError("Power Flow result voltage arrays must match the prepared bus ordering.")
        if buses:
            by_id = {str(getattr(bus, "id", "")): bus for bus in buses}
            if set(by_id) != set(prepared.bus_ids):
                raise ValueError("Supplied buses must match prepared Power Flow bus IDs.")
        else:
            by_id = {}
        converted: dict[str, EngineeringPowerFlowBusResult] = {}
        for index, bus_id in enumerate(prepared.bus_ids):
            voltage_pu = float(result.voltage_magnitudes[index])
            angle_rad = float(result.voltage_angles[index])
            if not math.isfinite(voltage_pu) or voltage_pu <= 0.0 or not math.isfinite(angle_rad):
                raise ValueError(f"Power Flow result for Bus '{bus_id}' contains invalid voltage data.")
            kv = float(prepared.bus_voltage_bases[bus_id])
            converted[bus_id] = EngineeringPowerFlowBusResult(
                bus_id=bus_id,
                voltage_pu=voltage_pu,
                voltage_kv=voltage_pu * kv,
                angle_rad=angle_rad,
                angle_deg=math.degrees(angle_rad),
            )
        return converted

    @staticmethod
    def _element_result(flow: Any, prepared: Any, per_unit: PerUnitSystem, *, is_transformer: bool) -> EngineeringElementResult:
        element_id = str(flow.transformer_id if is_transformer else flow.line_id)
        if is_transformer:
            item = next((x for x in prepared.transformers if x.branch_id == element_id), None)
            i_from_pu = flow.i_from_pu
            i_to_pu = flow.i_to_pu
            p_loss_pu = flow.p_loss
            q_loss_pu = flow.q_loss
        else:
            item = next((x for x in prepared.branches if x.branch_id == element_id), None)
            i_from_pu = abs(flow.current_from)
            i_to_pu = abs(flow.current_to)
            p_loss_pu = flow.p_loss
            q_loss_pu = flow.q_balance
        if item is None:
            raise ValueError(f"Flow result '{element_id}' is absent from the prepared snapshot.")

        s_from_pu = abs(complex(flow.p_from, flow.q_from)) if is_transformer else flow.s_from_magnitude
        s_to_pu = abs(complex(flow.p_to, flow.q_to)) if is_transformer else flow.s_to_magnitude
        from_kv = float(prepared.bus_voltage_bases[item.from_bus_id])
        to_kv = float(prepared.bus_voltage_bases[item.to_bus_id])
        current_from_a = per_unit.from_pu_current(i_from_pu, from_kv) * 1000.0
        current_to_a = per_unit.from_pu_current(i_to_pu, to_kv) * 1000.0
        p_from_mw, q_from_mvar = per_unit.from_pu_power(complex(flow.p_from, flow.q_from))
        p_to_mw, q_to_mvar = per_unit.from_pu_power(complex(flow.p_to, flow.q_to))
        limit_mva = PowerFlowResultConverter._limit_mva(item, prepared, current_from_a, current_to_a)
        loading_percent = None if limit_mva is None else max(s_from_pu, s_to_pu) * prepared.base_mva / limit_mva * 100.0
        return EngineeringElementResult(
            element_id=element_id,
            from_bus_id=item.from_bus_id,
            to_bus_id=item.to_bus_id,
            current_from_a=current_from_a,
            current_to_a=current_to_a,
            p_from_mw=p_from_mw,
            q_from_mvar=q_from_mvar,
            mva_from=s_from_pu * prepared.base_mva,
            p_to_mw=p_to_mw,
            q_to_mvar=q_to_mvar,
            mva_to=s_to_pu * prepared.base_mva,
            loss_p_mw=p_loss_pu * prepared.base_mva,
            loss_q_mvar=q_loss_pu * prepared.base_mva,
            limit_mva=limit_mva,
            loading_percent=loading_percent,
            within_limit=None if loading_percent is None else loading_percent <= 100.0,
        )

    @staticmethod
    def _limit_mva(item: Any, prepared: Any, current_from_a: float, current_to_a: float) -> float | None:
        if hasattr(item, "rated_mva") and item.rated_mva is not None:
            return float(item.rated_mva)
        thermal = getattr(item, "thermal_limit_mva", None)
        if thermal is not None:
            return float(thermal)
        rated_current = getattr(item, "rated_current_a", None)
        if rated_current is not None:
            # Existing Cable semantics define current ampacity separately;
            # convert it using the declared terminal voltage base.
            kv = float(prepared.bus_voltage_bases[item.from_bus_id])
            return math.sqrt(3.0) * kv * float(rated_current) / 1000.0
        rate = getattr(item, "rate_mva", None)
        return None if rate is None else float(rate)


def _complex_voltage(Vm: Any, Va: Any):
    import numpy as np
    return np.asarray(Vm, dtype=float) * np.exp(1j * np.asarray(Va, dtype=float))


def _as_mapping(value: EngineeringElementResult) -> dict[str, Any]:
    return {
        "element_id": value.element_id,
        "from_bus_id": value.from_bus_id,
        "to_bus_id": value.to_bus_id,
        "current_from_a": value.current_from_a,
        "current_to_a": value.current_to_a,
        "p_from_mw": value.p_from_mw,
        "q_from_mvar": value.q_from_mvar,
        "mva_from": value.mva_from,
        "p_to_mw": value.p_to_mw,
        "q_to_mvar": value.q_to_mvar,
        "mva_to": value.mva_to,
        "loss_p_mw": value.loss_p_mw,
        "loss_q_mvar": value.loss_q_mvar,
        "limit_mva": value.limit_mva,
        "loading_percent": value.loading_percent,
        "within_limit": value.within_limit,
    }


__all__ = [
    "EngineeringPowerFlowBusResult",
    "EngineeringElementResult",
    "EngineeringPowerFlowResult",
    "PowerFlowResultConverter",
]
