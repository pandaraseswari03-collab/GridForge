"""Executable regression coverage for the Core endpoint boundary."""

from __future__ import annotations

import importlib

import pytest

from core.model.bus import Bus
from core.model.generator import Generator
from core.model.line import Line
from core.network.endpoint import resolve_terminal_bus
from core.network.network import Network


class EndpointAdapter:
    """Minimal existing-compatible endpoint wrapper for resolver coverage."""

    def __init__(self, object_id: str, bus: Bus) -> None:
        self.id = object_id
        self.bus = bus


def make_network() -> tuple[Network, Bus, Bus]:
    network = Network()
    bus_a = Bus("BUS-A", nominal_voltage_kv=110.0)
    bus_b = Bus("BUS-B", nominal_voltage_kv=110.0)
    network.add_bus(bus_a)
    network.add_bus(bus_b)
    return network, bus_a, bus_b


def test_endpoint_module_imports_successfully() -> None:
    module = importlib.import_module("core.network.endpoint")
    assert callable(module.resolve_terminal_bus)


def test_valid_direct_endpoint_resolves_to_bus() -> None:
    _, bus, _ = make_network()
    generator = Generator("GEN-1", endpoint=bus)

    assert resolve_terminal_bus(generator.terminal) is bus


def test_valid_endpoint_adapter_resolves_through_bus() -> None:
    _, bus, _ = make_network()
    generator = Generator("GEN-1", endpoint=EndpointAdapter("EP-1", bus))

    assert resolve_terminal_bus(generator.terminal) is bus


def test_disconnected_terminal_is_explicitly_distinct_from_invalid_endpoint() -> None:
    generator = Generator("GEN-1")

    assert generator.terminal.endpoint is None
    assert generator.terminal.is_connected is False

    with pytest.raises(ValueError, match="does not have an endpoint"):
        resolve_terminal_bus(generator.terminal)


def test_terminal_to_terminal_endpoint_is_rejected() -> None:
    _, bus, _ = make_network()
    generator = Generator("GEN-1", endpoint=bus)

    class MalformedTerminal:
        endpoint = generator.terminal

    with pytest.raises(ValueError, match="Terminal-to-Terminal"):
        resolve_terminal_bus(MalformedTerminal())


def test_attach_and_detach_preserve_terminal_authority() -> None:
    _, bus_a, bus_b = make_network()
    generator = Generator("GEN-1")

    generator.terminal.attach(bus_a)
    assert generator.terminal.endpoint is bus_a
    assert generator.endpoint is bus_a
    assert generator.is_connected is True

    generator.terminal.attach(bus_b)
    assert generator.terminal.endpoint is bus_b
    assert generator.endpoint is bus_b

    generator.terminal.detach()
    assert generator.terminal.endpoint is None
    assert generator.is_connected is False


def test_topology_resolves_branch_terminals_through_canonical_endpoint_path() -> None:
    network, bus_a, bus_b = make_network()
    line = Line(
        id="LINE-1",
        endpoint_from=bus_a,
        endpoint_to=bus_b,
        resistance_ohm=0.1,
        reactance_ohm=0.2,
    )
    network.add_line(line)

    assert network.topology.is_connected(bus_a, bus_b) is True
    assert network.topology.branches_between(bus_a, bus_b) == [line]


def test_disconnected_branch_terminal_does_not_create_phantom_topology() -> None:
    network, bus_a, bus_b = make_network()
    line = Line(
        id="LINE-1",
        endpoint_from=bus_a,
        endpoint_to=None,
        resistance_ohm=0.1,
        reactance_ohm=0.2,
    )
    network.add_line(line)

    assert network.topology.is_connected(bus_a, bus_b) is False
    assert network.topology.branches_between(bus_a, bus_b) == []


def test_unregistered_endpoint_is_rejected_by_network_topology() -> None:
    network, bus_a, _ = make_network()
    foreign_bus = Bus("BUS-FOREIGN", nominal_voltage_kv=110.0)
    line = Line(
        id="LINE-1",
        endpoint_from=bus_a,
        endpoint_to=foreign_bus,
        resistance_ohm=0.1,
        reactance_ohm=0.2,
    )
    network.add_line(line)

    with pytest.raises(ValueError, match="unregistered Bus"):
        network.rebuild_topology()


def test_reordering_bus_collection_does_not_change_connectivity() -> None:
    network, bus_a, bus_b = make_network()
    line = Line(
        id="LINE-1",
        endpoint_from=bus_a,
        endpoint_to=bus_b,
        resistance_ohm=0.1,
        reactance_ohm=0.2,
    )
    network.add_line(line)
    assert network.topology.is_connected(bus_a, bus_b) is True

    network.registry._buses = {
        bus_b.id: bus_b,
        bus_a.id: bus_a,
    }
    network.invalidate_topology()

    assert network.topology.is_connected(bus_a, bus_b) is True
    assert network.topology.branches_between(bus_a, bus_b) == [line]


def test_terminal_identity_is_owner_plus_role_not_collection_position() -> None:
    _, bus_a, _ = make_network()
    generator_a = Generator("GEN-A", endpoint=bus_a)
    generator_b = Generator("GEN-B", endpoint=bus_a)

    assert generator_a.terminal.owner is generator_a
    assert generator_b.terminal.owner is generator_b
    assert generator_a.terminal.role == generator_b.terminal.role == "terminal"
