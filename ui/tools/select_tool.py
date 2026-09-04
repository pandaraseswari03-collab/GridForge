# ============================================================
# GridForge V2
# ============================================================
# File:
#     ui/tools/select_tool.py
#
# Purpose:
#     Selection interaction tool for the GridForge UI.
#
# Architectural Role:
#     SelectTool translates pointer interaction into requests to
#     SelectionManager. It never owns rendering infrastructure.
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
        return "Select GridForge UI objects."

    def on_activate(self) -> None:
        self._clear_pointer_state()

    def on_deactivate(self) -> None:
        self._clear_pointer_state()

    def on_mouse_press(self, event: Any) -> bool:
        self._ensure_active()
        object_id = self._event_object_id(event)
        position = self.event_position(event)
        modifiers = self._event_modifiers(event)
        self._pressed_object_id = object_id
        self._pressed_position = position
        self._dragging = False
        if object_id is None:
            self._handle_empty_canvas_click(modifiers)
            return True
        self._handle_object_click(object_id, modifiers)
        return True

    def on_mouse_move(self, event: Any) -> bool:
        self._ensure_active()
        if self._pressed_position is None:
            return False
        position = self.event_position(event)
        if position != self._pressed_position:
            self._dragging = True
        return self._dragging

    def on_mouse_release(self, event: Any) -> bool:
        self._ensure_active()
        handled = self._pressed_object_id is not None or self._pressed_position is not None or self._dragging
        self._clear_pointer_state()
        return handled

    def on_mouse_double_click(self, event: Any) -> bool:
        self._ensure_active()
        object_id = self._event_object_id(event)
        if object_id is None:
            return False
        self._handle_object_click(object_id, self._event_modifiers(event))
        return True

    def on_key_press(self, event: Any) -> bool:
        self._ensure_active()
        return False

    def on_cancel(self) -> bool:
        self._ensure_active()
        had_state = self._pressed_object_id is not None or self._pressed_position is not None or self._dragging
        self._clear_pointer_state()
        return had_state

    def on_reset(self) -> None:
        self._ensure_active()
        self._clear_pointer_state()

    def _handle_object_click(self, object_id: Any, modifiers: int) -> None:
        manager = self.get_selection_manager()
        if self._has_toggle_modifier(modifiers):
            self._toggle_selection(manager, object_id)
            return
        if self._has_additive_modifier(modifiers):
            self._add_to_selection(manager, object_id)
            return
        self._select_single(manager, object_id)

    def _handle_empty_canvas_click(self, modifiers: int) -> None:
        if self._has_additive_modifier(modifiers) or self._has_toggle_modifier(modifiers):
            return
        manager = self.get_selection_manager()
        clear = getattr(manager, "clear", None)
        if not callable(clear):
            raise TypeError("SelectionManager must provide clear().")
        clear()

    @staticmethod
    def _select_single(manager: Any, object_id: Any) -> Any:
        select_single = getattr(manager, "select_single", None)
        if not callable(select_single):
            raise TypeError("SelectionManager must provide select_single().")
        return select_single(object_id)

    @staticmethod
    def _add_to_selection(manager: Any, object_id: Any) -> Any:
        add_to_selection = getattr(manager, "add_to_selection", None)
        if not callable(add_to_selection):
            raise TypeError("SelectionManager must provide add_to_selection().")
        return add_to_selection(object_id)

    @staticmethod
    def _toggle_selection(manager: Any, object_id: Any) -> Any:
        toggle_selection = getattr(manager, "toggle_selection", None)
        if not callable(toggle_selection):
            raise TypeError("SelectionManager must provide toggle_selection().")
        return toggle_selection(object_id)

    @classmethod
    def _has_additive_modifier(cls, modifiers: int) -> bool:
        return bool(modifiers & (cls.SHIFT_MODIFIER | cls.META_MODIFIER))

    @classmethod
    def _has_toggle_modifier(cls, modifiers: int) -> bool:
        return bool(modifiers & (cls.CTRL_MODIFIER | cls.META_MODIFIER))

    @staticmethod
    def _event_object_id(event: Any) -> Any:
        if event is None:
            return None
        object_id = getattr(event, "object_id", None)
        if object_id is not None:
            return object_id
        if isinstance(event, dict):
            return event.get("object_id")
        return None

    @staticmethod
    def _event_modifiers(event: Any) -> int:
        if event is None:
            return 0
        modifiers = getattr(event, "modifiers", 0)
        if callable(modifiers):
            modifiers = modifiers()
        if isinstance(event, dict):
            modifiers = event.get("modifiers", modifiers)
        if modifiers is None:
            return 0
        try:
            return int(modifiers)
        except (TypeError, ValueError) as exc:
            raise TypeError("event modifiers must be integer-compatible.") from exc

    def _clear_pointer_state(self) -> None:
        self._pressed_object_id = None
        self._pressed_position = None
        self._dragging = False

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        state.update({"pressed_object_id": self._pressed_object_id, "pressed_position": self._pressed_position, "dragging": self._dragging})
        return state


__all__ = ["SelectTool"]
