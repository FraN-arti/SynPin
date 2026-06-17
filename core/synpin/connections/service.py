"""Service — business logic for connections, escalation, and graph building."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from .models import (
    Connection,
    ConnectionType,
    EscalationRecord,
    EscalationStatus,
    Graph,
    GraphEdge,
    GraphNode,
    NodePosition,
)
from . import config

logger = logging.getLogger("synpin.connections.service")

# ── WebSocket broadcast ──────────────────────────────────────────────────────

_ws_loop: asyncio.AbstractEventLoop | None = None


def set_ws_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Set the event loop for broadcasting WS events from sync context."""
    global _ws_loop
    _ws_loop = loop


def _broadcast(event: dict) -> None:
    """Schedule a broadcast on the WS event loop (thread-safe)."""
    if _ws_loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(_ws_broadcast(event), _ws_loop)
    except Exception:
        pass


async def _ws_broadcast(event: dict) -> None:
    """Actually broadcast via ws_manager."""
    try:
        from ..chat.ws_manager import ws_manager
        await ws_manager.broadcast(event)
    except Exception:
        pass


# ── Connections CRUD ─────────────────────────────────────────────────────────

def list_connections() -> list[Connection]:
    """List all connections."""
    return config.load_connections()


def get_connection(conn_id: str) -> Connection | None:
    """Get a single connection."""
    return config.get_connection(conn_id)


def create_connection(
    from_otdel: str,
    to_otdel: str,
    conn_type: str = "peer",
    label: str = "",
    description: str = "",
    auto_trigger: dict[str, Any] | None = None,
) -> Connection:
    """Create a new connection and broadcast WS event."""
    conn = config.create_connection(from_otdel, to_otdel, conn_type, label, description, auto_trigger)
    _broadcast({"type": "connections:created", "connection": _conn_to_dict(conn)})
    return conn


def update_connection(conn_id: str, updates: dict[str, Any]) -> Connection | None:
    """Update a connection and broadcast WS event."""
    conn = config.update_connection(conn_id, updates)
    if conn:
        _broadcast({"type": "connections:updated", "connection": _conn_to_dict(conn)})
    return conn


def delete_connection(conn_id: str) -> bool:
    """Delete a connection with Clean Delete and broadcast WS event."""
    ok = config.delete_connection(conn_id)
    if ok:
        _broadcast({"type": "connections:deleted", "connection_id": conn_id})
    return ok


def _conn_to_dict(conn: Connection) -> dict[str, Any]:
    """Serialize connection for WS/API."""
    return {
        "id": conn.id,
        "from": conn.from_otdel,
        "to": conn.to_otdel,
        "type": conn.type.value,
        "label": conn.label,
        "description": conn.description,
        "active": conn.active,
        "auto_trigger": {
            "on_status": conn.auto_trigger.on_status,
            "timeout_s": conn.auto_trigger.timeout_s,
        } if conn.auto_trigger else None,
    }


# ── Escalation ───────────────────────────────────────────────────────────────

def escalate_task(
    task_id: str,
    from_otdel: str,
    to_otdel: str | None = None,
    reason: str = "",
    report: str = "",
) -> EscalationRecord | None:
    """Escalate a task from one department to another.

    If to_otdel is None, finds the escalation connection automatically.
    """
    # Find connection
    connection = _find_escalation_connection(from_otdel, to_otdel)
    if not connection:
        logger.warning("No escalation connection found: %s → %s", from_otdel, to_otdel or "(auto)")
        return None

    target = connection.to_otdel

    # Record escalation
    record = config.add_history_record(
        task_id=task_id,
        from_otdel=from_otdel,
        to_otdel=target,
        connection_id=connection.id,
        reason=reason,
        report=report,
    )

    # Update kanban task
    _move_task_to_otdel(task_id, target)

    # Broadcast
    _broadcast({
        "type": "connections:escalation_started",
        "escalation": {
            "id": record.id,
            "task_id": task_id,
            "from": from_otdel,
            "to": target,
            "connection_id": connection.id,
            "reason": reason,
        },
    })

    logger.info("Escalated task %s: %s → %s (reason: %s)", task_id, from_otdel, target, reason)
    return record


