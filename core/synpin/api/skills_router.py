"""Skills settings endpoint — list + enable/disable globally.

Mirrors tools_router.py in structure. Returns skill metadata from
the SkillManager (data/skills/*/SKILL.md), enriched with enabled
state from settings.yaml:skills.disabled.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config.manager import get_disabled_skills, set_disabled_skill
from ..skills.manager import list_skills

logger = logging.getLogger("synpin.api.skills")

router = APIRouter(prefix="/api/skills/settings", tags=["skills"])


# ── Response models ────────────────────────────────────────────────

class SkillEntry(BaseModel):
    name: str
    description: str
    category: str
    enabled: bool


class SkillToggleRequest(BaseModel):
    name: str
    enabled: bool


class SkillToggleResponse(BaseModel):
    name: str
    enabled: bool
    changed: bool


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("/")
def list_all_skills() -> list[SkillEntry]:
    """Return all known skills with their current enabled state."""
    disabled = set(get_disabled_skills())
    entries: list[SkillEntry] = []
    for s in list_skills():
        entries.append(SkillEntry(
            name=s.name,
            description=s.description,
            category=s.category,
            enabled=s.name not in disabled,
        ))
    entries.sort(key=lambda s: (s.category, s.name))
    return entries


@router.post("/toggle", response_model=SkillToggleResponse)
def toggle_skill(req: SkillToggleRequest) -> SkillToggleResponse:
    """Enable or disable a skill globally."""
    # Validate skill exists
    all_names = {s.name for s in list_skills()}
    if req.name not in all_names:
        raise HTTPException(404, f"Unknown skill: {req.name}")
    changed = set_disabled_skill(req.name, not req.enabled)
    return SkillToggleResponse(
        name=req.name,
        enabled=req.enabled,
        changed=changed,
    )


@router.get("/disabled")
def list_disabled() -> dict:
    """Return just the disabled skill names — debug/health."""
    return {"disabled": get_disabled_skills()}
