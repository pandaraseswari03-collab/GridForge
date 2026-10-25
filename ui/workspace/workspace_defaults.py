# ============================================================
# File: ui/workspace/workspace_defaults.py
# GridForge V2 — Canonical Workspace Defaults
# Author: Subhendu Mishra
# ============================================================
"""Canonical Area → Editor → Region workspace definitions."""

from __future__ import annotations

from .area import AreaDefinition
from .workspace_definition import WorkspaceDefinition
from .editor import EditorDefinition, SLD_EDITOR, CONTROL_EDITOR, PROTECTION_EDITOR, STUDY_EDITOR
from .region import (
    CANVAS_REGION, DIAGNOSTICS_REGION, HEADER_REGION, OVERLAY_REGION,
    SIDEBAR_REGION, STATUS_REGION, TOOL_SHELF_REGION, TOOL_SETTINGS_REGION, RegionDefinition,
)

SLD_WORKSPACE_ID = "sld"
CONTROL_WORKSPACE_ID = "control"
PROTECTION_WORKSPACE_ID = "protection"
STUDY_WORKSPACE_ID = "study"

# These IDs identify existing presentation widgets only. They are not workspace
# placement records and are intentionally outside WorkspaceDefinition.
PROJECT_PANEL_ID = "project"
EQUIPMENT_PANEL_ID = "equipment"
PROPERTIES_PANEL_ID = "properties"
ELEMENT_LIST_PANEL_ID = "element_list"
MESSAGES_PANEL_ID = "messages"
STUDY_CASES_PANEL_ID = "study_cases"
CANONICAL_PANEL_IDS = (
    PROJECT_PANEL_ID, EQUIPMENT_PANEL_ID, PROPERTIES_PANEL_ID,
    ELEMENT_LIST_PANEL_ID, MESSAGES_PANEL_ID, STUDY_CASES_PANEL_ID,
)

EDITOR_REGIONS = (
    RegionDefinition(HEADER_REGION, HEADER_REGION, minimum_size=34, preferred_size=44),
    RegionDefinition(TOOL_SHELF_REGION, TOOL_SHELF_REGION, minimum_size=180, preferred_size=250),
    RegionDefinition(TOOL_SETTINGS_REGION, TOOL_SETTINGS_REGION, minimum_size=34, preferred_size=42),
    RegionDefinition(CANVAS_REGION, CANVAS_REGION, minimum_size=120),
    RegionDefinition(SIDEBAR_REGION, SIDEBAR_REGION, minimum_size=260, preferred_size=320),
    RegionDefinition(OVERLAY_REGION, OVERLAY_REGION, minimum_size=80, preferred_size=120),
    RegionDefinition(DIAGNOSTICS_REGION, DIAGNOSTICS_REGION, minimum_size=110, preferred_size=180),
    RegionDefinition(STATUS_REGION, STATUS_REGION, minimum_size=28, preferred_size=32),
)

SLD_EDITOR_REGIONS = (
    RegionDefinition(HEADER_REGION, HEADER_REGION, minimum_size=34, preferred_size=38),
    RegionDefinition(TOOL_SHELF_REGION, TOOL_SHELF_REGION, minimum_size=44, preferred_size=52),
    RegionDefinition(TOOL_SETTINGS_REGION, TOOL_SETTINGS_REGION, visible=False, minimum_size=0, preferred_size=42),
    RegionDefinition("explorer", "explorer", visible=False, minimum_size=0, preferred_size=220),
    RegionDefinition(CANVAS_REGION, CANVAS_REGION, minimum_size=120),
    RegionDefinition(SIDEBAR_REGION, SIDEBAR_REGION, visible=False, minimum_size=0, preferred_size=280),
    RegionDefinition(OVERLAY_REGION, OVERLAY_REGION, visible=False, minimum_size=0, preferred_size=0),
    RegionDefinition(DIAGNOSTICS_REGION, DIAGNOSTICS_REGION, visible=False, minimum_size=0, preferred_size=180),
    RegionDefinition(STATUS_REGION, STATUS_REGION, minimum_size=24, preferred_size=26),
)

