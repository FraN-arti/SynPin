"""Head Protocol: Worker reports a blocker to head."""
from __future__ import annotations

from typing import Any

from ._registry import register_tool
from .base import ToolResult, make_success, make_error


# In-memory storage for blockers per otdel
_blockers: dict[str, list[dict]] = {}



@register_tool(
    name='head_block',
    description='Сообщить голове о блокере. Используй когда застрял и нужна помощь.',
    category='other',
    scope='head',
    dangerous=False,
)
async def head_block(params: dict[str, Any]) -> ToolResult:
    """
    Worker reports a blocker to head.
    
    Params:
        otdel_id: str (injected)
        reason: str - what's blocking the work
        severity: str - low|medium|high|critical (default: medium)
        context: str - additional context about the blocker
        
    Returns:
        {blocker_id, message, guidance}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required")
    
    reason = params.get("reason", "")
    if not reason:
        return make_error("reason required")
    
    severity = params.get("severity", "medium")
    valid_severities = ("low", "medium", "high", "critical")
    if severity not in valid_severities:
        return make_error(f"Invalid severity. Must be one of: {', '.join(valid_severities)}")
    
    context = params.get("context", "")
    
    # Generate blocker ID
    import uuid
    blocker_id = f"blocker-{uuid.uuid4().hex[:8]}"
    
    # Store blocker
    if otdel_id not in _blockers:
        _blockers[otdel_id] = []

    blocker = {
        "id": blocker_id,
        "reason": reason,
        "severity": severity,
        "context": context,
        "status": "open",  # open | resolved | escalated
    }
    _blockers[otdel_id].append(blocker)

    # Record in task history if task_id provided
    task_id = params.get("task_id", "")
    if task_id:
        try:
            from ..kanban.service import KanbanService
            from ..kanban.models import TaskStatus, ActionType
            svc = KanbanService()
            task = svc.get_task(task_id)
            if task:
                task.add_history(
                    actor=otdel_id,
                    action=ActionType.COMMENT,
                    detail=f"BLOCK [{severity}]: {reason}",
                )
                if severity in ("high", "critical"):
                    task.move_to(TaskStatus.BLOCKED, actor="head_block")
                svc.save_task(task)
        except Exception:
            pass
    
    # Severity-based guidance
    severity_guidance = {
        "low": "Minor issue. Consider resolving yourself or asking a colleague.",
        "medium": "Moderate blocker. May need head assistance.",
        "high": "Significant blocker. Head should decide: help, reassign, or escalate.",
        "critical": "Critical blocker. Immediate attention required.",
    }
    
    guidance = (
        f"Blocker reported: {blocker_id}\n"
        f"Severity: {severity}\n"
        f"Reason: {reason}\n"
        f"{severity_guidance[severity]}\n"
        f"Use head_decide or head_delegate to resolve."
    )
    
    return make_success({
        "blocker_id": blocker_id,
        "severity": severity,
        "message": f"Blocker {blocker_id} reported to head",
        "guidance": guidance,
    })


def get_blockers(otdel_id: str) -> list[dict]:
    """Get all blockers for an otdel."""
    return _blockers.get(otdel_id, [])


def resolve_blocker(otdel_id: str, blocker_id: str) -> bool:
    """Mark a blocker as resolved."""
    if otdel_id in _blockers:
        for b in _blockers[otdel_id]:
            if b["id"] == blocker_id:
                b["status"] = "resolved"
                return True
    return False


__all__ = ["head_block", "get_blockers", "resolve_blocker"]