def complete_escalation(escalation_id: str, resolution: str = "") -> bool:
    """Mark an escalation as completed."""
    records = config.load_history()
    for rec in records:
        if rec.id == escalation_id:
            rec.status = EscalationStatus.COMPLETED
            rec.resolved_at = datetime.now(timezone.utc)
            rec.resolution = resolution
            config.save_history(records)

            _broadcast({
                "type": "connections:escalation_complete",
                "escalation_id": escalation_id,
                "resolution": resolution,
            })
            return True
    return False


def _find_escalation_connection(from_otdel: str, to_otdel: str | None = None) -> Connection | None:
    """Find an escalation connection between departments."""
    connections = config.load_connections()
    for conn in connections:
        if not conn.active:
            continue
        if conn.type != ConnectionType.ESCALATION:
            continue
        if conn.from_otdel != from_otdel:
            continue
        if to_otdel and conn.to_otdel != to_otdel:
            continue
        return conn
    return None


def _move_task_to_otdel(task_id: str, target_otdel: str) -> None:
    """Move a kanban task to a target department."""
    try:
        from ..kanban.service import KanbanService
        from ..kanban.models import TaskStatus

        svc = KanbanService()
        task = svc.get_task(task_id)
        if not task:
            logger.warning("Task %s not found for escalation", task_id)
            return

        # Update department
        task.current_department = target_otdel
        task.department = target_otdel

        # Add to summon chain
        if target_otdel not in task.summon_chain:
            task.summon_chain.append(target_otdel)

        # Move to TODO status in new department
        task.move_to(TaskStatus.TODO, actor="escalation")

        svc.save_task(task)
    except Exception as e:
        logger.error("Failed to move task %s to %s: %s", task_id, target_otdel, e)


# ── Graph Building ───────────────────────────────────────────────────────────

def build_graph() -> Graph:
    """Build a React Flow graph from connections + otdel data."""
    connections = config.load_connections()
    canvas = config.load_canvas()

    # Load otdel data for node info
    otdels = _load_otdels()
    agents = _load_agents()

    # Build nodes
    nodes: list[GraphNode] = []
    involved_otdels: set[str] = set()

    for conn in connections:
        involved_otdels.add(conn.from_otdel)
        involved_otdels.add(conn.to_otdel)

    for slug in involved_otdels:
        otdel = otdels.get(slug, {})
        pos = canvas.nodes.get(slug, NodePosition(x=0, y=0))

        # Count active tasks
        active_tasks = _count_active_tasks(slug)

        # Resolve head agent name
        head_id = otdel.get("head", "")
        head_name = agents.get(head_id, {}).get("name", head_id) if head_id else ""

        nodes.append(GraphNode(
            id=slug,
            type="department",
            position=pos,
            data={
                "name": otdel.get("name", slug),
                "head": head_name,
                "level": otdel.get("level", 0),
                "workers_count": len(otdel.get("workers", [])),
                "active_tasks": active_tasks,
                "status": "active",
            },
        ))

    # Build edges — merge multiple connections between same pair into one edge
    color_map = {
        ConnectionType.PEER: "#3b82f6",
        ConnectionType.ESCALATION: "#f97316",
        ConnectionType.DELEGATION: "#22c55e",
    }

    # Group connections by (from, to) pair
    edge_groups: dict[tuple[str, str], list] = {}
    for conn in connections:
        if not conn.active:
            continue
        key = (conn.from_otdel, conn.to_otdel)
        if key not in edge_groups:
            edge_groups[key] = []
        edge_groups[key].append(conn)

    edges: list[GraphEdge] = []
    for (source, target), conns in edge_groups.items():
        # Merge labels
        labels = [c.label or c.type.value for c in conns]
        merged_label = " · ".join(labels)

        # Use the "highest priority" color (escalation > delegation > peer)
        priority = {ConnectionType.ESCALATION: 3, ConnectionType.DELEGATION: 2, ConnectionType.PEER: 1}
        top_conn = max(conns, key=lambda c: priority.get(c.type, 0))
        color = color_map.get(top_conn.type, "#6b7280")

        # Check for active escalations
        has_active = any(_has_active_escalation(c.id) for c in conns)

        # Collect all connection IDs for the edge data
        conn_ids = [c.id for c in conns]
        conn_types = list({c.type.value for c in conns})

        edges.append(GraphEdge(
            id=conns[0].id,  # Use first connection ID
            source=source,
            target=target,
            label=merged_label,
            animated=has_active,
            data={
                "connection_types": conn_types,
                "connection_ids": conn_ids,
                "color": color,
                "active_transfers": 1 if has_active else 0,
            },
        ))

    return Graph(nodes=nodes, edges=edges)