SLD_EDITOR_DEFINITION = EditorDefinition("sld-editor", SLD_EDITOR, "SLD Editor", SLD_EDITOR_REGIONS)
CONTROL_EDITOR_DEFINITION = EditorDefinition("control-editor", CONTROL_EDITOR, "Control Editor", EDITOR_REGIONS)
PROTECTION_EDITOR_DEFINITION = EditorDefinition("protection-editor", PROTECTION_EDITOR, "Protection Editor", EDITOR_REGIONS)
STUDY_EDITOR_DEFINITION = EditorDefinition(
    "study-editor", STUDY_EDITOR, "Study Editor",
    EDITOR_REGIONS + (
        RegionDefinition("explorer", "explorer", visible=False, minimum_size=0, preferred_size=220),
        RegionDefinition("timeline", "timeline"),
    ),
)

def _workspace(workspace_id: str, title: str, editor: EditorDefinition, central_surface: str) -> WorkspaceDefinition:
    return WorkspaceDefinition(
        workspace_id=workspace_id,
        title=title,
        areas=(
            AreaDefinition(f"main-{workspace_id}", editor, metadata={"role": "main"}),
        ),
        metadata={"kind": workspace_id, "central_surface": central_surface},
    )

SLD_WORKSPACE = _workspace(SLD_WORKSPACE_ID, "SLD Workspace", SLD_EDITOR_DEFINITION, "sld")
CONTROL_WORKSPACE = _workspace(CONTROL_WORKSPACE_ID, "Control Workspace", CONTROL_EDITOR_DEFINITION, "control")
PROTECTION_WORKSPACE = _workspace(PROTECTION_WORKSPACE_ID, "Protection Workspace", PROTECTION_EDITOR_DEFINITION, "protection")
STUDY_WORKSPACE = WorkspaceDefinition(
    workspace_id=STUDY_WORKSPACE_ID,
    title="Study Workspace",
    areas=(
        AreaDefinition("main-study", STUDY_EDITOR_DEFINITION, metadata={"role": "main"}),
    ),
    metadata={"kind": "study", "central_surface": "reports"},
)

DEFAULT_WORKSPACES = (SLD_WORKSPACE, CONTROL_WORKSPACE, PROTECTION_WORKSPACE, STUDY_WORKSPACE)

def default_workspaces() -> tuple[WorkspaceDefinition, ...]:
    return DEFAULT_WORKSPACES

def default_workspace_ids() -> tuple[str, ...]:
    return tuple(item.workspace_id for item in DEFAULT_WORKSPACES)

def get_default_workspace(workspace_id: str) -> WorkspaceDefinition:
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id must be a non-empty string.")
    for workspace in DEFAULT_WORKSPACES:
        if workspace.workspace_id == workspace_id:
            return workspace
    raise KeyError(f"Unknown default workspace: {workspace_id!r}")

def get_initial_workspace() -> WorkspaceDefinition:
    return SLD_WORKSPACE

def validate_default_workspace() -> None:
    for workspace in DEFAULT_WORKSPACES:
        if not workspace.areas:
            raise RuntimeError(f"Workspace {workspace.workspace_id!r} has no Areas.")
        if not any(area.metadata.get("role") == "main" for area in workspace.areas):
            raise RuntimeError(f"Workspace {workspace.workspace_id!r} has no main Area.")

validate_default_workspace()

__all__ = [
    "SLD_WORKSPACE_ID", "CONTROL_WORKSPACE_ID", "PROTECTION_WORKSPACE_ID", "STUDY_WORKSPACE_ID",
    "PROJECT_PANEL_ID", "EQUIPMENT_PANEL_ID", "PROPERTIES_PANEL_ID", "ELEMENT_LIST_PANEL_ID",
    "MESSAGES_PANEL_ID", "STUDY_CASES_PANEL_ID", "CANONICAL_PANEL_IDS",
    "SLD_WORKSPACE", "CONTROL_WORKSPACE", "PROTECTION_WORKSPACE", "STUDY_WORKSPACE",
    "DEFAULT_WORKSPACES", "SLD_EDITOR_REGIONS", "SLD_EDITOR_DEFINITION", "CONTROL_EDITOR_DEFINITION",
    "PROTECTION_EDITOR_DEFINITION", "STUDY_EDITOR_DEFINITION", "default_workspaces",
    "default_workspace_ids", "get_default_workspace", "get_initial_workspace", "validate_default_workspace",
]
