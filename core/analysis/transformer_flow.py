"""Transformer terminal-flow evaluation from detached Power Flow data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import numpy as np

from core.analysis.power_flow_preparation import PreparedPowerFlow, PreparedTransformer


@dataclass(frozen=True)
class TransformerFlowResult:
    """Immutable result of one transformer terminal-flow calculation."""

    transformer_id: Any
    from_bus: Any
    to_bus: Any
    tap_ratio: float
    phase_shift_deg: float
    p_from: float
    q_from: float
    p_to: float
    q_to: float
    p_loss: float
    q_loss: float
    s_from_pu: float
    s_to_pu: float
    i_from_pu: float
    i_to_pu: float
    loading_mva: Optional[float] = None
    loading_percent: Optional[float] = None
    in_service: bool = True

    @property
    def s_from(self) -> complex:
        return complex(self.p_from, self.q_from)

    @property
    def s_to(self) -> complex:
        return complex(self.p_to, self.q_to)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["s_from"] = {"real": float(self.s_from.real), "imag": float(self.s_from.imag)}
        data["s_to"] = {"real": float(self.s_to.real), "imag": float(self.s_to.imag)}
        return data


class TransformerFlowCalculator:
    """Calculate transformer flows from one detached PreparedPowerFlow."""

    _IMPEDANCE_TOLERANCE = 1.0e-12

    def __init__(self, network: Any = None, prepared: PreparedPowerFlow | None = None) -> None:
        if prepared is None:
            raise ValueError("TransformerFlowCalculator requires a PreparedPowerFlow snapshot; live transformer impedance is not a numerical source.")
        if not isinstance(prepared, PreparedPowerFlow):
            raise TypeError("prepared must be a PreparedPowerFlow instance.")
        self.network = network
        self.prepared = prepared
        self._transformers = {item.branch_id: item for item in prepared.transformers}
        self._bus_index = {bus_id: index for index, bus_id in enumerate(prepared.bus_ids)}

    @classmethod
    def from_prepared(cls, prepared: PreparedPowerFlow, network: Any = None) -> "TransformerFlowCalculator":
        return cls(network=network, prepared=prepared)

    def calculate(self, Vm: np.ndarray, Va: np.ndarray, include_out_of_service: bool = False) -> Dict[Any, TransformerFlowResult]:
        Vm, Va = self._validate_voltage_arrays(Vm, Va)
        results: Dict[Any, TransformerFlowResult] = {}
        for transformer in self.prepared.transformers:
            if not transformer.in_service:
                if include_out_of_service:
                    results[transformer.branch_id] = self._out_of_service_result(transformer)
                continue
            results[transformer.branch_id] = self.calculate_prepared(transformer, Vm, Va)
        return results

    def calculate_one(self, transformer: Any, Vm: np.ndarray, Va: np.ndarray) -> TransformerFlowResult:
        Vm, Va = self._validate_voltage_arrays(Vm, Va)
        transformer_id = getattr(transformer, "id", transformer)
        try:
            prepared = self._transformers[str(transformer_id)]
        except KeyError as exc:
            raise ValueError(f"Transformer '{transformer_id}' is absent from PreparedPowerFlow.") from exc
        return self.calculate_prepared(prepared, Vm, Va)

    def calculate_prepared(self, transformer: PreparedTransformer, Vm: np.ndarray, Va: np.ndarray) -> TransformerFlowResult:
        if not isinstance(transformer, PreparedTransformer):
            raise TypeError("transformer must be a PreparedTransformer instance.")
        if not transformer.in_service:
            raise ValueError(f"Transformer '{transformer.branch_id}' is out of service.")
        Vm, Va = self._validate_voltage_arrays(Vm, Va)
        try:
            i = self._bus_index[transformer.from_bus_id]
            j = self._bus_index[transformer.to_bus_id]
        except KeyError as exc:
            raise ValueError(f"Prepared transformer '{transformer.branch_id}' references an unknown bus.") from exc

        V_from = Vm[i] * np.exp(1j * Va[i])
        V_to = Vm[j] * np.exp(1j * Va[j])
        z = complex(transformer.r_pu, transformer.x_pu)
        if abs(z) <= self._IMPEDANCE_TOLERANCE:
            raise ValueError(f"Transformer '{transformer.branch_id}' has zero series impedance.")
        y = 1.0 / z
        a = transformer.tap * np.exp(1j * transformer.shift)
        if abs(a) <= self._IMPEDANCE_TOLERANCE:
            raise ValueError(f"Transformer '{transformer.branch_id}' has a zero tap ratio.")

        # Exactly match YBusBuilder._stamp_transformer():
        # Yff=y/|a|²+jB/2, Yft=-y/conj(a),
        # Ytf=-y/a, Ytt=y+jB/2.
        ysh = 1j * transformer.b_pu / 2.0
        I_from = (y / abs(a) ** 2 + ysh) * V_from - (y / np.conj(a)) * V_to
        I_to = -(y / a) * V_from + (y + ysh) * V_to
        S_from = V_from * np.conj(I_from)
        S_to = V_to * np.conj(I_to)

        return TransformerFlowResult(
            transformer_id=transformer.branch_id,
            from_bus=transformer.from_bus_id,
            to_bus=transformer.to_bus_id,
            tap_ratio=float(transformer.tap),
            phase_shift_deg=float(np.degrees(transformer.shift)),
            p_from=float(S_from.real),
            q_from=float(S_from.imag),
            p_to=float(S_to.real),
            q_to=float(S_to.imag),
            p_loss=float((S_from + S_to).real),
            q_loss=float((S_from + S_to).imag),
            s_from_pu=float(abs(S_from)),
            s_to_pu=float(abs(S_to)),
            i_from_pu=float(abs(I_from)),
            i_to_pu=float(abs(I_to)),
            loading_mva=None,
            loading_percent=None,
            in_service=True,
        )

    def _validate_voltage_arrays(self, Vm: np.ndarray, Va: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        Vm = np.asarray(Vm, dtype=float).reshape(-1)
        Va = np.asarray(Va, dtype=float).reshape(-1)
        expected = len(self.prepared.bus_ids)
        if len(Vm) != expected or len(Va) != expected:
            raise ValueError(f"Voltage arrays must match prepared bus count: expected {expected}, received Vm={len(Vm)}, Va={len(Va)}.")
        if not np.all(np.isfinite(Vm)) or not np.all(np.isfinite(Va)):
            raise ValueError("Voltage arrays contain NaN or infinite values.")
        return Vm, Va

    @staticmethod
    def _out_of_service_result(transformer: PreparedTransformer) -> TransformerFlowResult:
        return TransformerFlowResult(
            transformer_id=transformer.branch_id,
            from_bus=transformer.from_bus_id,
            to_bus=transformer.to_bus_id,
            tap_ratio=float(transformer.tap),
            phase_shift_deg=float(np.degrees(transformer.shift)),
            p_from=0.0,
            q_from=0.0,
            p_to=0.0,
            q_to=0.0,
            p_loss=0.0,
            q_loss=0.0,
            s_from_pu=0.0,
            s_to_pu=0.0,
            i_from_pu=0.0,
            i_to_pu=0.0,
            loading_mva=None,
            loading_percent=None,
            in_service=False,
        )

    def __repr__(self) -> str:
        return f"TransformerFlowCalculator(transformers={len(self.prepared.transformers)}, buses={len(self.prepared.bus_ids)})"


__all__ = ["TransformerFlowResult", "TransformerFlowCalculator"]
