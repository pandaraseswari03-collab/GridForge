# ============================================================
# GridForge V2
# ============================================================
# File:
#     ui/tools/transformer_tool.py
#
# Purpose:
#     SLD transformer-placement interaction tool.
#
# Architectural Role:
#     TransformerTool captures placement intent in scene
#     coordinates and stops at the Application command boundary.
#     It does not mutate Core directly.
#
# IMPORTANT:
#     The current repository does not expose a confirmed
#     Core CreateTransformer command/factory. Therefore this
#     tool does NOT invent one and does NOT bypass CommandManager.
#
# Author:
#     Subhendu Mishra
# ============================================================

from __future__ import annotations

from typing import Any, Optional, Tuple

from .tool_base import ToolBase


class TransformerTool(ToolBase):
    """SLD transformer-placement interaction tool."""

    TOOL_ID = "transformer"

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
        """Return the stable transformer-tool identifier."""
        return self.TOOL_ID

    @property
    def name(self) -> str:
        """Return the user-facing transformer-tool name."""
        return "Transformer"

    @property
    def description(self) -> str:
        """Return the tool description."""
        return "Place a transformer on the SLD canvas."

    def on_activate(self) -> None:
        """Reset transient placement state."""
        self._clear_state()

    def on_deactivate(self) -> None:
        """Clear transient placement state."""
        self._clear_state()

    def on_mouse_press(self, event: Any) -> bool:
        """Capture a snapped scene-space transformer placement."""
        self._ensure_active()
        position = self._snap_position(event)
        if position is None:
            return False
        self._position = position
        self._preview_active = True
        return True

    def on_mouse_move(self, event: Any) -> bool:
        """Update the transient transformer preview position."""
        self._ensure_active()
        position = self._snap_position(event)
        if position is None:
            return False
        self._position = position
        self._preview_active = True
        return True

    def on_mouse_release(self, event: Any) -> bool:
        """Reject persistent creation until its Core command exists."""
        self._ensure_active()
        position = self._snap_position(event)
        if position is None:
            self._clear_state()
            return False
        self._position = position
        self._require_transformer_command_boundary()
        return False

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
        snap_system = self.get_snap_system()
        snap = getattr(snap_system, "snap", None)
        if not callable(snap):
            raise TypeError("SnapSystem must provide snap().")
        result = snap(scene_position, allow_grid=True, allow_object=True)
        position = getattr(result, "position", None)
        if position is None:
            return None
        return self._position_tuple(position)

    @staticmethod
    def _require_transformer_command_boundary() -> None:
        raise RuntimeError(
            "Transformer placement requires a confirmed Core "
            "transformer-creation command. No CreateTransformer "
            "command is currently exposed by the GridForge Core "
            "command API."
        )

    @staticmethod
    def _position_tuple(position: Any) -> Tuple[float, float]:
        if hasattr(position, "x") and hasattr(position, "y"):
            return float(position.x()), float(position.y())
        if isinstance(position, (tuple, list)) and len(position) >= 2:
            return float(position[0]), float(position[1])
        raise TypeError(
            "SnapResult.position must provide x/y coordinates "
            "or a two-element position."
        )

    @staticmethod
    def _is_escape_event(event: Any) -> bool:
        if event is None:
            return False
        key = getattr(event, "key", None)
        if callable(key):
            key = key()
        if isinstance(event, dict):
            key = event.get("key", key)
        return key in ("Escape", "escape", 0x01000000)

    def _clear_state(self) -> None:
        self._position = None
        self._preview_active = False

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        state.update(
            {
                "position": self._position,
                "preview_active": self._preview_active,
            }
        )
        return state


__all__ = [
    "TransformerTool",
]
