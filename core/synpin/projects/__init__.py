"""
Projects module — project management for SynPin.
"""
from .models import (
    Project,
    ProjectStatus,
    ProjectGoal,
    GoalStatus,
    ProjectDepartment,
    ArchiveEntry,
    create_project,
)
from .config import ProjectConfig
from .service import ProjectService
from .router import router as projects_router

__all__ = [
    "Project",
    "ProjectStatus",
    "ProjectGoal",
    "GoalStatus",
    "ProjectDepartment",
    "ArchiveEntry",
    "create_project",
    "ProjectConfig",
    "ProjectService",
    "projects_router",
]
