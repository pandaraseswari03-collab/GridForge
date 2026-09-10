# ============================================================
# File: core/analysis/power_flow_preparation.py
# GridForge V2 — Power Flow Preparation
# Author: Subhendu Mishra
# ============================================================

"""Prepare detached numerical Power Flow snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

from core.analysis.power_flow_configuration import PowerFlowStudyConfiguration
from core.base.per_unit import PerUnitSystem
from core.model.cable import Cable
from core.model.capacitor import Capacitor
from core.model.injection import Injection
from core.model.line import Line
from core.model.reactor import Reactor
from core.model.transformer import Transformer
from core.network.endpoint import resolve_terminal_bus
from core.numerical.ybus import YBus, YBusBuilder
from core.solver.power_flow.input import PowerFlowBusType, PowerFlowInput


@dataclass(frozen=True, slots=True)
class PreparedBranch:
    """Detached PU representation plus immutable engineering limits."""

    branch_id: str
    from_bus_id: str
    to_bus_id: str
    r_pu: float
    x_pu: float
    b_pu: float
    in_service: bool = True
    rate_mva: float | None = None
    rated_current_a: float | None = None
    thermal_limit_mva: float | None = None

    def __post_init__(self) -> None:
        if not self.branch_id or not self.from_bus_id or not self.to_bus_id:
            raise ValueError("Prepared branch identifiers must be non-empty.")
        for value, name in ((self.r_pu, "r_pu"), (self.x_pu, "x_pu"), (self.b_pu, "b_pu")):
            if not math.isfinite(float(value)):
                raise ValueError(f"Prepared branch {name} must be finite.")
        if float(self.r_pu) == 0.0 and float(self.x_pu) == 0.0:
            raise ValueError("Prepared branch series impedance cannot be zero.")
        for value, name in ((self.rate_mva, "rate_mva"), (self.rated_current_a, "rated_current_a"), (self.thermal_limit_mva, "thermal_limit_mva")):
            if value is not None and (not math.isfinite(float(value)) or float(value) <= 0.0):
                raise ValueError(f"Prepared branch {name} must be positive and finite when provided.")
        object.__setattr__(self, "r_pu", float(self.r_pu))
        object.__setattr__(self, "x_pu", float(self.x_pu))
        object.__setattr__(self, "b_pu", float(self.b_pu))
        if self.rate_mva is not None:
            object.__setattr__(self, "rate_mva", float(self.rate_mva))
        if self.rated_current_a is not None:
            object.__setattr__(self, "rated_current_a", float(self.rated_current_a))
        if self.thermal_limit_mva is not None:
            object.__setattr__(self, "thermal_limit_mva", float(self.thermal_limit_mva))


@dataclass(frozen=True, slots=True)
class PreparedTransformer:
    """Detached PU representation of a transformer branch and rating."""

    branch_id: str
    from_bus_id: str
    to_bus_id: str
    r_pu: float
    x_pu: float
    b_pu: float
    tap: float
    shift: float
    in_service: bool = True
    rated_mva: float | None = None

    def __post_init__(self) -> None:
        if not self.branch_id or not self.from_bus_id or not self.to_bus_id:
            raise ValueError("Prepared transformer identifiers must be non-empty.")
        for value, name in ((self.r_pu, "r_pu"), (self.x_pu, "x_pu"), (self.b_pu, "b_pu"), (self.tap, "tap"), (self.shift, "shift")):
            if not math.isfinite(float(value)):
                raise ValueError(f"Prepared transformer {name} must be finite.")
        if float(self.r_pu) == 0.0 and float(self.x_pu) == 0.0:
            raise ValueError("Prepared transformer series impedance cannot be zero.")
        if float(self.tap) <= 0.0:
            raise ValueError("Prepared transformer tap must be positive.")
        if self.rated_mva is not None and (not math.isfinite(float(self.rated_mva)) or float(self.rated_mva) <= 0.0):
            raise ValueError("Prepared transformer rated_mva must be positive and finite when provided.")
        object.__setattr__(self, "r_pu", float(self.r_pu))
        object.__setattr__(self, "x_pu", float(self.x_pu))
        object.__setattr__(self, "b_pu", float(self.b_pu))
        object.__setattr__(self, "tap", float(self.tap))
        object.__setattr__(self, "shift", float(self.shift))
        if self.rated_mva is not None:
            object.__setattr__(self, "rated_mva", float(self.rated_mva))


@dataclass(frozen=True, slots=True)
class PreparedShunt:
    """Detached PU representation of a shunt admittance."""

    shunt_id: str
    bus_id: str
    g_pu: float
    b_pu: float
    in_service: bool = True

    def __post_init__(self) -> None:
        if not self.shunt_id or not self.bus_id:
            raise ValueError("Prepared shunt identifiers must be non-empty.")
        for value, name in ((self.g_pu, "g_pu"), (self.b_pu, "b_pu")):
            if not math.isfinite(float(value)):
                raise ValueError(f"Prepared shunt {name} must be finite.")
        object.__setattr__(self, "g_pu", float(self.g_pu))
        object.__setattr__(self, "b_pu", float(self.b_pu))


@dataclass(frozen=True, slots=True)
class PreparedPowerFlow:
    """Immutable, detached numerical Power Flow problem snapshot."""

    input: PowerFlowInput
    ybus: YBus
    base_mva: float
    bus_voltage_bases: Mapping[str, float]
    branches: tuple[PreparedBranch, ...] = ()
    transformers: tuple[PreparedTransformer, ...] = ()
    shunts: tuple[PreparedShunt, ...] = ()
    topology_revision: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.input, PowerFlowInput):
            raise TypeError("input must be a PowerFlowInput instance.")
        if not isinstance(self.ybus, YBus):
            raise TypeError("ybus must be a YBus instance.")
        if self.input.bus_ids != self.ybus.bus_ids:
            raise ValueError("PowerFlowInput and YBus must use identical bus ordering.")
        base_mva = float(self.base_mva)
        if not math.isfinite(base_mva) or base_mva <= 0.0:
            raise ValueError("Prepared Power Flow base MVA must be positive and finite.")
        bases = {str(bus_id): float(value) for bus_id, value in self.bus_voltage_bases.items()}
        if set(bases) != set(self.input.bus_ids):
            raise ValueError("Prepared voltage bases must match PowerFlowInput bus IDs.")
        if any(not math.isfinite(value) or value <= 0.0 for value in bases.values()):
            raise ValueError("Prepared voltage bases must be positive and finite.")
        object.__setattr__(self, "base_mva", base_mva)
        object.__setattr__(self, "bus_voltage_bases", MappingProxyType(bases))
        object.__setattr__(self, "branches", tuple(self.branches))
        object.__setattr__(self, "transformers", tuple(self.transformers))
        object.__setattr__(self, "shunts", tuple(self.shunts))

    @property
    def bus_ids(self) -> tuple[str, ...]:
        return self.input.bus_ids


class PowerFlowPreparation:
    """Own the live-model to detached numerical Power Flow boundary."""

    _INJECTION_COLLECTIONS = ("grids", "generators", "synchronous_machines", "loads", "motors", "solar", "batteries")

    @staticmethod
    def prepare(network: Any, power_flow_configuration: PowerFlowStudyConfiguration) -> PreparedPowerFlow:
        return PowerFlowPreparation(network, power_flow_configuration)._prepare()

    def __init__(self, network: Any, power_flow_configuration: PowerFlowStudyConfiguration) -> None:
        self.network = network
        self.power_flow_configuration = power_flow_configuration
        self._validate_network()
        if not isinstance(power_flow_configuration, PowerFlowStudyConfiguration):
            raise TypeError("power_flow_configuration must be a PowerFlowStudyConfiguration.")
        self._per_unit = PerUnitSystem(power_flow_configuration.base_mva)

    def _prepare(self) -> PreparedPowerFlow:
        buses = tuple(self.network.buses)
        if not buses:
            raise ValueError("Power Flow preparation requires at least one bus.")
        bus_ids = tuple(str(bus.id) for bus in buses)
        classification = self._prepare_bus_types(bus_ids)
        voltage_bases = self._prepare_voltage_bases(buses)
        p_spec: list[float] = []
        q_spec: list[float] = []
        q_min: list[float | None] = []
        q_max: list[float | None] = []
        initial_vm: list[float] = []
        initial_va: list[float] = []
        for bus in buses:
            p, q, minimum_q, maximum_q = self._bus_power_spec(bus)
            s_pu = self._per_unit.to_pu_power(p, q)
            p_spec.append(s_pu.real)
            q_spec.append(s_pu.imag)
            q_min.append(self._to_pu_reactive_power(minimum_q))
            q_max.append(self._to_pu_reactive_power(maximum_q))
            initial_vm.append(self._initial_voltage_pu(bus))
            initial_va.append(math.radians(self._finite(getattr(bus, "angle_deg", 0.0), f"Bus '{bus.id}' angle_deg")))

        input_data = PowerFlowInput(
            bus_ids=bus_ids, bus_types=classification, p_spec=tuple(p_spec), q_spec=tuple(q_spec),
            q_min=tuple(q_min), q_max=tuple(q_max), initial_vm=tuple(initial_vm), initial_va=tuple(initial_va),
        )
        branches = self._prepare_branches(voltage_bases)
        transformers = self._prepare_transformers(voltage_bases)
        shunts = self._prepare_shunts(voltage_bases)
        topology_revision = getattr(self.network, "topology_revision", None)
        snapshot = PreparedPowerFlow(
            input=input_data,
            ybus=YBus(matrix=self._empty_ybus_matrix(len(bus_ids)), bus_ids=bus_ids, topology_revision=topology_revision),
            base_mva=self._per_unit.base_mva,
            bus_voltage_bases=voltage_bases,
            branches=branches,
            transformers=transformers,
            shunts=shunts,
            topology_revision=topology_revision,
        )
        ybus = YBusBuilder().build(snapshot)
        return PreparedPowerFlow(
            input=input_data, ybus=ybus, base_mva=snapshot.base_mva,
            bus_voltage_bases=snapshot.bus_voltage_bases, branches=branches,
            transformers=transformers, shunts=shunts, topology_revision=snapshot.topology_revision,
        )

    @staticmethod
    def _empty_ybus_matrix(size: int):
        import numpy as np
        from scipy.sparse import csr_matrix
        return csr_matrix((size, size), dtype=np.complex128)

    def _prepare_voltage_bases(self, buses: tuple[Any, ...]) -> dict[str, float]:
        return {str(bus.id): self._finite_positive(getattr(bus, "nominal_voltage_kv", 0.0), f"Bus '{bus.id}' nominal_voltage_kv") for bus in buses}

    def _prepare_branches(self, voltage_bases: Mapping[str, float]) -> tuple[PreparedBranch, ...]:
        prepared: list[PreparedBranch] = []
        for branch in getattr(self.network, "lines", ()):
            if not getattr(branch, "in_service", True):
                continue
            if not isinstance(branch, Line):
                raise TypeError(f"Network line '{getattr(branch, 'id', branch)}' is not a Line model.")
            from_bus, to_bus = self._resolve_branch_endpoints(branch)
            kv = self._common_branch_voltage(from_bus, to_bus, voltage_bases, branch)
            z_pu = self._per_unit.to_pu_impedance(branch.series_impedance, kv)
            b_pu = self._per_unit.to_pu_admittance(complex(0.0, branch.shunt_susceptance_siemens), kv).imag
            prepared.append(PreparedBranch(str(branch.id), str(from_bus.id), str(to_bus.id), z_pu.real, z_pu.imag, b_pu, True, branch.rate_mva, None, None))

        for cable in getattr(self.network, "cables", ()):
            if not getattr(cable, "in_service", True):
                continue
            if not isinstance(cable, Cable):
                raise TypeError(f"Network cable '{getattr(cable, 'id', cable)}' is not a Cable model.")
            from_bus, to_bus = self._resolve_branch_endpoints(cable)
            kv = self._common_branch_voltage(from_bus, to_bus, voltage_bases, cable)
            z_pu = self._per_unit.to_pu_impedance(complex(cable.resistance_ohm, cable.reactance_ohm), kv)
            b_pu = self._per_unit.to_pu_admittance(complex(0.0, cable.shunt_susceptance_siemens), kv).imag
            prepared.append(PreparedBranch(str(cable.id), str(from_bus.id), str(to_bus.id), z_pu.real, z_pu.imag, b_pu, True, None, cable.rated_current_a, cable.thermal_limit_mva))
        return tuple(prepared)

    def _prepare_transformers(self, voltage_bases: Mapping[str, float]) -> tuple[PreparedTransformer, ...]:
        prepared: list[PreparedTransformer] = []
        for transformer in getattr(self.network, "transformers", ()):
            if not getattr(transformer, "in_service", True):
                continue
            if not isinstance(transformer, Transformer):
                raise TypeError(f"Network transformer '{getattr(transformer, 'id', transformer)}' is not a Transformer model.")
            from_bus, to_bus = self._resolve_branch_endpoints(transformer)
            reference_kv = transformer.impedance_base_voltage_kv
            from_kv = voltage_bases[str(from_bus.id)]
            if not math.isclose(reference_kv, from_kv, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Transformer '{transformer.id}' impedance reference voltage {reference_kv:g} kV does not match FROM bus voltage base {from_kv:g} kV. Declare engineering/PU impedance on the actual transformer-side voltage base.")
            if transformer.impedance_basis == "pu":
                z_pu = self._per_unit.convert_impedance_base(complex(transformer.r, transformer.x), transformer.impedance_base_mva, reference_kv, from_kv)
                b_pu = self._per_unit.convert_admittance_base(complex(0.0, transformer.b), transformer.impedance_base_mva, reference_kv, from_kv).imag
            elif transformer.impedance_basis == "engineering":
                z_pu = self._per_unit.to_pu_impedance(complex(transformer.r, transformer.x), reference_kv)
                b_pu = self._per_unit.to_pu_admittance(complex(0.0, transformer.b), reference_kv).imag
            else:
                raise ValueError(f"Transformer '{transformer.id}' has unsupported impedance basis {transformer.impedance_basis!r}.")
            prepared.append(PreparedTransformer(str(transformer.id), str(from_bus.id), str(to_bus.id), z_pu.real, z_pu.imag, b_pu, transformer.tap, transformer.shift, True, transformer.rated_mva))
        return tuple(prepared)

    def _prepare_shunts(self, voltage_bases: Mapping[str, float]) -> tuple[PreparedShunt, ...]:
        prepared: list[PreparedShunt] = []
        for shunt in getattr(self.network, "shunts", ()):
            if not getattr(shunt, "in_service", True):
                continue
            bus = self._resolve_shunt_bus(shunt)
            prepared.append(PreparedShunt(str(shunt.id), str(bus.id), float(shunt.g_pu), float(shunt.b_pu), True))
        for equipment in (*getattr(self.network, "capacitors", ()), *getattr(self.network, "reactors", ())):
            if not getattr(equipment, "in_service", True):
                continue
            if not isinstance(equipment, (Capacitor, Reactor)):
                raise TypeError(f"Reactive shunt '{getattr(equipment, 'id', equipment)}' is not a supported Capacitor/Reactor model.")
            bus = self._resolve_shunt_bus(equipment)
            bus_kv = voltage_bases[str(bus.id)]
            q_mvar = self._finite(equipment.get_power()[1], f"Reactive shunt '{equipment.id}' reactive power")
            q_pu = self._per_unit.to_pu_power(0.0, q_mvar).imag
            if bus_kv <= 0.0:
                raise ValueError(f"Reactive shunt '{equipment.id}' has invalid bus voltage base.")
            prepared.append(PreparedShunt(str(equipment.id), str(bus.id), 0.0, -q_pu, True))
        return tuple(prepared)

    @staticmethod
    def _resolve_branch_endpoints(branch: Any) -> tuple[Any, Any]:
        try:
            from_bus = resolve_terminal_bus(branch.from_terminal)
            to_bus = resolve_terminal_bus(branch.to_terminal)
        except Exception as exc:
            raise ValueError(f"Element '{getattr(branch, 'id', branch)}' has unresolved branch terminals.") from exc
        if from_bus is None or to_bus is None:
            raise ValueError(f"Element '{getattr(branch, 'id', branch)}' has unresolved branch terminals.")
        return from_bus, to_bus

    @staticmethod
    def _resolve_shunt_bus(shunt: Any) -> Any:
        try:
            bus = resolve_terminal_bus(shunt.terminal)
        except Exception as exc:
            raise ValueError(f"Shunt '{getattr(shunt, 'id', shunt)}' has an unresolved terminal.") from exc
        if bus is None:
            raise ValueError(f"Shunt '{getattr(shunt, 'id', shunt)}' has an unresolved terminal.")
        return bus

    def _common_branch_voltage(self, from_bus: Any, to_bus: Any, voltage_bases: Mapping[str, float], branch: Any) -> float:
        from_kv = voltage_bases[str(from_bus.id)]
        to_kv = voltage_bases[str(to_bus.id)]
        if not math.isclose(from_kv, to_kv, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"Branch '{getattr(branch, 'id', branch)}' connects incompatible voltage bases ({from_kv:g} kV and {to_kv:g} kV); use a Transformer for a voltage change.")
        return from_kv

    def _to_pu_reactive_power(self, value: float | None) -> float | None:
        return None if value is None else self._per_unit.to_pu_power(0.0, value).imag

    def _prepare_bus_types(self, bus_ids: tuple[str, ...]) -> tuple[PowerFlowBusType, ...]:
        configured = self.power_flow_configuration.bus_types
        expected = set(bus_ids)
        supplied = set(configured)
        missing = expected - supplied
        extra = supplied - expected
        if missing or extra:
            raise ValueError("Power Flow study configuration must match the case Network buses; " f"missing={sorted(missing)!r}, extra={sorted(extra)!r}.")
        return tuple(configured[bus_id] for bus_id in bus_ids)

    def _initial_voltage_pu(self, bus: Any) -> float:
        return self._finite_positive(getattr(bus, "voltage_pu", 1.0), f"Bus '{bus.id}' voltage_pu")

    def _bus_power_spec(self, bus: Any) -> tuple[float, float, float | None, float | None]:
        p = q = 0.0
        q_min: float | None = None
        q_max: float | None = None
        for collection_name in self._INJECTION_COLLECTIONS:
            for equipment in getattr(self.network, collection_name, ()):
                if not isinstance(equipment, Injection) or not getattr(equipment, "in_service", True):
                    continue
                terminal = getattr(equipment, "terminal", None)
                endpoint = getattr(terminal, "endpoint", None)
                if endpoint is not bus and getattr(endpoint, "id", None) != getattr(bus, "id", None):
                    continue
                ep, eq = equipment.get_power()
                p += self._finite(ep, f"Injection '{getattr(equipment, 'id', equipment)}' active power")
                q += self._finite(eq, f"Injection '{getattr(equipment, 'id', equipment)}' reactive power")
                if hasattr(equipment, "q_min"):
                    value = self._finite(getattr(equipment, "q_min"), f"Injection '{getattr(equipment, 'id', equipment)}' q_min")
                    q_min = value if q_min is None else q_min + value
                if hasattr(equipment, "q_max"):
                    value = self._finite(getattr(equipment, "q_max"), f"Injection '{getattr(equipment, 'id', equipment)}' q_max")
                    q_max = value if q_max is None else q_max + value
        if q_min is not None and q_max is not None and q_min > q_max:
            raise ValueError(f"Aggregated reactive limits at bus '{bus.id}' are invalid.")
        return p, q, q_min, q_max

    @staticmethod
    def _finite(value: Any, name: str) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric.") from exc
        if not math.isfinite(numeric):
            raise ValueError(f"{name} must be finite.")
        return numeric

    @classmethod
    def _finite_positive(cls, value: Any, name: str) -> float:
        numeric = cls._finite(value, name)
        if numeric <= 0.0:
            raise ValueError(f"{name} must be greater than zero.")
        return numeric

    def _validate_network(self) -> None:
        if self.network is None:
            raise ValueError("network is required for Power Flow preparation.")
        if not hasattr(self.network, "buses"):
            raise TypeError("network must expose buses.")


__all__ = ["PowerFlowPreparation", "PreparedBranch", "PreparedTransformer", "PreparedShunt", "PreparedPowerFlow"]
