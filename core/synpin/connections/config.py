"""Config loader — connections.yaml, approval_history.yaml, canvas positions."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..paths import get_config_dir, get_data_dir
from ..time import now as _now
from .models import (
    AutoTriggerConfig,
    CanvasData,
    Connection,
    ConnectionType,
    ApprovalRecord,
    ApprovalStatus,
    NodePosition,
)

logger = logging.getLogger("synpin.connections.config")

# ── Path resolution ──────────────────────────────────────────────────────────


def _connections_path() -> Path:
    return get_config_dir() / "connections.yaml"


def _history_path() -> Path:
    return get_data_dir() / "approval_history.yaml"


def _canvas_path() -> Path:
    return get_data_dir() / "canvas" / "positions.json"


# ── YAML helpers ─────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file, return empty dict if missing."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        return {}


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    """Save dict to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


# ── Connection ID generation ─────────────────────────────────────────────────

def _generate_id(prefix: str = "conn") -> str:
    """Generate a unique ID with prefix."""
    import secrets
    return f"{prefix}-{secrets.token_hex(4)}"


# ── Connections CRUD ─────────────────────────────────────────────────────────

def load_connections() -> list[Connection]:
    """Load all connections from connections.yaml."""
    data = _load_yaml(_connections_path())
    raw_list = data.get("connections", [])
    result = []
    for item in raw_list:
        try:
            # Map YAML keys to model fields
            conn_data = {
                "id": item.get("id", ""),
                "from_otdel": item.get("from", ""),
                "to_otdel": item.get("to", ""),
                "type": item.get("type", "peer"),
                "label": item.get("label", ""),
                "description": item.get("description", ""),
                "active": item.get("active", True),
            }
            if "auto_trigger" in item and item["auto_trigger"]:
                conn_data["auto_trigger"] = AutoTriggerConfig(**item["auto_trigger"])
            result.append(Connection(**conn_data))
        except Exception as e:
            logger.warning("Skipping invalid connection: %s — %s", item, e)
    return result


def save_connections(connections: list[Connection]) -> None:
    """Save connections list to connections.yaml."""
    raw_list = []
    for conn in connections:
        item: dict[str, Any] = {
            "id": conn.id,
            "from": conn.from_otdel,
            "to": conn.to_otdel,
            "type": conn.type.value,
            "label": conn.label,
            "description": conn.description,
            "active": conn.active,
        }
        if conn.auto_trigger:
            item["auto_trigger"] = {
                "on_status": conn.auto_trigger.on_status,
                "timeout_s": conn.auto_trigger.timeout_s,
            }
        raw_list.append(item)

    _save_yaml(_connections_path(), {"connections": raw_list})


def get_connection(conn_id: str) -> Connection | None:
    """Get a single connection by ID."""
    for conn in load_connections():
        if conn.id == conn_id:
            return conn
    return None


def create_connection(
    from_otdel: str,
    to_otdel: str,
    conn_type: str = "peer",
    label: str = "",
    description: str = "",
    auto_trigger: dict[str, Any] | None = None,
) -> Connection:
    """Create a new connection and save."""
    conn = Connection(
        id=_generate_id("conn"),
        from_otdel=from_otdel,
        to_otdel=to_otdel,
        type=ConnectionType(conn_type),
        label=label,
        description=description,
    )
    if auto_trigger and conn_type == "approval":
        conn.auto_trigger = AutoTriggerConfig(**auto_trigger)

    connections = load_connections()
    connections.append(conn)
    save_connections(connections)
    logger.info("Created connection %s: %s →%s (%s)", conn.id, from_otdel, to_otdel, conn_type)
    return conn


def update_connection(conn_id: str, updates: dict[str, Any]) -> Connection | None:
    """Update an existing connection."""
    connections = load_connections()
    for i, conn in enumerate(connections):
        if conn.id == conn_id:
            for key, value in updates.items():
                if key == "type" and isinstance(value, str):
                    value = ConnectionType(value)
                if key == "auto_trigger" and isinstance(value, dict):
                    value = AutoTriggerConfig(**value)
                if hasattr(conn, key):
                    setattr(conn, key, value)
            conn.updated_at = _now()
            connections[i] = conn
            save_connections(connections)
            logger.info("Updated connection %s", conn_id)
            return conn
    return None


def delete_connection(conn_id: str) -> bool:
    """Delete a connection. Clean Delete — also removes related approval history."""
    connections = load_connections()
    original_len = len(connections)
    connections = [c for c in connections if c.id != conn_id]
    if len(connections) == original_len:
        return False

    save_connections(connections)

    # Clean Delete: remove approval history for this connection
    _clean_history_for_connection(conn_id)

    # Clean Delete: remove canvas position if source/target has no other connections
    _clean_positions_if_orphaned(conn_id, connections)

    logger.info("Deleted connection %s (with cleanup)", conn_id)
    return True


