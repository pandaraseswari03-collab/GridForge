# ============================================================
# File: core/application/commands/sld_commands.py
# GridForge V2 — Immutable SLD presentation commands
# Author: Subhendu Mishra
# ============================================================

from __future__ import annotations

from uuid import UUID, uuid4

from ..command import Command


SET_SLD_NODE_POSITION = "sld.set_node_position"
ADD_SLD_NODE = "sld.add_node"
REMOVE_SLD_NODE = "sld.remove_node"
SET_SLD_NODE_PRESENTATION = "sld.set_node_presentation"
ADD_SLD_CONNECTION = "sld.add_connection"
REMOVE_SLD_CONNECTION = "sld.remove_connection"
SET_SLD_CONNECTION_ROUTE = "sld.set_connection_route"
SET_SLD_NODE_PROPERTIES = "sld.set_node_properties"


class SetSLDNodePositionCommand(Command):
    def __init__(self, *, node_id: str, x: float, y: float,
                 command_id: UUID | None = None, correlation_id: UUID | None = None,
                 causation_id: UUID | None = None) -> None:
        super().__init__(command_type=SET_SLD_NODE_POSITION,
                         payload={"node_id": node_id, "x": float(x), "y": float(y)},
                         command_id=command_id or uuid4(), correlation_id=correlation_id, causation_id=causation_id)


class AddSLDNodeCommand(Command):
    def __init__(self, *, node_id: str, equipment_id: str | None = None,
                 x: float = 0.0, y: float = 0.0,
                 presentation_owner: str = "engineer",
                 projection_source: str | None = None,
                 element_type: str | None = None,
                 presentation: dict | None = None,
                 presentation_properties: dict | None = None,
                 command_id: UUID | None = None, correlation_id: UUID | None = None,
                 causation_id: UUID | None = None) -> None:
        super().__init__(
            command_type=ADD_SLD_NODE,
            payload={
                "node_id": node_id,
                "equipment_id": equipment_id,
                "x": float(x),
                "y": float(y),
                "presentation_owner": presentation_owner,
                "projection_source": projection_source,
                "element_type": element_type,
                "presentation": None if presentation is None else dict(presentation),
                "presentation_properties": {} if presentation_properties is None else dict(presentation_properties),
            },
            command_id=command_id or uuid4(),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )


class SetSLDNodePresentationCommand(Command):
    def __init__(
        self,
        *,
        node_id: str,
        presentation: dict,
        command_id: UUID | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        if not isinstance(presentation, dict):
            raise TypeError("presentation must be a dictionary")
        super().__init__(
            command_type=SET_SLD_NODE_PRESENTATION,
            payload={"node_id": node_id, "presentation": dict(presentation)},
            command_id=command_id or uuid4(),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )


class RemoveSLDNodeCommand(Command):
    def __init__(self, *, node_id: str, projection_source: str | None = None,
                 command_id: UUID | None = None,
                 correlation_id: UUID | None = None, causation_id: UUID | None = None) -> None:
        super().__init__(
            command_type=REMOVE_SLD_NODE,
            payload={"node_id": node_id, "projection_source": projection_source},
            command_id=command_id or uuid4(),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )


class AddSLDConnectionCommand(Command):
    """Create one persistent SLD connection with explicit ownership contract."""

    def __init__(
        self,
        *,
        connection_id: str,
        source_node_id: str,
        target_node_id: str,
        source_endpoint: dict | None = None,
        target_endpoint: dict | None = None,
        route: dict | None = None,
        connection_kind: str | None = None,
        presentation_owner: str = "engineer",
        projection_source: str | None = None,
        command_id: UUID | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        if presentation_owner not in {"engineer", "projection"}:
            raise ValueError("presentation_owner must be 'engineer' or 'projection'.")
        if projection_source is not None and presentation_owner != "projection":
            raise ValueError("projection_source requires presentation_owner='projection'.")
        super().__init__(
            command_type=ADD_SLD_CONNECTION,
            payload={
                "connection_id": connection_id,
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "source_endpoint": None if source_endpoint is None else dict(source_endpoint),
                "target_endpoint": None if target_endpoint is None else dict(target_endpoint),
                "route": None if route is None else dict(route),
                "connection_kind": connection_kind,
                "presentation_owner": presentation_owner,
                "projection_source": projection_source,
            },
            command_id=command_id or uuid4(),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

class SetSLDNodePropertiesCommand(Command):
    def __init__(self, *, node_id: str, properties: dict,
                 command_id: UUID | None = None, correlation_id: UUID | None = None,
                 causation_id: UUID | None = None) -> None:
        if not isinstance(properties, dict):
            raise TypeError("properties must be a dictionary")
        super().__init__(command_type=SET_SLD_NODE_PROPERTIES,
                         payload={"node_id": node_id, "properties": dict(properties)},
                         command_id=command_id or uuid4(), correlation_id=correlation_id, causation_id=causation_id)


class SetSLDConnectionRouteCommand(Command):
    def __init__(self, *, connection_id: str, route: dict,
                 command_id: UUID | None = None, correlation_id: UUID | None = None,
                 causation_id: UUID | None = None) -> None:
        if not isinstance(route, dict):
            raise TypeError("route must be a dictionary")
        super().__init__(command_type=SET_SLD_CONNECTION_ROUTE,
                         payload={"connection_id": connection_id, "route": dict(route)},
                         command_id=command_id or uuid4(), correlation_id=correlation_id, causation_id=causation_id)


class RemoveSLDConnectionCommand(Command):
    def __init__(self, *, connection_id: str, command_id: UUID | None = None,
                 correlation_id: UUID | None = None, causation_id: UUID | None = None) -> None:
        super().__init__(command_type=REMOVE_SLD_CONNECTION, payload={"connection_id": connection_id},
                         command_id=command_id or uuid4(), correlation_id=correlation_id, causation_id=causation_id)


__all__ = [
    "SET_SLD_NODE_POSITION", "ADD_SLD_NODE", "REMOVE_SLD_NODE", "SET_SLD_NODE_PRESENTATION",
    "ADD_SLD_CONNECTION", "REMOVE_SLD_CONNECTION", "SET_SLD_CONNECTION_ROUTE", "SET_SLD_NODE_PROPERTIES",
    "SetSLDNodePositionCommand", "AddSLDNodeCommand", "SetSLDNodePresentationCommand", "RemoveSLDNodeCommand",
    "AddSLDConnectionCommand", "SetSLDConnectionRouteCommand", "SetSLDNodePropertiesCommand", "RemoveSLDConnectionCommand",
]
