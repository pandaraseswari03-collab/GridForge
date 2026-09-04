# ============================================================
# GridForge V2
# ============================================================
# File:
#     ui/tools/bus_tool.py
# ============================================================

from __future__ import annotations

from typing import Any, Optional, Tuple
from uuid import uuid4

from core.application.commands.model_commands import CreateBusCommand

from .tool_base import ToolBase


class BusTool(ToolBase):
    """SLD bus-placement interaction tool."""

    TOOL_ID = "bus"

    def __init__(
        self,
        command_manager: Any,
        selection_manager: Any,
        snap_system: Any,
    ) -> None:
        super().__init__(
            command_manager=command_manager,
            selection_manager=selection_manager,
            snap_system=snap_system,
        )
        self._position: Optional[Tuple[float, float]] = None
        self._preview_active = False

    @property
    def tool_id(self) -> str:
        return self.TOOL_ID

    @property
    def name(self) -> str:
        return "Bus"

    @property
    def description(self) -> str:
        return "Place a bus on the SLD canvas."

    def on_activate(self) -> None:
        self._clear_state()

    def on_deactivate(self) -> None:
        self._clear_state()

    def on_mouse_press(self, event: Any) -> bool:
        self._ensure_active()
        position = self._snap_position(event)
        if position is None:
            return False
        self._position = position
        self._preview_active = True
        return True

    def on_mouse_move(self, event: Any) -> bool:
        self._ensure_active()
        position = self._snap_position(event)
        if position is None:
            return False
        self._position = position
        self._preview_active = True
        return True

    def on_mouse_release(self, event: Any) -> bool:
        self._ensure_active()
        position = self._snap_position(event)
        if position is None:
            self._clear_state()
            return False
        self._position = position
        command = CreateBusCommand(
            bus_id=f"bus-{uuid4()}",
            name="Bus",
            nominal_voltage_kv=0.0,
            voltage_pu=1.0,
            angle_deg=0.0,
            frequency_hz=50.0,
            in_service=True,
        )
        result = self.execute_command(command)
        self._clear_state()
        return result

    def on_mouse_double_click(self, event: Any) -> bool:
        return self.on_mouse_press(event)

    def on_key_press(self, event: Any) -> bool:
        self._ensure_active()
        if self._is_escape_event(event):
            return self.on_cancel()
        return False

    def on_cancel(self) -> bool:
        self._ensure_active()
        had_state = self._preview_active or self._position is not None
        self._clear_state()
        return had_state

    def on_reset(self) -> None:
        self._ensure_active()
        self._clear_state()

    def _snap_position(self, event: Any) -> Optional[Tuple[float, float]]:
        scene_position = self.event_position(event)
        snap = getattr(self.get_snap_system(), "snap", None)
        if not callable(snap):
            raise TypeError("SnapSystem must provide snap().")
        result = snap(scene_position, allow_grid=True, allow_object=True)
        position = getattr(result, "position", None)
        if position is None:
            return None
        if hasattr(position, "x") and hasattr(position, "y"):
            return float(position.x()), float(position.y())
        if isinstance(position, (tuple, list)) and len(position) >= 2:
            return float(position[0]), float(position[1])
        raise TypeError("SnapResult.position must provide x/y coordinates or a two-element position.")

    def _clear_state(self) -> None:
        self._position = None
        self._preview_active = False

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        state.update({"position": self._position, "preview_active": self._preview_active})
        return state


__all__ = ["BusTool"]