# ── Approval History ────────────────────────────────────────────────────────

def load_history() -> list[ApprovalRecord]:
    """Load approval history."""
    data = _load_yaml(_history_path())
    raw_list = data.get("history", [])
    result = []
    for item in raw_list:
        try:
            record = ApprovalRecord(
                id=item.get("id", ""),
                task_id=item.get("task_id", ""),
                from_otdel=item.get("from", ""),
                to_otdel=item.get("to", ""),
                connection_id=item.get("connection_id", ""),
                reason=item.get("reason", ""),
                report=item.get("report", ""),
                status=item.get("status", "pending"),
                timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else _now(),
                resolved_at=datetime.fromisoformat(item["resolved_at"]) if item.get("resolved_at") else None,
                resolution=item.get("resolution", ""),
            )
            result.append(record)
        except Exception as e:
            logger.warning("Skipping invalid history record: %s — %s", item, e)
    return result


def save_history(records: list[ApprovalRecord]) -> None:
    """Save approval history."""
    raw_list = []
    for rec in records:
        raw_list.append({
            "id": rec.id,
            "task_id": rec.task_id,
            "from": rec.from_otdel,
            "to": rec.to_otdel,
            "connection_id": rec.connection_id,
            "reason": rec.reason,
            "report": rec.report,
            "status": rec.status.value,
            "timestamp": rec.timestamp.isoformat(),
            "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
            "resolution": rec.resolution,
        })
    _save_yaml(_history_path(), {"history": raw_list})


def add_history_record(
    task_id: str,
    from_otdel: str,
    to_otdel: str,
    connection_id: str,
    reason: str = "",
    report: str = "",
) -> ApprovalRecord:
    """Add a new approval record."""
    record = ApprovalRecord(
        id=_generate_id("esc"),
        task_id=task_id,
        from_otdel=from_otdel,
        to_otdel=to_otdel,
        connection_id=connection_id,
        reason=reason,
        report=report,
    )
    records = load_history()
    records.append(record)
    save_history(records)
    return record


def _clean_history_for_connection(connection_id: str) -> None:
    """Clean Delete: remove all history records for a connection."""
    records = load_history()
    cleaned = [r for r in records if r.connection_id != connection_id]
    if len(cleaned) < len(records):
        save_history(cleaned)
        logger.info("Cleaned %d history records for connection %s", len(records) - len(cleaned), connection_id)


def clean_history_for_task(task_id: str) -> None:
    """Clean Delete: remove all history records for a task."""
    records = load_history()
    cleaned = [r for r in records if r.task_id != task_id]
    if len(cleaned) < len(records):
        save_history(cleaned)
        logger.info("Cleaned %d history records for task %s", len(records) - len(cleaned), task_id)


def clean_history_for_otdel(otdel_slug: str) -> None:
    """Clean Delete: remove all history records where otdel is involved."""
    records = load_history()
    cleaned = [r for r in records if r.from_otdel != otdel_slug and r.to_otdel != otdel_slug]
    if len(cleaned) < len(records):
        save_history(cleaned)
        logger.info("Cleaned %d history records for otdel %s", len(records) - len(cleaned), otdel_slug)


# ── Canvas Positions ─────────────────────────────────────────────────────────

def load_canvas() -> CanvasData:
    """Load canvas positions from JSON."""
    path = _canvas_path()
    if not path.exists():
        return CanvasData()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes = {}
        for slug, pos in data.get("nodes", {}).items():
            nodes[slug] = NodePosition(x=pos.get("x", 0), y=pos.get("y", 0))
        return CanvasData(
            version=data.get("version", 1),
            nodes=nodes,
            viewport=data.get("viewport", {"x": 0, "y": 0, "zoom": 1}),
        )
    except Exception as e:
        logger.warning("Failed to load canvas positions: %s", e)
        return CanvasData()


def save_canvas(canvas: CanvasData) -> None:
    """Save canvas positions to JSON."""
    path = _canvas_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": canvas.version,
        "nodes": {slug: {"x": pos.x, "y": pos.y} for slug, pos in canvas.nodes.items()},
        "viewport": canvas.viewport,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _clean_positions_if_orphaned(conn_id: str, remaining_connections: list[Connection]) -> None:
    """Clean Delete: if a department has no more connections, remove its canvas position."""
    # Find all departments still involved in connections
    active_otdels: set[str] = set()
    for conn in remaining_connections:
        active_otdels.add(conn.from_otdel)
        active_otdels.add(conn.to_otdel)

    canvas = load_canvas()
    orphans = [slug for slug in canvas.nodes if slug not in active_otdels]
    for slug in orphans:
        del canvas.nodes[slug]
        logger.info("Removed orphaned canvas position for %s", slug)

    if orphans:
        save_canvas(canvas)
