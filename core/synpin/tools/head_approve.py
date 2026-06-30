"""Head Protocol: Approve/transfer tasks to other departments via connections."""
from __future__ import annotations

from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool



@register_tool(
    name='head_approve',
    description='Передать задачу в другой отдел через связь (утверждение/делегирование). Используй когда задача требует проверки или выполнения другим отделом.',
    category='other',
    scope='head',
    dangerous=False,
)
async def head_approve(params: dict[str, Any]) -> ToolResult:
    """
    Transfer a task to another department through a connection.

    Params:
        otdel_id: str (injected by execute_tool) — current department
        task_id: str (required) — kanban task ID (T-xxx)
        target_otdel: str (optional) — target department slug.
                      If omitted, auto-detects approval connection.
        reason: str (required) — why escalating
        report: str (optional) — detailed report for target department

    Returns:
        {approval_id, from, to, task_id, status, message}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required (should be injected by system)")

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required (e.g. 'T-001')")

    reason = params.get("reason", "")
    if not reason:
        return make_error("reason required — explain why you're escalating")

    target_otdel = params.get("target_otdel") or None
    report = params.get("report", "")

    try:
        from ..connections.service import escalate_task

        record = escalate_task(
            task_id=task_id,
            from_otdel=otdel_id,
            to_otdel=target_otdel,
            reason=reason,
            report=report,
        )

        if not record:
            # Find available connections for better error message
            from ..connections.config import load_connections
            from ..connections.models import ConnectionType
            connections = load_connections()
            available = [
                c.to_otdel for c in connections
                if c.from_otdel == otdel_id and c.type == ConnectionType.APPROVAL and c.active
            ]
            if available:
                return make_error(
                    f"No approval connection to '{target_otdel}'. "
                    f"Available targets from {otdel_id}: {available}"
                )
            else:
                return make_error(
                    f"No approval connections from {otdel_id}. "
                    f"Create a connection in Settings → Связи first."
                )

        return make_success({
            "approval_id": record.id,
            "from": record.from_otdel,
            "to": record.to_otdel,
            "task_id": record.task_id,
            "status": record.status.value,
            "message": (
                f"Task {task_id} transferred from {record.from_otdel} to {record.to_otdel}. "
                f"Reason: {reason}"
            ),
        })

    except Exception as e:
        return make_error(f"Approval failed: {e}")


async def head_approval_status(params: dict[str, Any]) -> ToolResult:
    """
    Check approval status or list recent approvals.

    Params:
        otdel_id: str (injected by execute_tool)
        task_id: str (optional) — filter by task
        status: str (optional) — filter by status (pending/completed/rejected)

    Returns:
        {approvals: [...]}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required (should be injected by system)")

    task_id = params.get("task_id") or None
    status = params.get("status") or None

    try:
        from ..connections.service import list_history

        records = list_history(
            task_id=task_id,
            from_otdel=otdel_id,
            status=status,
        )

        approvals = [
            {
                "id": r.id,
                "task_id": r.task_id,
                "from": r.from_otdel,
                "to": r.to_otdel,
                "reason": r.reason,
                "status": r.status.value,
                "timestamp": r.timestamp.isoformat(),
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                "resolution": r.resolution,
            }
            for r in records
        ]

        return make_success({"approvals": approvals})

    except Exception as e:
        return make_error(f"Failed to get approval status: {e}")


__all__ = ["head_approve", "head_approval_status"]
