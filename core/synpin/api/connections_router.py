"""REST API for connections — CRUD, graph, approval, history."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ._base import BaseRequest
from ..connections import service as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/connections", tags=["connections"])


# ── Request models ───────────────────────────────────────────────────────────

class ConnectionCreate(BaseRequest):
    # Both `from_ref` and the legacy `from_otdel` are accepted. New
    # clients send `from_ref` (refs can target the primary agent);
    # older clients still posting `from_otdel` keep working.
    from_ref: str | None = None
    from_otdel: str | None = None
    to_ref: str | None = None
    to_otdel: str | None = None
    type: str = "peer"
    label: str
    description: str
    auto_trigger: dict[str, Any] | None = None

    def get_from(self) -> str:
        return self.from_ref or self.from_otdel or ""
    def get_to(self) -> str:
        return self.to_ref or self.to_otdel or ""


class ConnectionUpdate(BaseRequest):
    label: str | None = None
    description: str | None = None
    active: bool | None = None
    type: str | None = None
    auto_trigger: dict[str, Any] | None = None


class ApprovalCreate(BaseRequest):
    task_id: str
    # Both names accepted; the new `from_ref` is canonical, the
    # legacy `from_otdel` is mapped on the way in for older clients.
    from_ref: str | None = None
    from_otdel: str | None = None
    to_ref: str | None = None
    to_otdel: str | None = None

    def get_from(self) -> str:
        return self.from_ref or self.from_otdel or ""

    def get_to(self) -> str | None:
        return self.to_ref or self.to_otdel
    reason: str = ""
    report: str = ""


class ApprovalComplete(BaseRequest):
    resolution: str = ""


class PositionsUpdate(BaseRequest):
    positions: dict[str, dict[str, float]]
    viewport: dict[str, float] | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
async def list_connections():
    """List all connections."""
    connections = svc.list_connections()
    return {"connections": [svc._conn_to_dict(c) for c in connections]}


@router.post("")
async def create_connection(req: ConnectionCreate):
    """Create a new connection."""
    try:
        conn = svc.create_connection(
            from_ref=req.get_from(),
            to_ref=req.get_to(),
            conn_type=req.type,
            label=req.label,
            description=req.description,
            auto_trigger=req.auto_trigger,
        )
        return svc._conn_to_dict(conn)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/graph")
async def get_graph():
    """Get graph for React Flow rendering."""
    graph = svc.build_graph()
    return {
        "nodes": [{"id": n.id, "type": n.type, "position": {"x": n.position.x, "y": n.position.y}, "data": n.data} for n in graph.nodes],
        "edges": [{"id": e.id, "source": e.source, "target": e.target, "type": e.type, "label": e.label, "animated": e.animated, "data": e.data} for e in graph.edges],
    }


@router.get("/history")
async def get_history(
    task_id: str | None = None,
    from_otdel: str | None = None,
    to_otdel: str | None = None,
    status: str | None = None,
):
    """Get approval history with optional filters."""
    records = svc.list_history(task_id=task_id, from_otdel=from_otdel, to_otdel=to_otdel, status=status)

    # Resolve otdel names for display
    try:
        from ..agents.manager import load_otdels as _load_otdels
        otdels_list = _load_otdels()
        otdel_names: dict[str, str] = {}
        if isinstance(otdels_list, list):
            otdel_names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list}
        elif isinstance(otdels_list, dict):
            otdel_names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list.get("otdels", [])}
    except Exception:
        otdel_names = {}

    return {"history": [
        {
            "id": r.id,
            "task_id": r.task_id,
            "from": r.from_otdel,
            "from_name": otdel_names.get(r.from_otdel, r.from_otdel),
            "to": r.to_otdel,
            "to_name": otdel_names.get(r.to_otdel, r.to_otdel),
            "connection_id": r.connection_id,
            "reason": r.reason,
            "report": r.report,
            "status": r.status.value,
            "timestamp": r.timestamp.isoformat(),
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "resolution": r.resolution,
        }
        for r in records
    ]}


@router.put("/positions")
async def update_positions(req: PositionsUpdate):
    """Save canvas node positions."""
    svc.save_positions(req.positions, req.viewport)
    return {"ok": True}


@router.post("/escalate")
async def approve(req: ApprovalCreate):
    """Escalate a task to another department."""
    record = svc.escalate_task(
        task_id=req.task_id,
        from_otdel=req.get_from(),
        to_otdel=req.get_to(),
        reason=req.reason,
        report=req.report,
    )
    if not record:
        raise HTTPException(404, "No approval connection found between these departments")
    return {
        "id": record.id,
        "task_id": record.task_id,
        "from": record.from_otdel,
        "to": record.to_otdel,
        "status": record.status.value,
    }


@router.put("/{conn_id}")
async def update_connection(conn_id: str, req: ConnectionUpdate):
    """Update a connection."""
    updates = req.model_dump(exclude_none=True)
    conn = svc.update_connection(conn_id, updates)
    if not conn:
        raise HTTPException(404, f"Connection not found: {conn_id}")
    return svc._conn_to_dict(conn)


@router.delete("/{conn_id}")
async def delete_connection(conn_id: str):
    """Delete a connection (Clean Delete)."""
    ok = svc.delete_connection(conn_id)
    if not ok:
        raise HTTPException(404, f"Connection not found: {conn_id}")
    return {"ok": True}


@router.put("/history/{approval_id}/complete")
async def complete_approval(approval_id: str, req: ApprovalComplete):
    """Mark an approval as completed."""
    ok = svc.complete_approval(approval_id, req.resolution)
    if not ok:
        raise HTTPException(404, f"Approval not found: {approval_id}")
    return {"ok": True}
