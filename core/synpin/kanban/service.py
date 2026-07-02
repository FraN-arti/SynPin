"""Kanban service — manages task lifecycle, assignment, Summon, and escalation.

This is the business logic layer between the API and the task data.
Broadcasts WebSocket events on every task change for live board updates.
"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from ..time import now as _now
from ..paths import get_tasks_dir
from .models import (
    ActionType,
    Priority,
    Task,
    TaskStatus,
    create_task,
    load_all_tasks,
    load_task,
    save_task,
)

# ── WebSocket broadcast helper ───────────────────────────────────────────────

def _broadcast(event: dict) -> None:
    """Thread-safe broadcast via centralized ws_broadcast module."""
    from ..ws_broadcast import broadcast as _ws_broadcast
    _ws_broadcast(event)

# ── Directory resolution ─────────────────────────────────────────────────────


def _get_tasks_dir() -> Path:
    """Get tasks directory, create if needed.

    Uses paths.get_tasks_dir() as the single source of truth: in dev
    mode that's core/synpin/data/tasks/, in prod it's ~/.synpin/data/tasks/.
    Both were already the targets of the previous hand-rolled logic.
    """
    d = get_tasks_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Next ID generator ────────────────────────────────────────────────────────

def _next_task_id() -> str:
    """Generate next task ID: T-0001, T-0002, ..."""
    tasks_dir = _get_tasks_dir()
    existing = sorted(tasks_dir.glob("T-*.yaml"))
    if not existing:
        return "T-0001"

    # Parse last number
    last_id = existing[-1].stem  # "T-0005"
    num = int(last_id.split("-")[1]) + 1
    return f"T-{num:04d}"


# ── CRUD Operations ──────────────────────────────────────────────────────────

class KanbanService:
    """Service for managing tasks on the global Kanban board."""

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or _get_tasks_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @property
    def tasks_dir(self) -> Path:
        return self._data_dir

    # ── Create ────────────────────────────────────────────────────────

    def create_task(
        self,
        title: str,
        department: str = "",
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        status: TaskStatus = TaskStatus.BACKLOG,
        deadline: datetime | None = None,
        tags: list[str] | None = None,
        required_skills: list[str] | None = None,
        project_id: str | None = None,
        project_goal_id: str | None = None,
    ) -> Task:
        """Create a new task and save to disk."""
        with self._lock:
            task_id = _next_task_id()
            task = create_task(
                title=title,
                department=department,
                description=description,
                priority=priority,
                status=status,
                deadline=deadline,
                tags=tags,
                required_skills=required_skills,
                task_id=task_id,
                project_id=project_id,
                project_goal_id=project_goal_id,
            )
            save_task(task, self._data_dir)
            # Broadcast new task to all connected clients
            _broadcast({
                "type": "kanban:task_created",
                "task": task.model_dump(mode="json"),
            })
            return task

    # ── Read ──────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task | None:
        """Load a single task by ID."""
        filepath = self._data_dir / f"{task_id}.yaml"
        if not filepath.exists():
            return None
        return load_task(filepath)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        department: str | None = None,
        assigned_head: str | None = None,
        project_id: str | None = None,
    ) -> list[Task]:
        """List all tasks with optional filters."""
        tasks = load_all_tasks(self._data_dir)

        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if department:
            tasks = [t for t in tasks if t.department == department]
        if assigned_head:
            tasks = [t for t in tasks if t.assigned_head == assigned_head]
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]

        return tasks

    def list_by_status(self) -> dict[str, list[Task]]:
        """Group tasks by status (for Kanban board rendering)."""
        tasks = load_all_tasks(self._data_dir)
        groups: dict[str, list[Task]] = {s.value: [] for s in TaskStatus}
        for task in tasks:
            groups[task.status.value].append(task)
        return groups

    # ── Update ────────────────────────────────────────────────────────

    def save_task(self, task: Task) -> Path:
        """Save task changes to disk and broadcast update."""
        with self._lock:
            task.updated_at = _now()
            path = save_task(task, self._data_dir)
            # Broadcast live update to all connected clients
            _broadcast({
                "type": "kanban:task_updated",
                "task": task.model_dump(mode="json"),
            })
            return path

    def assign_head(self, task_id: str, head_agent_id: str) -> Task | None:
        """Assign a head agent to manage the task."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.assigned_head = head_agent_id
        task.move_to(TaskStatus.TODO, actor=head_agent_id)
        self.save_task(task)
        return task

    def assign_worker(self, task_id: str, agent_id: str, subtask: str) -> Task | None:
        """Assign a worker to a subtask."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.assign_worker(agent_id, subtask)
        if task.status == TaskStatus.TODO:
            task.move_to(TaskStatus.IN_PROGRESS, actor=task.assigned_head or "system")
        self.save_task(task)
        return task

    def start_work(self, task_id: str, actor: str = "head") -> Task | None:
        """Mark task as in progress."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.move_to(TaskStatus.IN_PROGRESS, actor=actor)
        self.save_task(task)
        return task

    def submit_for_review(self, task_id: str, actor: str = "worker") -> Task | None:
        """Worker submits completed work for head review."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.move_to(TaskStatus.REVIEW, actor=actor)
        self.save_task(task)
        return task

    def approve(self, task_id: str, actor: str = "head") -> Task | None:
        """Head approves the work — task is done."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.move_to(TaskStatus.DONE, actor=actor)
        self.save_task(task)
        return task

    def reject(self, task_id: str, feedback: str, actor: str = "head") -> Task | None:
        """Head rejects work — sends back for revision."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.send_to_revision(feedback, actor=actor)
        self.save_task(task)
        return task

    # ── Summon (cross-department transfer) ────────────────────────────

    def summon(
        self,
        task_id: str,
        target_department: str,
        reason: str,
        actor: str = "head",
    ) -> Task | None:
        """Transfer task to another department via Summon."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.summon(target_department, reason, actor=actor)
        self.save_task(task)
        return task

    # ── Escalation ────────────────────────────────────────────────────

    def escalate(
        self,
        task_id: str,
        reason: str,
        report: str,
    ) -> Task | None:
        """Escalate task to Council of Directors."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.escalate(reason, report)
        self.save_task(task)
        return task

    def escalate_to_human(
        self,
        task_id: str,
        reason: str,
    ) -> Task | None:
        """Escalate task to the human user (Arthur)."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.status = TaskStatus.BLOCKED
        task.add_history(
            actor="council",
            action=ActionType.ESCALATED_TO_HUMAN,
            detail=reason,
        )
        self.save_task(task)
        return task

    # ── Results ───────────────────────────────────────────────────────

    def add_result(
        self,
        task_id: str,
        file_path: str,
        description: str = "",
        created_by: str = "",
    ) -> Task | None:
        """Add a result artifact to the task."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.add_result(file_path, description, created_by)
        self.save_task(task)
        return task

    # ── Delete ────────────────────────────────────────────────────────

    def archive_task(self, task_id: str) -> bool:
        """Archive a task.

        If a column mapped to ARCHIVE status exists, moves the task
        to ARCHIVE status. Otherwise falls back to file-level archive.
        """
        from .config import load_settings, load_columns

        task = self.get_task(task_id)
        if task is None:
            return False

        # Auto-discover archive column from status mapping
        cols = load_columns()
        archive_col = next((c for c in cols if c.status == TaskStatus.ARCHIVE.value), None)

        # Legacy: also check explicit archive_column setting
        if not archive_col:
            settings = load_settings()
            if settings.archive_column:
                archive_col = next((c for c in cols if c.id == settings.archive_column), None)

        if archive_col:
            try:
                new_status = TaskStatus(archive_col.status)
            except ValueError:
                new_status = None
            if new_status:
                task.move_to(new_status, actor="system")
                self.save_task(task)
                return True

        # Fallback: file-level archive
        filepath = self._data_dir / f"{task_id}.yaml"
        if not filepath.exists():
            return False

        archive_dir = self._data_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        with self._lock:
            filepath.rename(archive_dir / filepath.name)
        return True

    def delete_task(self, task_id: str) -> bool:
        """Permanently delete a task."""
        filepath = self._data_dir / f"{task_id}.yaml"
        if not filepath.exists():
            return False
        with self._lock:
            filepath.unlink()
        _broadcast({
            "type": "kanban:task_deleted",
            "task_id": task_id,
        })
        return True
