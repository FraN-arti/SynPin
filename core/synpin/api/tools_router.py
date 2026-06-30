"""Tools settings endpoint — list + enable/disable globally.

Source of truth split between two places:
  - chat/router.py:_NATIVE_TOOL_DEFS  → what tools exist + JSON-schema for LLM
  - tools/                           → handlers (.py files)
  - config/tools.yaml                → optional metadata (display, category)

For the UI we read _NATIVE_TOOL_DEFS (the canonical list — onboarding a new
tool means adding it here), enrich with metadata where present in tools.yaml,
and overlay the disabled state from settings.yaml:tools.disabled.

Future refactor (separate ticket): auto-discover from tools/*.py instead of
hardcoded _NATIVE_TOOL_DEFS. See plan in session_search 2026-06-30.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config.manager import get_disabled_tools, set_disabled_tool
from ..chat.router import (
    _NATIVE_TOOL_DEFS,
    HEAD_TOOLS,
    PRIMARY_TOOLS,
    BUILTINS,
    DANGEROUS_TOOLS,
)

logger = logging.getLogger("synpin.api.tools")

router = APIRouter(prefix="/api/tools/settings", tags=["tools"])


# ── Metadata enrichment from tools.yaml ────────────────────────────────────────

def _load_tools_yaml_meta() -> dict[str, dict[str, Any]]:
    """Load optional display/category metadata from config/tools.yaml.

    Returns {tool_name: {display, description, category, implemented, builtin}}
    or {} if the file is missing/malformed. Tools NOT in this file still
    appear in the API — they just fall back to defaults derived from the
    JSON-schema description.
    """
    try:
        from ..config.manager import load_yaml
        data = load_yaml("tools.yaml")
        return (data or {}).get("tools", {}) or {}
    except Exception:
        return {}


# ── Response models ────────────────────────────────────────────────────────────

class ToolEntry(BaseModel):
    name: str
    display: str
    description: str
    category: str
    scope: str            # "all" | "head" | "primary" | "builtin"
    dangerous: bool
    implemented: bool
    enabled: bool         # not in settings.tools.disabled


class ToolToggleRequest(BaseModel):
    name: str
    enabled: bool


class ToolToggleResponse(BaseModel):
    name: str
    enabled: bool
    changed: bool         # True if state actually changed


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ToolEntry])
def list_tools() -> list[ToolEntry]:
    """Return all known tools with their current enabled state.

    Category/scope/dangerous flags come from the chat.router constants
    (single source of truth for tool role policy). Display/description
    enrichment comes from tools.yaml where present.
    """
    meta = _load_tools_yaml_meta()
    disabled = set(get_disabled_tools())

    entries: list[ToolEntry] = []
    for name, schema in _NATIVE_TOOL_DEFS.items():
        func = schema.get("function", {}) or {}
        m = meta.get(name, {}) or {}

        # Scope: where this tool is allowed to run
        if name in PRIMARY_TOOLS:
            scope = "primary"
        elif name in HEAD_TOOLS:
            scope = "head"
        elif name in BUILTINS:
            scope = "builtin"
        else:
            scope = "all"

        # Description for UI: prefer tools.yaml "description", fall back to schema
        ui_desc = m.get("description") or func.get("description", "") or ""

        # Category from tools.yaml; sensible default if missing
        category = m.get("category") or "other"

        entries.append(ToolEntry(
            name=name,
            display=m.get("display") or name,
            description=ui_desc,
            category=category,
            scope=scope,
            dangerous=name in DANGEROUS_TOOLS,
            implemented=bool(m.get("implemented", True)),
            enabled=name not in disabled,
        ))

    # Sort: by category then name — predictable order for the UI
    entries.sort(key=lambda t: (t.category, t.name))
    return entries


@router.post("/toggle", response_model=ToolToggleResponse)
def toggle_tool(req: ToolToggleRequest) -> ToolToggleResponse:
    """Enable or disable a tool globally.

    Persists to settings.yaml:tools.disabled. The disabled list is re-read
    on every LLM call (see get_all_tool_names in chat/router.py), so changes
    take effect immediately for subsequent messages — in-flight streams
    that have already been sent their tool schema are unaffected.
    """
    if req.name not in _NATIVE_TOOL_DEFS:
        raise HTTPException(404, f"Unknown tool: {req.name}")
    changed = set_disabled_tool(req.name, not req.enabled)
    return ToolToggleResponse(
        name=req.name,
        enabled=req.enabled,
        changed=changed,
    )


@router.get("/disabled")
def list_disabled() -> dict:
    """Return just the disabled names — convenient for debug/health."""
    return {"disabled": get_disabled_tools()}