def _load_otdels() -> dict[str, dict[str, Any]]:
    """Load otdel data for graph nodes."""
    try:
        from ..agents.manager import load_otdels
        data = load_otdels()
        # load_otdels returns a list (not dict)
        if isinstance(data, list):
            return {o.get("otdelid", ""): o for o in data}
        return {o.get("otdelid", ""): o for o in data.get("otdels", [])}
    except Exception:
        return {}


def _load_agents() -> dict[str, dict[str, Any]]:
    """Load agent data for name resolution."""
    try:
        from ..config.manager import load_yaml
        from ..paths import get_data_dir
        data_dir = get_data_dir()
        agents_dir = data_dir / "agents"
        result = {}
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                agent_yaml = agent_dir / "agent.yaml"
                if agent_yaml.exists():
                    try:
                        data = load_yaml(str(agent_yaml))
                        if data and data.get("name"):
                            agent_id = agent_dir.name
                            result[agent_id] = data
                    except Exception:
                        pass
        # Also check config/agents.yaml for names
        config_agents = load_yaml("agents.yaml")
        for slug, cfg in config_agents.get("agents", {}).items():
            if slug not in result and cfg.get("name"):
                result[slug] = cfg
        return result
    except Exception:
        return {}


def _count_active_tasks(otdel_slug: str) -> int:
    """Count active tasks for an otdel."""
    try:
        from ..kanban.service import KanbanService
        from ..kanban.models import TaskStatus

        svc = KanbanService()
        active_statuses = {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.BLOCKED}
        tasks = svc.list_tasks()
        return sum(1 for t in tasks if t.department == otdel_slug and t.status in active_statuses)
    except Exception:
        return 0


def _has_active_escalation(connection_id: str) -> bool:
    """Check if there's an active (pending) escalation for this connection."""
    records = config.load_history()
    return any(r.connection_id == connection_id and r.status == EscalationStatus.PENDING for r in records)


# ── Canvas Positions ─────────────────────────────────────────────────────────

def save_positions(positions: dict[str, dict[str, float]], viewport: dict[str, float] | None = None) -> None:
    """Save canvas node positions."""
    from .models import CanvasData, NodePosition

    nodes = {}
    for slug, pos in positions.items():
        nodes[slug] = NodePosition(x=pos.get("x", 0), y=pos.get("y", 0))

    canvas = config.load_canvas()
    canvas.nodes = nodes
    if viewport:
        canvas.viewport = viewport
    config.save_canvas(canvas)

    _broadcast({"type": "connections:positions_updated", "positions": positions})


# ── History ──────────────────────────────────────────────────────────────────

def list_history(
    task_id: str | None = None,
    from_otdel: str | None = None,
    to_otdel: str | None = None,
    status: str | None = None,
) -> list[EscalationRecord]:
    """List escalation history with optional filters."""
    records = config.load_history()
    if task_id:
        records = [r for r in records if r.task_id == task_id]
    if from_otdel:
        records = [r for r in records if r.from_otdel == from_otdel]
    if to_otdel:
        records = [r for r in records if r.to_otdel == to_otdel]
    if status:
        records = [r for r in records if r.status.value == status]
    return records


# ── Clean Delete ─────────────────────────────────────────────────────────────

def clean_for_otdel(otdel_slug: str) -> None:
    """Clean Delete: remove all connections and history for an otdel."""
    # Remove connections
    connections = config.load_connections()
    to_remove = [c.id for c in connections if c.from_otdel == otdel_slug or c.to_otdel == otdel_slug]
    for conn_id in to_remove:
        config.delete_connection(conn_id)

    # Clean history
    config.clean_history_for_otdel(otdel_slug)

    logger.info("Cleaned all connections data for otdel %s", otdel_slug)


def clean_for_task(task_id: str) -> None:
    """Clean Delete: remove escalation history for a task."""
    config.clean_history_for_task(task_id)
