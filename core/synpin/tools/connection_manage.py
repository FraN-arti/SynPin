"""Main Agent Protocol: Connection management — view, create, delete connections."""
from __future__ import annotations

from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool


@register_tool(
    name='connection_list',
    description='Показать все связи между отделами. Только для главного агента.',
    category='communication',
    scope='primary',
    dangerous=False,
)

async def connection_list(params: dict[str, Any]) -> ToolResult:
    """
    List all connections between departments.

    Returns:
        {connections: [{id, from, from_name, to, to_name, type, label, description, active}]}
    """
    try:
        from ..connections.config import load_connections
        from ..agents.manager import load_otdels as _load_otdels

        conns = load_connections()

        # Resolve otdel names
        otdels_list = _load_otdels()
        names: dict[str, str] = {}
        if isinstance(otdels_list, list):
            names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list}
        elif isinstance(otdels_list, dict):
            names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list.get("otdels", [])}

        result = []
        for c in conns:
            t = c.type.value if hasattr(c.type, 'value') else c.type
            result.append({
                "id": c.id,
                "from": c.from_otdel,
                "from_name": names.get(c.from_otdel, c.from_otdel),
                "to": c.to_otdel,
                "to_name": names.get(c.to_otdel, c.to_otdel),
                "type": t,
                "label": c.label,
                "description": c.description,
                "active": c.active,
            })

        return make_success({"connections": result, "count": len(result)})

    except Exception as e:
        return make_error(f"Failed to list connections: {e}")


@register_tool(
    name='connection_create',
    description='Создать связь между отделами. Только для главного агента.',
    category='communication',
    scope='primary',
    dangerous=False,
)

async def connection_create(params: dict[str, Any]) -> ToolResult:
    """
    Create a connection between two departments.

    Params:
        from_otdel: str (required) — source department ID
        to_otdel: str (required) — target department ID
        type: str (required) — "approval" | "delegation" | "peer"
        label: str (optional) — display name
        description: str (optional) — details

    Returns:
        {connection_id, from, to, type, message}
    """
    from_otdel = params.get("from_otdel", "")
    to_otdel = params.get("to_otdel", "")
    conn_type = params.get("type", "")
    label = params.get("label", "")
    description = params.get("description", "")

    if not from_otdel or not to_otdel:
        return make_error("from_otdel and to_otdel required")
    if conn_type not in ("approval", "delegation", "peer"):
        return make_error("type must be 'approval', 'delegation', or 'peer'")
    if from_otdel == to_otdel:
        return make_error("Cannot create connection to self")

    try:
        from ..connections.config import load_connections, save_connections
        from ..connections.models import Connection, ConnectionType
        import uuid

        conns = load_connections()

        # Check for duplicate
        for c in conns:
            if c.from_otdel == from_otdel and c.to_otdel == to_otdel and c.active:
                t = c.type.value if hasattr(c.type, 'value') else c.type
                if t == conn_type:
                    return make_error(f"Connection already exists: {from_otdel} → {to_otdel} ({conn_type})")

        type_map = {"approval": ConnectionType.APPROVAL, "delegation": ConnectionType.DELEGATION, "peer": ConnectionType.PEER}

        new_conn = Connection(
            id=f"conn-{uuid.uuid4().hex[:8]}",
            from_otdel=from_otdel,
            to_otdel=to_otdel,
            type=type_map[conn_type],
            label=label,
            description=description,
        )

        conns.append(new_conn)
        save_connections(conns)

        # Resolve names for display
        from ..agents.manager import load_otdels as _load_otdels
        otdels_list = _load_otdels()
        names: dict[str, str] = {}
        if isinstance(otdels_list, list):
            names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list}
        elif isinstance(otdels_list, dict):
            names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list.get("otdels", [])}

        from_name = names.get(from_otdel, from_otdel)
        to_name = names.get(to_otdel, to_otdel)

        # Broadcast
        from ..ws_broadcast import broadcast
        broadcast({"type": "connections:created"})

        return make_success({
            "connection_id": new_conn.id,
            "from": from_name,
            "to": to_name,
            "type": conn_type,
            "message": f"Connection created: {from_name} → {to_name} ({conn_type})",
        })

    except Exception as e:
        return make_error(f"Failed to create connection: {e}")


@register_tool(
    name='connection_delete',
    description='Удалить связь по ID. Только для главного агента.',
    category='communication',
    scope='primary',
    dangerous=False,
)

async def connection_delete(params: dict[str, Any]) -> ToolResult:
    """
    Delete a connection by ID.

    Params:
        connection_id: str (required) — connection ID (conn-xxx)

    Returns:
        {deleted, connection_id, message}
    """
    conn_id = params.get("connection_id", "")
    if not conn_id:
        return make_error("connection_id required")

    try:
        from ..connections.config import load_connections, save_connections

        conns = load_connections()
        found = False
        remaining = []

        for c in conns:
            if c.id == conn_id:
                found = True
            else:
                remaining.append(c)

        if not found:
            return make_error(f"Connection {conn_id} not found")

        save_connections(remaining)

        # Broadcast
        from ..ws_broadcast import broadcast
        broadcast({"type": "connections:deleted"})

        return make_success({
            "deleted": True,
            "connection_id": conn_id,
            "message": f"Connection {conn_id} deleted",
        })

    except Exception as e:
        return make_error(f"Failed to delete connection: {e}")


@register_tool(
    name='connection_history',
    description='История передач/утверждений/релайнов. Только для главного агента.',
    category='communication',
    scope='primary',
    dangerous=False,
)

async def connection_history(params: dict[str, Any]) -> ToolResult:
    """
    View approval/reline history.

    Params:
        task_id: str (optional) — filter by task
        limit: int (optional) — max records (default: 20)

    Returns:
        {history: [{id, task_id, from, from_name, to, to_name, reason, status, timestamp}]}
    """
    task_id = params.get("task_id") or None
    limit = params.get("limit", 20)

    try:
        from ..connections.config import load_history
        from ..agents.manager import load_otdels as _load_otdels

        records = load_history()

        # Resolve names
        otdels_list = _load_otdels()
        names: dict[str, str] = {}
        if isinstance(otdels_list, list):
            names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list}
        elif isinstance(otdels_list, dict):
            names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list.get("otdels", [])}

        # Filter
        if task_id:
            records = [r for r in records if r.task_id == task_id]

        # Sort by timestamp (newest first)
        records.sort(key=lambda r: r.timestamp, reverse=True)

        # Limit
        records = records[:limit]

        result = [
            {
                "id": r.id,
                "task_id": r.task_id,
                "from": r.from_otdel,
                "from_name": names.get(r.from_otdel, r.from_otdel),
                "to": r.to_otdel,
                "to_name": names.get(r.to_otdel, r.to_otdel),
                "reason": r.reason,
                "status": r.status.value,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in records
        ]

        return make_success({"history": result, "count": len(result)})

    except Exception as e:
        return make_error(f"Failed to get history: {e}")


__all__ = ["connection_list", "connection_create", "connection_delete", "connection_history"]
