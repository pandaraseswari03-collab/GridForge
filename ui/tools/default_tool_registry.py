# ============================================================
# GridForge V2 — Default UI Tool Registry
# Author: Subhendu Mishra
# ============================================================
"""Default concrete UI tool factories for GridForge V2."""

from __future__ import annotations

from typing import Any, Callable

from ui.core.line_creation_parameters import LineCreationParameters
from ui.tools.battery_tool import BatteryTool
from ui.tools.breaker_tool import BreakerTool
from ui.tools.bus_tool import BusTool
from ui.tools.cable_tool import CableTool
from ui.tools.capacitor_tool import CapacitorTool
from ui.tools.cvt_tool import CVTTool
from ui.tools.current_transformer_tool import CurrentTransformerTool
from ui.tools.disconnector_tool import DisconnectorTool
from ui.tools.fuse_tool import FuseTool
from ui.tools.generator_tool import GeneratorTool
from ui.tools.grid_tool import GridTool
from ui.tools.line_tool import LineTool
from ui.tools.load_tool import LoadTool
from ui.tools.motor_tool import MotorTool
from ui.tools.potential_transformer_tool import PotentialTransformerTool
from ui.tools.reactor_tool import ReactorTool
from ui.tools.relay_tool import RelayTool
from ui.tools.select_tool import SelectTool
from ui.tools.shunt_tool import ShuntTool
from ui.tools.solar_tool import SolarTool
from ui.tools.switch_tool import SwitchTool
from ui.tools.synchronous_machine_tool import SynchronousMachineTool
from ui.tools.transformer_tool import TransformerTool

ToolFactory = Callable[..., Any]


def create_default_tool_factories(
    *,
    controller: Any,
    command_manager: Any = None,
    selection_manager: Any,
    snap_system: Any,
    line_creation_parameters: LineCreationParameters | None = None,
) -> dict[str, ToolFactory]:
    """Return the standard concrete-tool factory mapping.

    LineTool receives its engineering configuration explicitly rather than
    reading it from Controller. Other legacy tools retain their existing
    constructor contract until their own ownership is audited.
    """

    def factory(tool_class: type[Any]) -> ToolFactory:
        return lambda **_ignored: tool_class(
            controller=controller,
            command_manager=command_manager,
            selection_manager=selection_manager,
            snap_system=snap_system,
        )

    def line_factory(**_ignored: Any) -> LineTool:
        return LineTool(
            controller=controller,
            command_manager=command_manager,
            selection_manager=selection_manager,
            snap_system=snap_system,
            line_creation_parameters=line_creation_parameters,
        )

    return {
        "select": factory(SelectTool),
        "bus": factory(BusTool),
        "line": line_factory,
        "cable": factory(CableTool),
        "transformer": factory(TransformerTool),
        "switch": factory(SwitchTool),
        "breaker": factory(BreakerTool),
        "disconnector": factory(DisconnectorTool),
        "fuse": factory(FuseTool),
        "load": factory(LoadTool),
        "generator": factory(GeneratorTool),
        "synchronous_machine": factory(SynchronousMachineTool),
        "motor": factory(MotorTool),
        "shunt": factory(ShuntTool),
        "capacitor": factory(CapacitorTool),
        "reactor": factory(ReactorTool),
        "solar": factory(SolarTool),
        "battery": factory(BatteryTool),
        "grid": factory(GridTool),
        "current_transformer": factory(CurrentTransformerTool),
        "potential_transformer": factory(PotentialTransformerTool),
        "cvt": factory(CVTTool),
        "relay": factory(RelayTool),
    }


__all__ = ["ToolFactory", "create_default_tool_factories"]
