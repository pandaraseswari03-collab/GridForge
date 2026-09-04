# ============================================================
# GridForge V2
# ============================================================
# File:
#     ui/tools/select_tool.py
# ============================================================

from __future__ import annotations

from typing import Any, Optional, Tuple

from .tool_base import ToolBase


class SelectTool(ToolBase):
    """Default GridForge object-selection tool."""

    TOOL_ID = "select"
    SHIFT_MODIFIER = 0x02000000
    CTRL_MODIFIER = 0x04000000
    META_MODIFIER = 0x10000000

    def __init__(self, command_manager: Any, selection_manager: Any, snap_system: Any) -> None:
        super().__init__(command_manager=command_manager, selection_manager=selection_manager, snap_system=snap_system)
        self._pressed_object_id: Any = None
        self._pressed_position: Optional[Tuple[float, float]] = None
        self._dragging = False

    @property
    def tool_id(self) -> str:
        return self.TOOL_ID

    @property
    def name(self) -> str:
        return "Select"

    @property
    def description(self) -> str:
        return "Select objects on the SLD canvas."

    def on_activate(self) -> None:
        self._clear_state()

    def on_deactivate(self) -> None:
        self._clear_state()

    def on_mouse_press(self, event: Any) -> bool:
        self._ensure_active()
        manager = self.get_selection_manager()
        object_id = self._object_id(event)
        if object_id is None:
            manager.clear()
        elif self._modifier(event, self.CTRL_MODIFIER) or self._modifier(event, self.META_MODIFIER):
            self._toggle_selection(manager, object_id)
        elif self._modifier(event, self.SHIFT_MODIFIER):
            self._add_to_selection(manager, object_id)
        else:
            self._select_single(manager, object_id)
        return True

    def on_mouse_move(self, event: Any) -> bool:
        self._ensure_active()
        return False

    def on_mouse_release(self, event: Any) -> bool:
        self._ensure_active()
        return False

    def on_mouse_double_click(self, event: Any) -> bool:
        return self.on_mouse_press(event)

    def on_key_press(self, event: Any) -> bool:
        self._ensure_active()
        return False

    def on_cancel(self) -> bool:
        self._ensure_active()
        self._clear_state()
        return False

    def on_reset(self) -> None:
        self._clear_state()

    @staticmethod
    def _object_id(event: Any) -> Any:
        if isinstance(event, dict):
            return event.get("object_id", event.get("item_id"))
        object_id = getattr(event, "object_id", None)
        if object_id is not None:
            return object_id() if callable(object_id) else object_id
        return getattr(event, "item_id", None)

    @staticmethod
    def _modifier(event: Any, modifier: int) -> bool:
        modifiers = getattr(event, "modifiers", None)
        if callable(modifiers):
            modifiers = modifiers()
        if isinstance(event, dict):
            modifiers = event.get("modifiers", modifiers)
        if isinstance(modifiers, int):
            return bool(modifiers & modifier)
        if isinstance(modifiers, (set, tuple, list)):
            return modifier in modifiers
        return False

    @staticmethod
    def _select_single(manager: Any, object_id: Any) -> Any:
        select_single = getattr(manager, "select_single", None)
        if not callable(select_single):
            raise TypeError("SelectionManager must provide select_single().")
        return select_single(object_id)

    @staticmethod
    def _add_to_selection(manager: Any, object_id: Any) -> Any:
        add = getattr(manager, "add_to_selection", None)
        if not callable(add):
            raise TypeError("SelectionManager must provide add_to_selection().")
        return add(object_id)

    @staticmethod
    def _toggle_selection(manager: Any, object_id: Any) -> Any:
        toggle = getattr(manager, "toggle_selection", None)
        if not callable(toggle):
            raise TypeError("SelectionManager must provide toggle_selection().")
        return toggle(object_id)

    def _clear_state(self) -> None:
        self._pressed_object_id = None
        self._pressed_position = None
        self._dragging = False


__all__ = ["SelectTool"]
