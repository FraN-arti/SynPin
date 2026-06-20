"""
Project models — Pydantic schemas for the project management system.

Projects group departments, tasks, and history under a single goal.
Each project is stored as a YAML file in data/projects/{project_id}/project.yaml.
"""
from __future__ import annotations

import re
import yaml
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class ProjectStatus(str, Enum):
    """Lifecycle stages of a project."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class GoalStatus(str, Enum):
    """Status of a project goal."""
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# ── Sub-models ───────────────────────────────────────────────────────────────

class ProjectDepartment(BaseModel):
    """Department binding within a project."""
    id: str                      # Department ID (otdelid)
    role: str = ""               # Role of this department in the project
    is_main: bool = False        # Main department (head of this = project head)
    joined_at: datetime = Field(default_factory=datetime.now)


class ProjectGoal(BaseModel):
    """A goal within a project."""
    id: str                      # Goal ID (goal-{hex})
    title: str
    status: GoalStatus = GoalStatus.BACKLOG
    description: str = ""
    completed_at: datetime | None = None


class ArchiveEntry(BaseModel):
    """An archived task or milestone."""
    id: str                      # Archive entry ID (arch-{hex})
    type: str                    # "task" or "milestone"
    title: str
    task_id: str | None = None   # For single task archive
    task_ids: list[str] = Field(default_factory=list)  # For milestone archive
    department: str = ""
    summary: str = ""
    completed_at: datetime = Field(default_factory=datetime.now)
    archived_at: datetime = Field(default_factory=datetime.now)
    reason: str = ""


# ── Main Project Model ─────────────────────────────────────────────────────

class Project(BaseModel):
    """
    A project groups departments, tasks, and history under a single goal.
    
    Stored as YAML in data/projects/{project_id}/project.yaml.
    """
    id: str                                     # Project ID (32 chars, alphanumeric)
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    priority: str = "medium"                    # low | medium | high | critical
    
    # Main department (head of this = project head)
    main_department: str = ""
    
    # Departments in the project
    departments: list[ProjectDepartment] = Field(default_factory=list)
    
    # Project goals
    goals: list[ProjectGoal] = Field(default_factory=list)
    
    # Archive (completed tasks/milestones)
    archive: list[ArchiveEntry] = Field(default_factory=list)
    
    # Work directory for tools
    work_dir: str | None = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    deadline: datetime | None = None
    created_by: str = "user"
    tags: list[str] = Field(default_factory=list)
    
    # ── Validators ───────────────────────────────────────────────────────
    
    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if len(v) != 32:
            raise ValueError(f"Project ID must be 32 characters, got {len(v)}")
        if not re.match(r'^[a-zA-Z0-9]+$', v):
            raise ValueError("Project ID must be alphanumeric")
        return v
    
    # ── Methods ──────────────────────────────────────────────────────────
    
    def add_department(self, dept_id: str, role: str = "", is_main: bool = False) -> None:
        """Add a department to the project."""
        # Check if already exists
        for d in self.departments:
            if d.id == dept_id:
                d.role = role or d.role
                d.is_main = is_main or d.is_main
                return
        
        self.departments.append(ProjectDepartment(
            id=dept_id,
            role=role,
            is_main=is_main,
        ))
        self.updated_at = datetime.now()
    
    def remove_department(self, dept_id: str) -> bool:
        """Remove a department from the project."""
        initial_len = len(self.departments)
        self.departments = [d for d in self.departments if d.id != dept_id]
        if len(self.departments) < initial_len:
            self.updated_at = datetime.now()
            return True
        return False
    
    def add_goal(self, title: str, description: str = "") -> ProjectGoal:
        """Add a goal to the project."""
        import uuid
        goal = ProjectGoal(
            id=f"goal-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
        )
        self.goals.append(goal)
        self.updated_at = datetime.now()
        return goal
    
    def remove_goal(self, goal_id: str) -> bool:
        """Remove a goal from the project."""
        initial_len = len(self.goals)
        self.goals = [g for g in self.goals if g.id != goal_id]
        if len(self.goals) < initial_len:
            self.updated_at = datetime.now()
            return True
        return False
    
    def archive_task(self, task_id: str, title: str, department: str = "", reason: str = "") -> ArchiveEntry:
        """Archive a single task."""
        import uuid
        entry = ArchiveEntry(
            id=f"arch-{uuid.uuid4().hex[:8]}",
            type="task",
            title=title,
            task_id=task_id,
            department=department,
            reason=reason,
        )
        self.archive.append(entry)
        self.updated_at = datetime.now()
        return entry
    
    def archive_milestone(self, title: str, task_ids: list[str], summary: str = "") -> ArchiveEntry:
        """Archive a milestone (group of tasks)."""
        import uuid
        entry = ArchiveEntry(
            id=f"arch-{uuid.uuid4().hex[:8]}",
            type="milestone",
            title=title,
            task_ids=task_ids,
            summary=summary,
        )
        self.archive.append(entry)
        self.updated_at = datetime.now()
        return entry
    
    def get_head_department(self) -> ProjectDepartment | None:
        """Get the main department of the project."""
        for d in self.departments:
            if d.is_main:
                return d
        return self.departments[0] if self.departments else None


# ── Factory ──────────────────────────────────────────────────────────────────

def create_project(
    name: str,
    description: str = "",
    main_department: str = "",
    priority: str = "medium",
    work_dir: str | None = None,
    deadline: datetime | None = None,
    tags: list[str] | None = None,
    project_id: str | None = None,
) -> Project:
    """Create a new project with initial data."""
    import uuid
    
    project = Project(
        id=project_id or uuid.uuid4().hex,
        name=name,
        description=description,
        main_department=main_department,
        priority=priority,
        work_dir=work_dir,
        deadline=deadline,
        tags=tags or [],
    )
    
    # Add main department if specified
    if main_department:
        project.add_department(main_department, role="Основной", is_main=True)
    
    return project


# ── YAML I/O ─────────────────────────────────────────────────────────────────

def project_to_yaml(project: Project) -> str:
    """Serialize a project to YAML string."""
    return yaml.dump(
        project.model_dump(mode="json"),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def project_from_yaml(yaml_str: str) -> Project:
    """Deserialize a project from YAML string."""
    data = yaml.safe_load(yaml_str)
    return Project.model_validate(data)


def save_project(project: Project, projects_dir: Path) -> Path:
    """Save a project to its YAML file."""
    project_dir = projects_dir / project.id
    project_dir.mkdir(parents=True, exist_ok=True)
    filepath = project_dir / "project.yaml"
    filepath.write_text(project_to_yaml(project), encoding="utf-8")
    return filepath


def load_project(filepath: Path) -> Project:
    """Load a project from a YAML file."""
    yaml_str = filepath.read_text(encoding="utf-8")
    return project_from_yaml(yaml_str)


def load_all_projects(projects_dir: Path) -> list[Project]:
    """Load all projects from the projects directory."""
    projects = []
    if not projects_dir.exists():
        return projects
    
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        yaml_file = project_dir / "project.yaml"
        if yaml_file.exists():
            try:
                projects.append(load_project(yaml_file))
            except Exception as e:
                print(f"Warning: Failed to load {project_dir.name}: {e}")
    
    return projects
