"""Kanban REST API — CRUD for tasks on the global board."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import Field

from ..kanban.service import KanbanService
from ..kanban.models import Priority, TaskStatus
from ._base import BaseRequest

router = APIRouter(prefix="/api/kanban", tags=["kanban"])

# Singleton service (created on first request)
_service: KanbanService | None = None


def _get_service() -> KanbanService:
    global _service
    if _service is None:
        _service = KanbanService()
    return _service


# ── Request models ───────────────────────────────────────────────────────────

class CreateTaskRequest(BaseRequest):
    title: str
    department: str = ""
    description: str = ""
    priority: str = "medium"
    status: str | None = None
    deadline: str | None = None
    tags: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)


class UpdateTaskRequest(BaseRequest):
    title: str | None = None
    description: str | None = None
    department: str | None = None
    priority: str | None = None
    deadline: str | None = None
    tags: list[str] | None = None
    status: str | None = None  # column move: backlog/todo/in_progress/review/done/blocked


class AssignHeadRequest(BaseRequest):
    head_agent_id: str


class AssignWorkerRequest(BaseRequest):
    agent_id: str
    subtask: str


class ActionRequest(BaseRequest):
    actor: str = "system"
    detail: str = ""


class SummonRequest(BaseRequest):
    target_department: str
    reason: str
    actor: str = "head"


class EscalateRequest(BaseRequest):
    reason: str
    report: str


class RejectRequest(BaseRequest):
    feedback: str
    actor: str = "head"


class AddResultRequest(BaseRequest):
    file_path: str
    description: str = ""
    created_by: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _task_to_dict(task: Any) -> dict:
    """Convert task model to JSON-safe dict."""
    d = task.model_dump(mode="json")
    # Convert datetime strings for frontend
    for key in ("created_at", "updated_at", "completed_at", "deadline"):
        if d.get(key) and isinstance(d[key], str):
            pass  # Already string in JSON mode
    return d


def _parse_deadline(deadline: str | None) -> datetime | None:
    """Parse deadline string to datetime."""
    if not deadline:
        return None
    try:
        return datetime.fromisoformat(deadline)
    except ValueError:
        return None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks(
    status: str | None = None,
    department: str | None = None,
) -> list[dict]:
    """List all tasks with optional filters."""
    svc = _get_service()
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    tasks = svc.list_tasks(status=task_status, department=department)
    return [_task_to_dict(t) for t in tasks]


@router.get("/tasks/board")
def get_board() -> dict[str, list[dict]]:
    """Get tasks grouped by status (for Kanban board rendering)."""
    svc = _get_service()
    grouped = svc.list_by_status()
    return {k: [_task_to_dict(t) for t in v] for k, v in grouped.items()}


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    """Get a single task by ID."""
    svc = _get_service()
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks")
def create_task(req: CreateTaskRequest) -> dict:
    """Create a new task."""
    svc = _get_service()
    priority = Priority.MEDIUM
    try:
        priority = Priority(req.priority)
    except ValueError:
        pass

    initial_status = TaskStatus.BACKLOG
    if req.status:
        try:
            initial_status = TaskStatus(req.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {req.status}")

    task = svc.create_task(
        title=req.title,
        department=req.department,
        description=req.description,
        priority=priority,
        status=initial_status,
        deadline=_parse_deadline(req.deadline),
        tags=req.tags,
        required_skills=req.required_skills,
    )
    return _task_to_dict(task)


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, req: UpdateTaskRequest) -> dict:
    """Update task fields."""
    svc = _get_service()
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")

    if req.title is not None:
        task.title = req.title
    if req.description is not None:
        task.description = req.description
    if req.department is not None:
        task.department = req.department
        task.current_department = req.department
    if req.priority is not None:
        try:
            task.priority = Priority(req.priority)
        except ValueError:
            pass
    if req.deadline is not None:
        task.deadline = _parse_deadline(req.deadline)
    if req.tags is not None:
        task.tags = req.tags
    if req.status is not None:
        # Validate it's a known TaskStatus, then move via the model method
        # so history is recorded (the UI relies on this for the activity log).
        try:
            new_status = TaskStatus(req.status)
        except ValueError:
            raise HTTPException(400, f"Unknown status: {req.status}")
        if new_status != task.status:
            task.move_to(new_status, actor="drag-drop")

    svc.save_task(task)
    return _task_to_dict(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> dict:
    """Delete a task."""
    svc = _get_service()
    ok = svc.delete_task(task_id)
    if not ok:
        raise HTTPException(404, f"Task {task_id} not found")
    return {"status": "ok", "deleted": task_id}


@router.post("/tasks/{task_id}/archive")
def archive_task(task_id: str) -> dict:
    """Archive a task."""
    svc = _get_service()
    ok = svc.archive_task(task_id)
    if not ok:
        raise HTTPException(404, f"Task {task_id} not found")
    return {"status": "ok", "archived": task_id}


# ── Actions ──────────────────────────────────────────────────────────────────

@router.post("/tasks/{task_id}/assign-head")
def assign_head(task_id: str, req: AssignHeadRequest) -> dict:
    """Assign a head agent to manage the task."""
    svc = _get_service()
    task = svc.assign_head(task_id, req.head_agent_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/assign-worker")
def assign_worker(task_id: str, req: AssignWorkerRequest) -> dict:
    """Assign a worker to a subtask."""
    svc = _get_service()
    task = svc.assign_worker(task_id, req.agent_id, req.subtask)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/start")
def start_work(task_id: str, req: ActionRequest = ActionRequest()) -> dict:
    """Mark task as in progress."""
    svc = _get_service()
    task = svc.start_work(task_id, actor=req.actor)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/submit-review")
def submit_for_review(task_id: str, req: ActionRequest = ActionRequest()) -> dict:
    """Worker submits completed work for review."""
    svc = _get_service()
    task = svc.submit_for_review(task_id, actor=req.actor)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/approve")
def approve(task_id: str, req: ActionRequest = ActionRequest()) -> dict:
    """Head approves the work."""
    svc = _get_service()
    task = svc.approve(task_id, actor=req.actor)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/reject")
def reject(task_id: str, req: RejectRequest) -> dict:
    """Head rejects work — sends back for revision."""
    svc = _get_service()
    task = svc.reject(task_id, feedback=req.feedback, actor=req.actor)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/summon")
def summon(task_id: str, req: SummonRequest) -> dict:
    """Transfer task to another department."""
    svc = _get_service()
    task = svc.summon(
        task_id,
        target_department=req.target_department,
        reason=req.reason,
        actor=req.actor,
    )
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/escalate")
def escalate(task_id: str, req: EscalateRequest) -> dict:
    """Escalate task to Council of Directors."""
    svc = _get_service()
    task = svc.escalate(task_id, reason=req.reason, report=req.report)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/escalate-human")
def escalate_to_human(task_id: str, req: ActionRequest = ActionRequest()) -> dict:
    """Escalate task to the human user."""
    svc = _get_service()
    task = svc.escalate_to_human(task_id, reason=req.detail or "Needs human input")
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/result")
def add_result(task_id: str, req: AddResultRequest) -> dict:
    """Add a result artifact to the task."""
    svc = _get_service()
    task = svc.add_result(
        task_id,
        file_path=req.file_path,
        description=req.description,
        created_by=req.created_by,
    )
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


# ── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats")
def kanban_stats() -> dict:
    """Get Kanban board statistics."""
    svc = _get_service()
    all_tasks = svc.list_tasks()

    by_status: dict[str, int] = {}
    by_department: dict[str, int] = {}
    by_priority: dict[str, int] = {}

    for t in all_tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        if t.department:
            by_department[t.department] = by_department.get(t.department, 0) + 1
        by_priority[t.priority.value] = by_priority.get(t.priority.value, 0) + 1

    return {
        "total": len(all_tasks),
        "by_status": by_status,
        "by_department": by_department,
        "by_priority": by_priority,
    }
