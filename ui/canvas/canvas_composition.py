"""GridForge V2 application-owned Canvas composition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ui.canvas.coordinate_system import CoordinateSystem
from ui.canvas.grid_scene import GridScene
from ui.canvas.grid_system import GridSystem
from ui.canvas.graphics_view import GraphicsView
from ui.canvas.interaction_manager import InteractionManager
from ui.canvas.navigation_controller import NavigationController
from ui.canvas.preview_layer import PreviewLayer
from ui.core.controller import Controller
from ui.core.line_creation_parameters import LineCreationParameters
from ui.core.qt import QWidget
from ui.core.selection_manager import SelectionManager
from ui.core.snap_system import SnapSystem
from ui.core.tool_manager import ToolManager
from ui.tools.default_tool_registry import create_default_tool_factories


@dataclass(frozen=True)
class CanvasComposition:
    """Fully composed Canvas viewport and interaction services."""

    view: GraphicsView
    scene: GridScene
    selection_manager: SelectionManager
    grid_system: GridSystem
    interaction_manager: InteractionManager
    navigation_controller: NavigationController
    coordinate_system: CoordinateSystem
    snap_system: SnapSystem
    preview_layer: PreviewLayer

    @property
    def widget(self) -> QWidget:
        return self.view


class CanvasComposer:
    """Application-level constructor for the Canvas service graph."""

    def compose(
        self,
        *,
        controller: Controller,
        tool_manager: ToolManager,
        command_manager: Any,
        line_creation_parameters: LineCreationParameters | None = None,
        parent: Optional[QWidget] = None,
    ) -> CanvasComposition:
        """Construct and wire one complete Canvas service graph."""
        if controller is None:
            raise ValueError("controller must not be None.")
        if tool_manager is None:
            raise ValueError("tool_manager must not be None.")
        if command_manager is None:
            raise ValueError("command_manager must not be None.")

        # Selection is UI-Core interaction state. Controller is deliberately
        # not the selection authority.
        selection_manager = SelectionManager()
        grid_system = GridSystem()
        scene = GridScene()

        view = GraphicsView(
            controller=controller,
            tool_manager=tool_manager,
            scene=scene,
            parent=parent,
        )

        coordinate_system = CoordinateSystem(
            view=view,
            grid_system=grid_system,
        )
        snap_system = SnapSystem(
            controller=controller,
            grid_system=grid_system,
            scene=scene,
        )
        preview_layer = PreviewLayer(scene=scene)
        interaction_manager = InteractionManager(
            view=view,
            controller=controller,
            tool_manager=tool_manager,
            coordinate_system=coordinate_system,
            snap_system=snap_system,
            preview_layer=preview_layer,
            selection_manager=selection_manager,
        )
        navigation_controller = NavigationController(view=view)

        view.bind_services(
            interaction_manager=interaction_manager,
            navigation_controller=navigation_controller,
        )

        selection_manager.set_scene(scene)

        tool_manager.register_tools(
            create_default_tool_factories(
                controller=controller,
                command_manager=command_manager,
                selection_manager=selection_manager,
                snap_system=snap_system,
                line_creation_parameters=line_creation_parameters,
            )
        )

        return CanvasComposition(
            view=view,
            scene=scene,
            selection_manager=selection_manager,
            grid_system=grid_system,
            interaction_manager=interaction_manager,
            navigation_controller=navigation_controller,
            coordinate_system=coordinate_system,
            snap_system=snap_system,
            preview_layer=preview_layer,
        )


__all__ = ["CanvasComposition", "CanvasComposer"]
