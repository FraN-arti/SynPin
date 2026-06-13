"""Kanban Task models — Pydantic schemas for the global task board.

Each task is stored as a YAML file in kanban/tasks/T-{id}.yaml.
The model handles validation, serialization, and business logic.
"""
from __future__ import annotations

import yaml
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    """Lifecycle stages of a task on the Kanban board."""
    BACKLOG = "backlog"        # Created, not yet assigned
    TODO = "todo"              # Assigned to department, awaiting start
    READY = "ready"            # User-defined intermediate status (e.g. queued for an agent)
    IN_PROGRESS = "in_progress"  # Agents are working
    REVIEW = "review"          # Work done, head is checking
    REVISION = "revision"      # Sent back for rework
    BLOCKED = "blocked"        # Escalated to Council of Directors
    DONE = "done"              # Completed and accepted


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    """Types of actions recorded in task history."""
    CREATED = "created"
    ACCEPTED = "accepted"
    ASSIGNED = "assigned"
    WORK_STARTED = "work_started"
    WORK_COMPLETED = "work_completed"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"
    SENT_TO_REVISION = "sent_to_revision"
    SUMMONED = "summoned"          # Cross-department transfer
    ESCALATED = "escalated"        # To Council of Directors
    ESCALATED_TO_HUMAN = "escalated_to_human"
    COMMENT = "comment"
    STATUS_CHANGED = "status_changed"
    RESULT_ADDED = "result_added"


# ── Sub-models ───────────────────────────────────────────────────────────────

class HistoryEntry(BaseModel):
    """A single action recorded in the task's live history."""
    timestamp: datetime = Field(default_factory=datetime.now)
    actor: str                  # agent_id, "head", "council", "human"
    action: ActionType
    detail: str = ""
    target_department: str | None = None  # For SUMMONED action
    target_agent: str | None = None       # For ASSIGNED action


class TaskResult(BaseModel):
    """A result artifact produced by task execution."""
    file_path: str              # Path to the output file
    description: str = ""       # What this file contains
    created_by: str = ""        # agent_id who created it


class WorkerAssignment(BaseModel):
    """Assignment of a specific worker to a subtask."""
    agent_id: str
    subtask: str                # Description of what this worker does
    status: str = "pending"     # pending | working | done


# ── Main Task Model ─────────────────────────────────────────────────────────

