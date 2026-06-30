"""Head Protocol: Reline — return task to previous department with remarks."""
from __future__ import annotations

from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool



@register_tool(
    name='head_reline',
    description='Вернуть задачу предыдущему отделу с замечаниями (релайн). Используй когда задача выполнена некачественно или не соответствует требованиям.',
    category='other',
    scope='head',
    dangerous=False,
)
async def head_reline(params: dict[str, Any]) -> ToolResult:
    """
    Return a task to the previous department with review remarks (reline).

    Reline is the reverse of approve/delegate:
    - You received a task for approval/delegation
    - You found issues or the task doesn't match requirements
    - You send it BACK with specific remarks on what needs fixing

    Params:
        otdel_id: str (injected by execute_tool) — current department
        task_id: str (required) — kanban task ID (T-xxx)
        remarks: str (required) — what needs to be fixed/improved
        severity: str (optional) — low/medium/high (default: medium)

    Returns:
        {reline_id, from, to, task_id, status, message}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required (should be injected by system)")

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required (e.g. 'T-001')")

    remarks = params.get("remarks", "")
    if not remarks:
        return make_error("remarks required — describe what needs to be fixed")

    severity = params.get("severity", "medium")

    try:
        from ..kanban.service import KanbanService
        from ..kanban.models import TaskStatus, ActionType

        svc = KanbanService()
        task = svc.get_task(task_id)
        if not task:
            return make_error(f"Task {task_id} not found")

        # Find where to return — use summon_chain (previous department)
        if not task.summon_chain:
            return make_error(
                f"Task {task_id} has no summon chain — cannot determine where to return. "
                f"Use head_approve to send it somewhere first."
            )

        # Get previous department from summon_chain (last entry)
        target_otdel = task.summon_chain[-1]

        # Move task back
        task.current_department = target_otdel
        task.department = target_otdel

        # Remove the last entry from summon_chain (we're going back)
        task.summon_chain = task.summon_chain[:-1]

        # Record reline in task history
        task.add_history(
            actor=otdel_id,
            action=ActionType.REWORK,
            detail=f"РЕЛАЙН [{severity}]: {remarks}",
            target_department=target_otdel,
        )

        # Move to TODO in target department
        task.move_to(TaskStatus.TODO, actor="reline")

        svc.save_task(task)

        # Record in approval history
        from ..connections.config import add_history_record
        from ..connections.models import ApprovalStatus

        record = add_history_record(
            task_id=task_id,
            from_otdel=otdel_id,
            to_otdel=target_otdel,
            connection_id="reline",
            reason=f"РЕЛАЙН: {remarks}",
            report=f"Severity: {severity}. Task returned for rework.",
        )

        # Broadcast
        from ..agents.manager import load_otdels as _load_otdels
        try:
            otdels_list = _load_otdels()
            _names: dict[str, str] = {}
            if isinstance(otdels_list, list):
                _names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list}
            elif isinstance(otdels_list, dict):
                _names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list.get("otdels", [])}
        except Exception:
            _names = {}

        from .service import _broadcast
        _broadcast({
            "type": "connections:approval_started",
            "approval": {
                "id": record.id if record else "reline",
                "task_id": task_id,
                "from": otdel_id,
                "from_name": _names.get(otdel_id, otdel_id),
                "to": target_otdel,
                "to_name": _names.get(target_otdel, target_otdel),
                "connection_id": "reline",
                "reason": f"РЕЛАЙН: {remarks}",
            },
        })

        return make_success({
            "reline_id": record.id if record else "reline",
            "from": otdel_id,
            "to": target_otdel,
            "task_id": task_id,
            "status": "relined",
            "message": (
                f"Task {task_id} returned from {otdel_id} to {target_otdel}. "
                f"Remarks: {remarks}"
            ),
        })

    except Exception as e:
        return make_error(f"Reline failed: {e}")


__all__ = ["head_reline"]
