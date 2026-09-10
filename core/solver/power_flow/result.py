"""Immutable standalone result contract for AC power flow."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


def _tuple_floats(values):
    result = tuple(float(value) for value in values)
    if not all(isfinite(value) for value in result):
        raise ValueError("Numerical result values must be finite.")
    return result


def _immutable_records(values):
    return tuple(MappingProxyType(dict(item)) for item in values)


def _immutable_mapping(value):
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(key): MappingProxyType(dict(record)) for key, record in value.items()})


@dataclass(frozen=True, slots=True)
class PowerFlowResult:
    """Completed Power Flow result with immutable numerical and engineering state.

    The numerical solver owns voltage-state fields. Analysis enriches the
    same result contract with engineering branch/transformer evaluations;
    no second result authority is created.
    """

    success: bool
    iterations: int
    error: float
    pv_to_pq: tuple[Mapping[str, Any], ...]
    history: tuple[float, ...]
    message: str
    voltage_magnitudes: tuple[float, ...]
    voltage_angles: tuple[float, ...]
    branch_results: Mapping[str, Mapping[str, Any]] | None = None
    transformer_results: Mapping[str, Mapping[str, Any]] | None = None
    bus_results: Mapping[str, Mapping[str, Any]] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "pv_to_pq", _immutable_records(self.pv_to_pq))
        object.__setattr__(self, "history", _tuple_floats(self.history))
        object.__setattr__(self, "voltage_magnitudes", _tuple_floats(self.voltage_magnitudes))
        object.__setattr__(self, "voltage_angles", _tuple_floats(self.voltage_angles))
        object.__setattr__(self, "branch_results", _immutable_mapping(self.branch_results))
        object.__setattr__(self, "transformer_results", _immutable_mapping(self.transformer_results))
        object.__setattr__(self, "bus_results", _immutable_mapping(self.bus_results))
        if len(self.voltage_magnitudes) != len(self.voltage_angles):
            raise ValueError("Voltage magnitude and angle result lengths must match.")
        if self.iterations < 0:
            raise ValueError("iterations cannot be negative.")
        if not isfinite(float(self.error)) and float(self.error) != float("inf"):
            raise ValueError("error must be finite or positive infinity.")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string.")

    @property
    def voltages(self) -> dict[str, tuple[float, ...]]:
        return {"Vm": self.voltage_magnitudes, "Va": self.voltage_angles}

    @property
    def converged(self) -> bool:
        """Compatibility alias for consumers that use engineering terminology."""
        return self.success

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "converged": self.converged,
            "iterations": self.iterations,
            "error": self.error,
            "pv_to_pq": tuple(dict(item) for item in self.pv_to_pq),
            "history": self.history,
            "message": self.message,
            "voltages": self.voltages,
            "bus_results": {key: dict(value) for key, value in self.bus_results.items()},
            "branch_results": {key: dict(value) for key, value in self.branch_results.items()},
            "transformer_results": {key: dict(value) for key, value in self.transformer_results.items()},
        }


__all__ = ["PowerFlowResult"]
