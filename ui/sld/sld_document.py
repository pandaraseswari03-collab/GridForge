# ============================================================
# GridForge V2
# ============================================================
# File: ui/sld/sld_document.py
# Purpose: SLD document lifecycle and structural model ownership.
# Author: Subhendu Mishra
# ============================================================
"""Presentation-owned SLD document.

SLDDocument owns editable SLD document structure, including persistent
presentation geometry. It never owns authoritative electrical truth.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Mapping, Optional

from ui.workspace.document import Document

from .sld_model import SLDModel
from ui.equipment.symbol.symbol_base import SymbolBase


class SLDDocument(Document):
    """Logical SLD document belonging to a Workspace Project.

    SLD_SCHEMA versions the persisted SLD representation independently from
    the enclosing GridForge project schema.
    """

    DOCUMENT_TYPE = "sld"
    SLD_SCHEMA = 2

    def __init__(
        self,
        document_id: str,
        name: str = "Untitled SLD",
        model: Optional[SLDModel] = None,
        *,
        project_id: str | None = None,
        default_symbol_presentation_factory: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            document_id=document_id,
            document_type=self.DOCUMENT_TYPE,
            name=name,
            project_id=project_id,
        )
        self._model = model if model is not None else SLDModel()
        self._default_symbol_presentation_factory = default_symbol_presentation_factory

    @property
    def model(self) -> SLDModel:
        """Return the presentation-owned SLD structural model."""
        return self._model

    @property
    def default_symbol_presentation_factory(self) -> Callable[[str], Mapping[str, Any]] | None:
        """Return the presentation-layer default symbol factory."""
        return self._default_symbol_presentation_factory

    def materialize_missing_symbol_presentations(self) -> None:
        """Materialize defaults only for nodes that have no authored presentation state."""
        factory = self._default_symbol_presentation_factory
        if factory is None:
            return
        for node in self._model.nodes:
            if node.presentation is not None:
                continue
            element_type = node.properties.get("element_type")
            identifier = (
                element_type
                if isinstance(element_type, str) and element_type.strip()
                else node.equipment_id
            )
            if not isinstance(identifier, str) or not identifier.strip():
                continue
            node.presentation = SymbolBase.from_dict(factory(identifier))

    def set_node_position(self, node_id: str, x: float, y: float) -> None:
        """Persist graphical position in the SLD document model."""
        self._model.get_node(node_id).set_position(x, y)
        self.mark_modified()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the SLD document and its structural model."""
        return {
            "schema": self.SLD_SCHEMA,
            "document_id": self.document_id,
            "project_id": self.project_id,
            "document_type": self.document_type,
            "name": self.name,
            "modified": self.modified,
            "model": self.model.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        default_symbol_presentation_factory: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> "SLDDocument":
        """Restore an SLD document and materialize missing symbol presentation defaults."""
        if not isinstance(data, Mapping):
            raise TypeError("SLD document payload must be a mapping.")
        schema = data.get("schema", 1)
        if schema not in (1, cls.SLD_SCHEMA):
            raise ValueError(f"Unsupported SLD representation schema: {schema!r}")
        document = cls(
            document_id=str(data["document_id"]),
            name=str(data.get("name", "Untitled SLD")),
            project_id=data.get("project_id"),
            model=SLDModel.from_dict(data.get("model", {})),
            default_symbol_presentation_factory=default_symbol_presentation_factory,
        )
        document.materialize_missing_symbol_presentations()
        if bool(data.get("modified", False)):
            document.mark_modified()
        return document

    def clear(self) -> None:
        """Clear presentation structure without touching Core."""
        self._model.clear()
        self.mark_modified()

    def __repr__(self) -> str:
        return (
            f"SLDDocument(document_id={self.document_id!r}, "
            f"name={self.name!r}, nodes={self.model.node_count}, "
            f"connections={self.model.connection_count}, "
            f"modified={self.modified!r})"
        )


__all__ = ["SLDDocument"]
