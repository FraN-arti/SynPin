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


class BulkActionRequest(BaseRequest):
    """Bulk delete or archive tasks by IDs."""
    task_ids: list[str]
    action: str = "delete"  # "delete" or "archive"


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

    # Use configured default column if no status specified
    initial_status = TaskStatus.BACKLOG
    if req.status:
        try:
            initial_status = TaskStatus(req.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {req.status}")
    else:
        # Check widget config for default_column
        try:
            from ..kanban.config import load_widget, load_columns
            widget = load_widget()
            if widget.default_column:
                cols = load_columns()
                target_col = next((c for c in cols if c.id == widget.default_column), None)
                if target_col and target_col.status:
                    try:
                        initial_status = TaskStatus(target_col.status)
                    except ValueError:
                        pass  # fallback to BACKLOG
        except Exception:
            pass  # fallback to BACKLOG

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

    # Parse #DepartmentID references from description
    from ..kanban.models import parse_department_refs
    refs = parse_department_refs(req.description)
    if refs:
        task.escalation_reason = f"Referenced departments: {', '.join(refs)}"
        svc.save_task(task)

    # Auto-assign head from otdel if department is an otdel ID
    if req.department:
        try:
            from ..agents.manager import load_otdels
            otdels = load_otdels()
            for o in otdels:
                otdel_id = o.get("otdelid") or o.get("id") or o.get("departmentsid") or ""
                if otdel_id == req.department:
                    head_slug = o.get("head", "")
                    if head_slug:
                        from ..kanban.models import HeadAssignment
                        task.assigned_head = head_slug
                        svc.save_task(task)
                    break
        except Exception:
            pass  # Non-critical — task is still created

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
        # Resolve the requested status to a valid TaskStatus.
        # Three input shapes are supported:
        #   1. A valid TaskStatus enum value (e.g. 'in_progress').
        #      Used by older clients / the KanbanBoard drag-drop.
        #   2. None — we treat this as 'no specific status requested'
        #      and fall back to the column the task is currently in,
        #      so a stray null PATCH is a no-op rather than a move.
        #   3. A column.id — used by custom user-added columns. The
        #      backend looks up the column and uses ITS status. This
        #      is the path that fixes 'drag into READ does nothing':
        #      the UI now sends the column id, and we route through
        #      it instead of dropping the task into TODO.
        # Anything else returns 400 with the list of valid enum
        # values and the column ids currently in use.
        from synpin.kanban.models import TaskStatus
        from synpin.kanban.config import load_columns
        requested = req.status
        if requested is None:
            # No-op: leave task where it is. This used to silently
            # coerce to TODO, which sent user-added-column drags
            # into the Архив column. Now we treat None as a null-op
            # so a future frontend bug (sending null) can't lose work.
            new_status = None
        elif requested in {s.value for s in TaskStatus}:
            new_status = TaskStatus(requested)
        else:
            # Maybe it's a column id?
            cols = load_columns()
            col_match = next((c for c in cols if c.id == requested), None)
            if col_match is not None and col_match.status:
                # Column exists AND has a TaskStatus mapping — use it.
                new_status = TaskStatus(col_match.status)
            elif col_match is not None:
                # Column exists but has no status mapping. The user
                # is dropping a task into a custom user-added column
                # whose status is None — a perfectly valid action,
                # we just don't know which TaskStatus bucket to use.
                # Fall back to TODO so the move succeeds. We log a
                # warning so the user can be told to set a status
                # in the Settings UI for this column.
                from synpin.kanban.models import TaskStatus as _TS
                import logging
                logging.getLogger("synpin.kanban").warning(
                    "[kanban] column '%s' (label=%r) has no status; "
                    "drag-drop will fall back to TODO. Set a status in "
                    "Settings → Kanban → Columns to route tasks properly.",
                    col_match.id, col_match.label,
                )
                new_status = _TS.TODO
            else:
                # Not a TaskStatus, not a column id — it's a true
                # typo or stale config. 400 with a clear list.
                valid = sorted(s.value for s in TaskStatus)
                col_ids = [c.id for c in cols]
                raise HTTPException(
                    400,
                    f"Unknown status '{requested}'. "
                    f"Use one of {valid} (TaskStatus) or one of {col_ids} (column id).",
                )
        if new_status is not None and new_status != task.status:
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


class AddHistoryRequest(BaseRequest):
    actor: str = "head"
    action: str
    detail: str = ""
    target_department: str | None = None
    target_agent: str | None = None


@router.post("/tasks/{task_id}/history")
def add_history(task_id: str, req: AddHistoryRequest) -> dict:
    """Add a history entry to the task."""
    svc = _get_service()
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    task.add_history(
        actor=req.actor,
        action=req.action,
        detail=req.detail,
        target_department=req.target_department,
        target_agent=req.target_agent,
    )
    svc.save_task(task)
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


@router.get("/stats/extended")
def kanban_stats_extended() -> dict:
    """Extended statistics for charts and analytics."""
    from datetime import datetime, timedelta, timezone
    svc = _get_service()
    all_tasks = svc.list_tasks()

    # ── Basic counts ──
    by_status: dict[str, int] = {}
    by_department: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for t in all_tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        if t.department:
            by_department[t.department] = by_department.get(t.department, 0) + 1
        by_priority[t.priority.value] = by_priority.get(t.priority.value, 0) + 1

    # ── Overdue tasks ──
    now = datetime.now(timezone.utc)
    overdue = 0
    for t in all_tasks:
        if t.deadline and t.status.value not in ("done", "blocked"):
            dl = t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)
            if dl < now:
                overdue += 1

    # ── Daily completions (last 30 days) ──
    daily_completed: dict[str, int] = {}
    daily_created: dict[str, int] = {}
    for t in all_tasks:
        if t.completed_at:
            day = t.completed_at.strftime("%Y-%m-%d")
            daily_completed[day] = daily_completed.get(day, 0) + 1
        if t.created_at:
            day = t.created_at.strftime("%Y-%m-%d")
            daily_created[day] = daily_created.get(day, 0) + 1

    # Fill missing days (last 30)
    timeline = []
    for i in range(30, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        timeline.append({
            "date": day,
            "completed": daily_completed.get(day, 0),
            "created": daily_created.get(day, 0),
        })

    # ── Average completion time (hours) ──
    completion_times = []
    for t in all_tasks:
        if t.completed_at and t.created_at:
            delta = t.completed_at - t.created_at
            completion_times.append(delta.total_seconds() / 3600)
    avg_completion_hours = round(sum(completion_times) / len(completion_times), 1) if completion_times else 0

    # ── Department names mapping (tasks use otdel IDs) ──
    try:
        from ..agents.manager import load_otdels
        otdels_raw = load_otdels()
        otdels_list = otdels_raw if isinstance(otdels_raw, list) else otdels_raw.get("otdels", [])
        dept_map = {}
        for o in otdels_list:
            oid = o.get("otdelid", "")
            name = o.get("name", "")
            if oid and name:
                dept_map[oid] = name
    except Exception:
        dept_map = {}

    by_department_named = {}
    for dept_id, count in by_department.items():
        # Handle both ID and name (some tasks store name directly)
        name = dept_map.get(dept_id, dept_id)
        # Deduplicate: if name already exists, merge counts
        if name in by_department_named:
            by_department_named[name] += count
        else:
            by_department_named[name] = count

    return {
        "total": len(all_tasks),
        "by_status": by_status,
        "by_department": by_department_named,
        "by_priority": by_priority,
        "overdue": overdue,
        "avg_completion_hours": avg_completion_hours,
        "timeline": timeline,
        "active": by_status.get("in_progress", 0) + by_status.get("review", 0),
        "done": by_status.get("done", 0),
    }


# ── Bulk Actions ──────────────────────────────────────────────────────────────

@router.post("/tasks/bulk")
def bulk_action(req: BulkActionRequest) -> dict:
    """Bulk delete or archive tasks by IDs.

    Returns count of successfully processed tasks.
    """
    svc = _get_service()
    processed = 0
    errors = []

    for task_id in req.task_ids:
        try:
            if req.action == "archive":
                ok = svc.archive_task(task_id)
            elif req.action == "delete":
                ok = svc.delete_task(task_id)
            else:
                raise HTTPException(400, f"Unknown action: {req.action}. Use 'delete' or 'archive'.")
            if ok:
                processed += 1
            else:
                errors.append(f"{task_id}: not found")
        except Exception as e:
            errors.append(f"{task_id}: {e}")

    # Broadcast board refresh
    try:
        from ..kanban.service import _broadcast
        _broadcast({"type": "kanban:task_updated", "bulk": True, "action": req.action, "count": processed})
    except Exception:
        pass

    return {
        "status": "ok",
        "action": req.action,
        "processed": processed,
        "total_requested": len(req.task_ids),
        "errors": errors,
    }