class Task(BaseModel):
    """
    A single task on the global Kanban board.

    Stored as YAML in kanban/tasks/T-{id}.yaml.
    This is a living document — history grows as the task progresses.
    """
    id: str                                     # T-001, T-002, etc.
    title: str                                  # Short description
    description: str = ""                       # Full context & requirements
    department: str = ""                        # Target department slug
    status: TaskStatus = TaskStatus.BACKLOG
    priority: Priority = Priority.MEDIUM

    # Timeline
    deadline: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None

    # Assignment
    assigned_head: str | None = None            # Head agent_id
    assigned_workers: list[WorkerAssignment] = Field(default_factory=list)

    # History & results
    history: list[HistoryEntry] = Field(default_factory=list)
    results: list[TaskResult] = Field(default_factory=list)

    # Cross-department (Summon)
    summon_chain: list[str] = Field(default_factory=list)  # department slugs
    current_department: str = ""                # Where the task lives now

    # Escalation
    escalation_reason: str | None = None
    escalation_report: str | None = None

    # Metadata
    tags: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)    # Other task IDs

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v.startswith("T-"):
            raise ValueError("Task ID must start with 'T-'")
        return v

    # ── Methods ──────────────────────────────────────────────────────────

    def add_history(
        self,
        actor: str,
        action: ActionType,
        detail: str = "",
        **kwargs: Any,
    ) -> None:
        """Append an entry to the task's live history."""
        entry = HistoryEntry(
            actor=actor,
            action=action,
            detail=detail,
            **kwargs,
        )
        self.history.append(entry)
        self.updated_at = datetime.now()

    def assign_worker(self, agent_id: str, subtask: str) -> None:
        """Assign a worker to a subtask."""
        assignment = WorkerAssignment(agent_id=agent_id, subtask=subtask)
        self.assigned_workers.append(assignment)
        self.add_history(
            actor="head",
            action=ActionType.ASSIGNED,
            detail=f"Assigned to {agent_id}: {subtask}",
            target_agent=agent_id,
        )

    def move_to(self, new_status: TaskStatus, actor: str = "system") -> None:
        """Change task status and record in history."""
        old_status = self.status
        self.status = new_status
        self.add_history(
            actor=actor,
            action=ActionType.STATUS_CHANGED,
            detail=f"{old_status.value} → {new_status.value}",
        )
        if new_status == TaskStatus.DONE:
            self.completed_at = datetime.now()

    def summon(self, target_department: str, reason: str, actor: str = "head") -> None:
        """Transfer task to another department via Summon."""
        self.summon_chain.append(self.current_department)
        self.current_department = target_department
        self.department = target_department
        self.add_history(
            actor=actor,
            action=ActionType.SUMMONED,
            detail=reason,
            target_department=target_department,
        )

    def escalate(self, reason: str, report: str) -> None:
        """Escalate to Council of Directors."""
        self.status = TaskStatus.BLOCKED
        self.escalation_reason = reason
        self.escalation_report = report
        self.add_history(
            actor="head",
            action=ActionType.ESCALATED,
            detail=reason,
        )

    def send_to_revision(self, feedback: str, actor: str = "head") -> None:
        """Send task back to agents for rework."""
        self.status = TaskStatus.REVISION
        self.add_history(
            actor=actor,
            action=ActionType.SENT_TO_REVISION,
            detail=feedback,
        )

    def add_result(self, file_path: str, description: str = "", created_by: str = "") -> None:
        """Record a result artifact."""
        result = TaskResult(
            file_path=file_path,
            description=description,
            created_by=created_by,
        )
        self.results.append(result)
        self.add_history(
            actor=created_by or "system",
            action=ActionType.RESULT_ADDED,
            detail=f"Result: {file_path}",
        )


# ── Factory ──────────────────────────────────────────────────────────────────

def create_task(
    title: str,
    department: str = "",
    description: str = "",
    priority: Priority = Priority.MEDIUM,
    status: TaskStatus = TaskStatus.BACKLOG,
    deadline: datetime | None = None,
    tags: list[str] | None = None,
    required_skills: list[str] | None = None,
    task_id: str | None = None,
) -> Task:
    """Create a new task with initial history entry."""
    task = Task(
        id=task_id or _generate_task_id(),
        title=title,
        description=description,
        department=department,
        current_department=department,
        priority=priority,
        status=status,
        deadline=deadline,
        tags=tags or [],
        required_skills=required_skills or [],
    )
    task.add_history(
        actor="council",
        action=ActionType.CREATED,
        detail=f"Task created for department: {department or 'unassigned'}",
    )
    return task


def _generate_task_id() -> str:
    """Generate next task ID based on existing tasks."""
    # This will be improved when we have the service layer
    import random
    num = random.randint(100, 9999)
    return f"T-{num:04d}"


# ── YAML I/O ─────────────────────────────────────────────────────────────────

def task_to_yaml(task: Task) -> str:
    """Serialize a task to YAML string."""
    return yaml.dump(
        task.model_dump(mode="json"),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def task_from_yaml(yaml_str: str) -> Task:
    """Deserialize a task from YAML string."""
    data = yaml.safe_load(yaml_str)
    return Task.model_validate(data)


def save_task(task: Task, tasks_dir: Path) -> Path:
    """Save a task to its YAML file."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    filepath = tasks_dir / f"{task.id}.yaml"
    filepath.write_text(task_to_yaml(task), encoding="utf-8")
    return filepath


def load_task(filepath: Path) -> Task:
    """Load a task from its YAML file."""
    yaml_str = filepath.read_text(encoding="utf-8")
    return task_from_yaml(yaml_str)


def load_all_tasks(tasks_dir: Path) -> list[Task]:
    """Load all tasks from the tasks directory."""
    tasks = []
    if not tasks_dir.exists():
        return tasks
    for filepath in sorted(tasks_dir.glob("T-*.yaml")):
        try:
            tasks.append(load_task(filepath))
        except Exception as e:
            print(f"Warning: Failed to load {filepath.name}: {e}")
    return tasks
