"""
Triggers — REST API for managing trigger definitions and instances.

Endpoints:
  GET    /api/triggers/definitions          — list all plugin types
  GET    /api/triggers/instances           — list all active instances
  POST   /api/triggers/instances           — create instance
  PATCH  /api/triggers/instances/{id}      — update config / enable / disable
  DELETE /api/triggers/instances/{id}      — delete instance
  POST   /api/triggers/reload              — force reload from disk

Definitions are scanned at engine startup and on every GET, so
newly-dropped plugin files in `definitions/` show up automatically.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ..triggers import registry as registry_mod
from ..triggers import store
from ..triggers.engine import get_engine

logger = logging.getLogger("synpin.api.triggers")

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


async def _broadcast(event_type: str) -> None:
    """Notify all WS clients that a trigger instance changed.

    Failures here must never break the API call — the worst case is
    a stale UI until the next refresh.
    """
    try:
        from ..chat.ws_manager import ws_manager
        await ws_manager.broadcast({"type": event_type})
    except Exception as e:  # noqa: BLE001
        logger.debug("triggers broadcast %s failed: %s", event_type, e)


def _definition_to_dict(defn: registry_mod.Definition) -> dict[str, Any]:
    """Project a Definition into the JSON shape the UI consumes."""
    meta = defn.metadata or {}
    return {
        "type": defn.type,
        "name": meta.get("name", defn.type),
        "description": meta.get("description", ""),
        "category": meta.get("category", "state"),
        "icon": meta.get("icon", "zap"),
        "color": meta.get("color", "orange"),
        "version": meta.get("version", 1),
        "config_schema": meta.get("config_schema", []),
        "action_types": meta.get("action_types", []),
        "tick_interval_s": int(getattr(defn.plugin_cls, "tick_interval", 0) or 0),
        # Optional: plugin opts into a global master switch in Settings.
        # Absence (or false) means the toggle isn't rendered.
        "global_toggle": bool(meta.get("global_toggle", {}).get("enabled_by_default", False)),
    }


@router.get("/definitions")
def list_definitions() -> dict[str, Any]:
    """All plugin types currently discovered in `definitions/`.

    Re-scans on every call so dropped-in plugins appear immediately.
    """
    defs = registry_mod.scan()
    return {
        "definitions": [_definition_to_dict(d) for d in defs.values()],
        "count": len(defs),
    }


@router.get("/instances")
def list_instances(type: str | None = None) -> dict[str, Any]:
    """All configured instances across all otdels.

    Optional `?type=foo` filters to a specific plugin type.
    """
    engine = get_engine()
    instances = engine.instances or store.all_instances()
    if type:
        instances = [i for i in instances if i.get("type") == type]
    return {"instances": instances, "count": len(instances)}


@router.post("/instances")
async def create_instance(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new trigger instance.

    Body: { type, otdel_id, config: {...}, action: {type, ...}, enabled? }
    """
    type_name = payload.get("type", "")
    otdel_id = payload.get("otdel_id", "")
    if not type_name or not otdel_id:
        raise HTTPException(400, "type and otdel_id are required")
    if type_name not in registry_mod.scan():
        raise HTTPException(404, f"unknown trigger type: {type_name}")

    instance_id = payload.get("id") or f"trig-{type_name}-{otdel_id}"
    data = store.load(otdel_id)
    # Avoid duplicates by id
    data["triggers"] = [t for t in data.get("triggers", []) if t.get("id") != instance_id]
    data["triggers"].append({
        "id": instance_id,
        "type": type_name,
        "config": payload.get("config", {}),
        "action": payload.get("action", {"type": "log"}),
        "enabled": payload.get("enabled", True),
    })
    store.save(otdel_id, data)
    get_engine().reload_instances()
    await _broadcast("triggers:instance_changed")
    return {"id": instance_id, "type": type_name, "otdel_id": otdel_id}


@router.patch("/instances/{instance_id}")
async def update_instance(instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update config / action / enabled state of an instance."""
    for oid in store.list_otdels():
        data = store.load(oid)
        for i, t in enumerate(data.get("triggers", [])):
            if t.get("id") == instance_id:
                for key in ("config", "action", "enabled"):
                    if key in payload:
                        t[key] = payload[key]
                data["triggers"][i] = t
                store.save(oid, data)
                get_engine().reload_instances()
                await _broadcast("triggers:instance_changed")
                return {"id": instance_id, "updated": True}
    raise HTTPException(404, f"instance not found: {instance_id}")


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str) -> dict[str, Any]:
    for oid in store.list_otdels():
        data = store.load(oid)
        before = len(data.get("triggers", []))
        data["triggers"] = [t for t in data.get("triggers", []) if t.get("id") != instance_id]
        if len(data["triggers"]) < before:
            store.save(oid, data)
            get_engine().reload_instances()
            await _broadcast("triggers:instance_changed")
            return {"id": instance_id, "deleted": True}
    raise HTTPException(404, f"instance not found: {instance_id}")


@router.post("/reload")
def force_reload() -> dict[str, Any]:
    """Force the engine to re-read instance YAMLs and re-scan definitions."""
    engine = get_engine()
    engine.reload_instances()
    return {"reloaded": True, "instances": len(engine.instances)}
