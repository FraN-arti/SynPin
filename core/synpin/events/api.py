"""Events HTTP API.

Endpoints:
  GET    /api/events                  — list recent events + unread count
  POST   /api/events/{id}/read        — mark one read
  POST   /api/events/read-all         — mark all read
  POST   /api/events/clear            — wipe all (settings action)
  GET    /api/events/settings         — return effective in-app settings
  PUT    /api/events/settings         — update in-app settings (limited keys)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .bus import get_bus
from .settings import get_in_app_settings, update_in_app_settings

router = APIRouter(prefix="/api/events", tags=["events"])


def _serialize(ev) -> dict:
    """Public shape of an event (dataclass → dict)."""
    return {
        "id": ev.id,
        "title": ev.title,
        "body": ev.body,
        "level": ev.level,
        "source": ev.source,
        "source_ref": ev.source_ref,
        "created_at": ev.created_at,
        "read_at": ev.read_at,
    }


@router.get("")
def list_events(limit: int = 50) -> dict:
    """Recent events (newest first) + unread count."""
    bus = get_bus()
    return {
        "unread_count": bus.unread_count(),
        "items": [_serialize(e) for e in bus.list_all(limit=limit)],
    }


@router.post("/{event_id}/read")
def mark_read(event_id: str) -> dict:
    bus = get_bus()
    ev = bus.mark_read(event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    return _serialize(ev)


@router.post("/read-all")
def mark_all_read() -> dict:
    n = get_bus().mark_all_read()
    return {"marked": n}


@router.post("/clear")
def clear() -> dict:
    n = get_bus().clear()
    return {"cleared": n}


@router.get("/settings")
def get_settings() -> dict:
    return {"in_app": get_in_app_settings(), "channels": []}


class InAppSettingsUpdate(BaseModel):
    enabled: bool | None = None
    auto_fade_seconds: int | None = None
    max_visible: int | None = None


@router.put("/settings")
def put_settings(update: InAppSettingsUpdate) -> dict:
    # Drop None fields so partial updates work.
    payload = {k: v for k, v in update.model_dump().items() if v is not None}
    in_app = update_in_app_settings(payload)
    return {"in_app": in_app, "channels": []}