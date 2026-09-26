"""
GridForge V2 — Canvas Graphics View
===================================

File:
    ui/canvas/graphics_view.py

Purpose
-------
Thin Qt viewport boundary for the GridForge SLD canvas.

Architectural role
------------------
GraphicsView is a Qt viewport boundary. Canvas services are composed
outside the view and injected into it.

It does not:
    - create Presentation controllers;
    - create ToolManager;
    - create InteractionManager;
    - create NavigationController;
    - own tool lifecycle;
    - perform electrical calculations;
    - modify Core state;
    - construct domain objects.

The Application layer is the explicit Core↔UI integration boundary.
GraphicsView does not bypass that boundary.

Author:
    Subhendu Mishra
"""

from __future__ import annotations

from typing import Any, Optional

from ui.core.qt import QGraphicsScene, QGraphicsView, Qt, Signal
from ui.canvas.interaction_manager import InteractionManager
from ui.canvas.navigation_controller import NavigationController


class GraphicsView(QGraphicsView):
    """Canonical GridForge Canvas viewport."""

    cursor_scene_position = Signal(object)

    def __init__(
        self,
        controller: Any,
        tool_manager: Any,
        *,
        scene: QGraphicsScene,
        interaction_manager: Optional[InteractionManager] = None,
        navigation_controller: Optional[NavigationController] = None,
        parent: Optional[Any] = None,
    ) -> None:
        if controller is None:
            raise ValueError("controller must not be None.")
        if tool_manager is None:
            raise ValueError("tool_manager must not be None.")
        if scene is None:
            raise ValueError("scene must not be None.")

        super().__init__(parent)
        self.controller = controller
        self.tool_manager = tool_manager
        self._scene = scene
        self._last_cursor_scene_position: tuple[float, float] | None = None
        self.interaction_manager = interaction_manager
        self.navigation_controller = navigation_controller

        if self._scene.parent() is None:
            self._scene.setParent(self)
        self.setScene(self._scene)
        # Canvas background is a fixed UI invariant: always render white.
        self.setBackgroundBrush(Qt.white)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def bind_services(
        self,
        *,
        interaction_manager: InteractionManager,
        navigation_controller: NavigationController,
    ) -> None:
        if interaction_manager is None:
            raise ValueError("interaction_manager must not be None.")
        if navigation_controller is None:
            raise ValueError("navigation_controller must not be None.")
        if self.interaction_manager is not None:
            raise RuntimeError("interaction_manager is already bound.")
        if self.navigation_controller is not None:
            raise RuntimeError("navigation_controller is already bound.")
        self.interaction_manager = interaction_manager
        self.navigation_controller = navigation_controller

    @property
    def graphics_scene(self) -> QGraphicsScene:
        return self._scene

    @property
    def last_cursor_scene_position(self) -> tuple[float, float] | None:
        return self._last_cursor_scene_position

    def mousePressEvent(self, event: Any) -> None:
        if self.interaction_manager is not None and self.interaction_manager.mouse_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        point = self.mapToScene(event.position().toPoint() if hasattr(event.position(), "toPoint") else event.pos())
        self._last_cursor_scene_position = (float(point.x()), float(point.y()))
        self.cursor_scene_position.emit(self._last_cursor_scene_position)
        if self.interaction_manager is not None and self.interaction_manager.mouse_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if self.interaction_manager is not None and self.interaction_manager.mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if self.interaction_manager is not None and self.interaction_manager.mouse_double_click(event):
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: Any) -> None:
        if self.navigation_controller is not None and self.navigation_controller.handle_wheel(event):
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: Any) -> None:
        if self.interaction_manager is not None and self.interaction_manager.key_press(event):
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: Any) -> None:
        if self.interaction_manager is not None and self.interaction_manager.key_release(event):
            return
        super().keyReleaseEvent(event)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)

    def dispose(self) -> None:
        self.interaction_manager = None
        self.navigation_controller = None
        self.controller = None
        self.tool_manager = None


__all__ = ["GraphicsView"]
