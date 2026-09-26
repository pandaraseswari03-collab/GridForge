# ============================================================
# File: core/application/services/sld_service.py
# GridForge V2 — Application SLD presentation service
# Author: Subhendu Mishra
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from typing import Any

from ..command import Command
from ..results import ApplicationResult
from ..transaction import Transaction


@dataclass(frozen=True, slots=True)
class SLDState:
    """Immutable snapshot of presentation-only SLD state."""
    nodes: tuple[dict[str, Any], ...] = ()
    connections: tuple[dict[str, Any], ...] = ()


class SLDService:
    """Application boundary for persistent SLD presentation state.

    The service performs presentation mutation only inside the Application
    transaction supplied by CommandManager. It never owns history or undo/redo.
    """

    COMMAND_TYPES = frozenset({
        "sld.set_node_position",
        "sld.set_node_presentation",
        "sld.add_node",
        "sld.remove_node",
        "sld.add_connection",
        "sld.remove_connection",
        "sld.set_connection_route",
        "sld.set_node_properties",
    })

    def __init__(
        self,
        document: Any,
        *,
        application: Any = None,
        symbol_presentation_factory: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self._document = None
        self._application = application
        self._symbol_presentation_factory = symbol_presentation_factory
        if application is not None:
            self.attach_application(application)
        self.bind_document(document)

    @property
    def document(self) -> Any:
        if self._document is None:
            raise RuntimeError("SLD service has no active document.")
        return self._document

    @property
    def is_bound(self) -> bool:
        return self._document is not None

    def bind_document(self, document: Any) -> None:
        """Bind only the Application-authoritative active presentation document."""
        if document is None:
            raise TypeError("SLDService requires an SLD document.")
        if self._application is not None:
            presentation = getattr(self._application, "presentation", None)
            if presentation is not document:
                raise RuntimeError(
                    "SLDService cannot bind a document that is not the "
                    "Application-authoritative active presentation."
                )
        self._document = document

    def attach_application(self, application: Any) -> None:
        """Attach the Application whose presentation state is authoritative."""
        if application is None:
            raise TypeError("application must not be None")
        self._application = application
        if self._document is not None:
            presentation = getattr(application, "presentation", None)
            if presentation is not self._document:
                raise RuntimeError(
                    "Existing SLD document does not match the Application presentation."
                )

    @property
    def application(self) -> Any:
        return self._application

    def detach_document(self) -> Any:
        """Detach the active document so closed projects cannot be mutated."""
        document = self._document
        self._document = None
        return document

    def supports(self, command: Command) -> bool:
        return command.command_type in self.COMMAND_TYPES

    def execute(self, command: Command, transaction: Transaction, *, context: Any = None) -> ApplicationResult:
        """Apply one SLD command inside the canonical Application transaction."""
        if not isinstance(command, Command):
            raise TypeError("command must be a Command")
        if not isinstance(transaction, Transaction):
            raise TypeError("transaction must be a Transaction")
        if not self.supports(command):
            raise ValueError(f"Unsupported SLD command: {command.command_type}")
        handler = {
            "sld.set_node_position": self._set_node_position,
            "sld.set_node_presentation": self._set_node_presentation,
            "sld.add_node": self._add_node,
            "sld.remove_node": self._remove_node,
            "sld.add_connection": self._add_connection,
            "sld.remove_connection": lambda cmd, tx: self._remove_connection(cmd, tx, context=context),
            "sld.set_connection_route": self._set_connection_route,
            "sld.set_node_properties": self._set_node_properties,
        }[command.command_type]
        return handler(command, transaction)

    def _set_node_position(self, command: Command, transaction: Transaction) -> ApplicationResult:
        p = command.payload
        node = self.document.model.get_node(p["node_id"])
        previous = node.position
        self.document.set_node_position(p["node_id"], float(p["x"]), float(p["y"]))
        transaction.record_undo(
            lambda node_id=p["node_id"], position=previous: self.document.set_node_position(node_id, *position)
        )
        return ApplicationResult.success_result(
            message="SLD node position updated.",
            metadata={"presentation_operation": "set_node_position", "node_id": p["node_id"]},
        )

    def _set_node_presentation(self, command: Command, transaction: Transaction) -> ApplicationResult:
        p = command.payload
        node = self.document.model.get_node(p["node_id"])
        self._require_engineer_owned_node(node)
        previous = None if node.presentation is None else node.presentation.to_dict()
        node.set_presentation(p["presentation"])
        self.document.mark_modified()
        if previous is None:
            transaction.record_undo(
                lambda node_id=p["node_id"]: self.document.model.get_node(node_id).clear_presentation()
            )
        else:
            transaction.record_undo(
                lambda node_id=p["node_id"], snapshot=previous: self.document.model.get_node(node_id).set_presentation(snapshot)
            )
        return ApplicationResult.success_result(
            message="SLD node presentation updated.",
            metadata={"presentation_operation": "set_node_presentation", "node_id": p["node_id"]},
        )

    def _add_node(self, command: Command, transaction: Transaction) -> ApplicationResult:
        p = command.payload
        equipment_id = p.get("equipment_id")
        if equipment_id is not None:
            self._validate_equipment_reference(str(equipment_id))
        presentation_owner = str(p.get("presentation_owner", "engineer"))
        projection_source = p.get("projection_source")
        if presentation_owner not in {"engineer", "projection"}:
            raise ValueError("presentation_owner must be 'engineer' or 'projection'.")
        if projection_source is not None and presentation_owner != "projection":
            raise ValueError("projection_source requires presentation_owner='projection'.")
        properties = {"presentation_owner": presentation_owner}
        element_type = p.get("element_type")
        if element_type is not None:
            properties["element_type"] = str(element_type)
        if projection_source is not None:
            properties["projection_source"] = str(projection_source)
        presentation_properties = p.get("presentation_properties", {})
        if not isinstance(presentation_properties, Mapping):
            raise TypeError("presentation_properties must be a mapping")
        properties.update(dict(presentation_properties))

        presentation = p.get("presentation")
        if presentation is None and self._symbol_presentation_factory is not None:
            if not isinstance(element_type, str) or not element_type.strip():
                raise ValueError(
                    "SLD node creation requires element_type when a default "
                    "symbol presentation factory is configured."
                )
            presentation = self._symbol_presentation_factory(element_type)

        self.document.model.create_node(
            node_id=p["node_id"],
            equipment_id=equipment_id,
            x=float(p["x"]),
            y=float(p["y"]),
            presentation=presentation,
            properties=properties,
        )
        self.document.mark_modified()
        transaction.record_undo(lambda node_id=p["node_id"]: self.document.model.remove_node(node_id))
        return ApplicationResult.success_result(
            message="SLD node added.",
            metadata={"presentation_operation": "add_node", "node_id": p["node_id"]},
        )

    def _validate_equipment_reference(self, equipment_id: str) -> None:
        """Validate an authored SLD equipment association through Application read state."""
        if self._application is None:
            raise RuntimeError("SLDService requires an Application to validate equipment references.")
        read_model = self._application.read_network()
        if any(element.object_id == equipment_id for element in read_model.elements):
            return
        protection = self._application.read_protection()
        if any(element.object_id == equipment_id for element in protection.elements):
            return
        raise ValueError(
            f"SLD node equipment reference {equipment_id!r} does not resolve to current Application read state."
        )

    def reconcile_element_update(
        self,
        *,
        equipment_id: str,
        element_type: str,
        read_model: Any,
        transaction: Transaction,
    ) -> None:
        """Reconcile authoritative semantic fields while preserving presentation overrides.

        This is intentionally a service operation, not a second command/history
        mechanism. It is invoked by the Application pre-commit hook inside the
        transaction opened for the originating Core command.
        """
        if not isinstance(equipment_id, str) or not equipment_id:
            raise ValueError("equipment_id must be a non-empty string")
        node = self.document.model.get_node_by_equipment_id_optional(equipment_id)
        if node is None:
            return
        previous = node.to_dict()
        attributes = dict(getattr(read_model, "attributes", {}) or {})
        labels = dict(getattr(read_model, "labels", {}) or {})
        connectivity = tuple(getattr(read_model, "connectivity_refs", ()) or ())
        node.properties.update({
            "element_type": str(element_type),
            "labels": labels,
            "attributes": attributes,
            "terminal_ids": connectivity,
            "terminal_connectivity": tuple(attributes.get("terminal_connectivity", ())),
            "lifecycle_state": "BOUND",
        })
        node.equipment_id = equipment_id
        transaction.record_undo(
            lambda snapshot=previous: self._restore_node_snapshot(snapshot)
        )
        self.document.mark_modified()

    def reconcile_element_delete(
        self,
        *,
        equipment_id: str,
        transaction: Transaction,
    ) -> str:
        """Apply the explicit BOUND/ORPHANED/REMOVED presentation policy.

        Projection-owned bindings are REMOVED with their projection-owned
        connections. Engineer-authored presentation is retained as ORPHANED;
        semantic binding is cleared while geometry, symbols, labels, and manual
        route state remain intact.
        """
        node = self.document.model.get_node_by_equipment_id_optional(equipment_id)
        if node is None:
            return "REMOVED"
        snapshot = node.to_dict()
        owner = node.properties.get("presentation_owner")
        source = node.properties.get("projection_source")
        attached = tuple(
            connection for connection in self.document.model.connections
            if connection.source_node_id == node.node_id
            or connection.target_node_id == node.node_id
        )
        connection_snapshots = tuple(connection.to_dict() for connection in attached)
        if owner == "projection" and source in {"application_read_model", "protection_read_model"}:
            self.document.model.remove_node(node.node_id)
            self.document.mark_modified()

            def restore_projection(snapshot=snapshot, connection_snapshots=connection_snapshots) -> None:
                self._restore_node_snapshot(snapshot)
                for item in connection_snapshots:
                    if self.document.model.get_connection_optional(item["connection_id"]) is None:
                        self._restore_connection_snapshot(item)

            transaction.record_undo(restore_projection)
            return "REMOVED"

        attached = tuple(
            connection for connection in self.document.model.connections
            if connection.source_node_id == node.node_id
            or connection.target_node_id == node.node_id
        )
        for connection in attached:
            if connection.properties.get("presentation_owner") == "projection":
                self.document.model.remove_connection(connection.connection_id)
            else:
                connection.source_endpoint = None if connection.source_node_id == node.node_id else connection.source_endpoint
                connection.target_endpoint = None if connection.target_node_id == node.node_id else connection.target_endpoint
                connection.properties.pop("projection_source", None)
                connection.properties["lifecycle_state"] = "ORPHANED"
                connection.properties["presentation_owner"] = "engineer"

        node.equipment_id = None
        node.properties.pop("projection_source", None)
        node.properties["lifecycle_state"] = "ORPHANED"
        node.properties["orphaned_equipment_id"] = equipment_id
        node.properties["presentation_owner"] = "engineer"
        self.document.mark_modified()

        def restore(snapshot=snapshot, connection_snapshots=connection_snapshots) -> None:
            self._restore_node_snapshot(snapshot)
            for connection in tuple(self.document.model.connections):
                if connection.connection_id in {item["connection_id"] for item in connection_snapshots}:
                    self.document.model.remove_connection(connection.connection_id)
            for item in connection_snapshots:
                self.document.model.create_connection(
                    connection_id=item["connection_id"],
                    source_node_id=item["source_node_id"],
                    target_node_id=item["target_node_id"],
                    source_endpoint=item.get("source_endpoint"),
                    target_endpoint=item.get("target_endpoint"),
                    route=item.get("route"),
                    properties=item.get("properties", {}),
                )
            self.document.mark_modified()

        transaction.record_undo(restore)
        return "ORPHANED"

    def reconcile_connection_delete(
        self,
        *,
        connection_id: str,
        transaction: Transaction,
    ) -> str:
        """Remove or orphan an SLD connection in the originating transaction."""
        connection = self.document.model.get_connection_optional(connection_id)
        if connection is None:
            return "REMOVED"
        snapshot = connection.to_dict()
        owner = connection.properties.get("presentation_owner")
        if owner == "projection":
            self.document.model.remove_connection(connection_id)
            self.document.mark_modified()
            transaction.record_undo(
                lambda snapshot=snapshot: self._restore_connection_snapshot(snapshot)
            )
            return "REMOVED"
        connection.source_endpoint = None
        connection.target_endpoint = None
        connection.properties.pop("projection_source", None)
        connection.properties["presentation_owner"] = "engineer"
        connection.properties["lifecycle_state"] = "ORPHANED"
        self.document.mark_modified()
        transaction.record_undo(
            lambda snapshot=snapshot: self._restore_connection_snapshot(snapshot)
        )
        return "ORPHANED"

    def _restore_node_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        self.document.model.create_node(
            node_id=snapshot["node_id"],
            equipment_id=snapshot.get("equipment_id"),
            x=snapshot.get("x", 0.0),
            y=snapshot.get("y", 0.0),
            presentation=snapshot.get("presentation"),
            properties=snapshot.get("properties", {}),
        )
        for item in snapshot.get("connections", ()):
            self._restore_connection_snapshot(item)
        self.document.mark_modified()

    def _restore_connection_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        self.document.model.create_connection(
            connection_id=snapshot["connection_id"],
            source_node_id=snapshot["source_node_id"],
            target_node_id=snapshot["target_node_id"],
            source_endpoint=snapshot.get("source_endpoint"),
            target_endpoint=snapshot.get("target_endpoint"),
            route=snapshot.get("route"),
            properties=snapshot.get("properties", {}),
        )
        self.document.mark_modified()

    def _remove_node(self, command: Command, transaction: Transaction) -> ApplicationResult:
        node_id = command.payload["node_id"]
        node = self.document.model.get_node(node_id)
        projection_source = command.payload.get("projection_source")
        if projection_source is None:
            self._require_engineer_owned_node(node)
        else:
            if node.properties.get("projection_source") != projection_source:
                raise ValueError("SLD node projection ownership does not match the removal command.")
        node_snapshot = node.to_dict()
        connection_snapshots = tuple(
            connection.to_dict()
            for connection in self.document.model.connections
            if connection.source_node_id == node_id or connection.target_node_id == node_id
        )
        self.document.model.remove_node(node_id)
        self.document.mark_modified()

        def restore() -> None:
            self.document.model.create_node(
                node_id=node_snapshot["node_id"],
                equipment_id=node_snapshot.get("equipment_id"),
                x=node_snapshot.get("x", 0.0),
                y=node_snapshot.get("y", 0.0),
                presentation=node_snapshot.get("presentation"),
                properties=node_snapshot.get("properties", {}),
            )
            for snapshot in connection_snapshots:
                self.document.model.create_connection(
                    connection_id=snapshot["connection_id"],
                    source_node_id=snapshot["source_node_id"],
                    target_node_id=snapshot["target_node_id"],
                    source_endpoint=snapshot.get("source_endpoint"),
                    target_endpoint=snapshot.get("target_endpoint"),
                    route=snapshot.get("route"),
                    properties=snapshot.get("properties", {}),
                )

        transaction.record_undo(restore)
        return ApplicationResult.success_result(
            message="SLD node removed.",
            metadata={"presentation_operation": "remove_node", "node_id": node_id},
        )

    def _add_connection(self, command: Command, transaction: Transaction) -> ApplicationResult:
        p = command.payload
        source_endpoint = p.get("source_endpoint")
        target_endpoint = p.get("target_endpoint")
        route = p.get("route")
        presentation_owner = str(p.get("presentation_owner", "engineer"))
        projection_source = p.get("projection_source")
        if presentation_owner not in {"engineer", "projection"}:
            raise ValueError("presentation_owner must be 'engineer' or 'projection'.")
        if projection_source is not None and presentation_owner != "projection":
            raise ValueError("projection_source requires presentation_owner='projection'.")
        properties = {"presentation_owner": presentation_owner}
        if projection_source is not None:
            properties["projection_source"] = str(projection_source)
        self.document.model.create_connection(
            connection_id=p["connection_id"],
            source_node_id=p["source_node_id"],
            target_node_id=p["target_node_id"],
            source_endpoint=source_endpoint,
            target_endpoint=target_endpoint,
            route=route,
            properties=properties,
        )
        self.document.mark_modified()
        transaction.record_undo(lambda connection_id=p["connection_id"]: self.document.model.remove_connection(connection_id))
        return ApplicationResult.success_result(
            message="SLD connection added.",
            metadata={"presentation_operation": "add_connection", "connection_id": p["connection_id"]},
        )

    def _set_node_properties(self, command: Command, transaction: Transaction) -> ApplicationResult:
        p = command.payload
        node = self.document.model.get_node(p["node_id"])
        self._require_engineer_owned_node(node)
        previous = dict(node.properties)
        properties = p["properties"]
        if not isinstance(properties, Mapping):
            raise TypeError("properties must be a mapping")
        node.properties.update(dict(properties))
        self.document.mark_modified()
        transaction.record_undo(lambda node=node, snapshot=previous: (node.properties.clear(), node.properties.update(snapshot)))
        return ApplicationResult.success_result(
            message="SLD node presentation properties updated.",
            metadata={"presentation_operation": "set_node_properties", "node_id": p["node_id"]},
        )

    def _set_connection_route(self, command: Command, transaction: Transaction) -> ApplicationResult:
        p = command.payload
        connection = self.document.model.get_connection(p["connection_id"])
        owner = connection.properties.get("presentation_owner")
        if owner not in (None, "engineer", "projection"):
            raise ValueError("SLD connection ownership is unknown; route edit is rejected.")
        previous = connection.route
        previous_properties = dict(connection.properties)
        updated = self.document.model.get_connection(p["connection_id"]).route.__class__.from_dict(p["route"])
        if updated.ownership != "engineer":
            updated = updated.__class__(routing_mode=updated.routing_mode, ownership="engineer", points=updated.points)
        connection.route = updated
        connection.properties.pop("projection_source", None)
        connection.properties["presentation_owner"] = "engineer"
        self.document.mark_modified()
        transaction.record_undo(lambda connection=connection, route=previous, properties=previous_properties: (setattr(connection, "route", route), connection.properties.clear(), connection.properties.update(properties)))
        return ApplicationResult.success_result(
            message="SLD connection route updated.",
            metadata={"presentation_operation": "set_connection_route", "connection_id": p["connection_id"]},
        )

    @staticmethod
    def _require_engineer_owned_node(node: Any) -> None:
        source = node.properties.get("projection_source")
        owner = node.properties.get("presentation_owner")
        if source in {"application_read_model", "protection_read_model"}:
            raise ValueError(
                "Projection-owned SLD nodes cannot be removed through "
                "engineer-owned presentation commands."
            )
        if source is not None or owner not in (None, "engineer"):
            raise ValueError(
                "SLD node ownership is unknown or invalid; removal is rejected."
            )

    @staticmethod
    def _require_engineer_owned_connection(connection: Any) -> None:
        source = connection.properties.get("projection_source")
        owner = connection.properties.get("presentation_owner")
        if source in {"application_read_model", "protection_read_model"}:
            raise ValueError(
                "Projection-owned SLD connections cannot be removed through "
                "engineer-owned presentation commands."
            )
        if owner != "engineer":
            raise ValueError(
                "SLD connection ownership is unknown; removal is rejected."
            )

    def _remove_connection(self, command: Command, transaction: Transaction, *, context: Any = None) -> ApplicationResult:
        connection_id = command.payload["connection_id"]
        connection = self.document.model.get_connection(connection_id)

        # Projection-owned Simple Wire deletion is an Application command
        # flowing through the same transaction. The SLD connection is only a
        # projection and never becomes the authority for engineering removal.
        if (
            connection.properties.get("projection_source") == "application_read_model"
            and connection.properties.get("connection_kind") == "SIMPLE_WIRE"
        ):
            if context is None:
                raise RuntimeError("Simple Wire projection deletion requires the Application command context.")
            from ..commands.simple_wire_commands import RemoveSimpleWireConnectionCommand
            from .simple_wire_service import SimpleWireConnectionService

            domain_result = SimpleWireConnectionService().execute(
                RemoveSimpleWireConnectionCommand(connection_id=connection_id),
                context,
                transaction,
            )
            snapshot = connection.to_dict()
            self.document.model.remove_connection(connection_id)
            self.document.mark_modified()

            def restore_projection() -> None:
                self.document.model.create_connection(
                    connection_id=snapshot["connection_id"],
                    source_node_id=snapshot["source_node_id"],
                    target_node_id=snapshot["target_node_id"],
                    source_endpoint=snapshot.get("source_endpoint"),
                    target_endpoint=snapshot.get("target_endpoint"),
                    route=snapshot.get("route"),
                    properties=snapshot.get("properties", {}),
                )

            transaction.record_undo(restore_projection)
            return ApplicationResult.success_result(
                message=f"Simple Wire {connection_id} removed through the Application boundary.",
                metadata={
                    **dict(domain_result.metadata),
                    "presentation_operation": "remove_projection_connection",
                },
            )

        self._require_engineer_owned_connection(connection)
        snapshot = connection.to_dict()
        self.document.model.remove_connection(connection_id)
        self.document.mark_modified()

        def restore() -> None:
            self.document.model.create_connection(
                connection_id=snapshot["connection_id"],
                source_node_id=snapshot["source_node_id"],
                target_node_id=snapshot["target_node_id"],
                source_endpoint=snapshot.get("source_endpoint"),
                target_endpoint=snapshot.get("target_endpoint"),
                route=snapshot.get("route"),
                properties=snapshot.get("properties", {}),
            )

        transaction.record_undo(restore)
        return ApplicationResult.success_result(
            message="SLD connection removed.",
            metadata={"presentation_operation": "remove_connection", "connection_id": connection_id},
        )


__all__ = ["SLDService", "SLDState"]
