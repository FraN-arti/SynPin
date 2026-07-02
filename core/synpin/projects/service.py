"""
Project service — business logic for project management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import (
    Project,
    ProjectStatus,
    create_project,
)
from .config import ProjectConfig
from ..time import now as _now


class ProjectService:
    """Business logic for projects."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def get_all_projects(self) -> list[Project]:
        """Get all projects."""
        return self.config.load_all_projects()

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self.config.load_project(project_id)

    def create_project(
        self,
        name: str,
        description: str = "",
        main_department: str = "",
        departments: list[dict[str, Any]] | None = None,
        goals: list[dict[str, Any]] | None = None,
        work_dir: str | None = None,
        deadline: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Project:
        """Create a new project."""
        project = create_project(
            name=name,
            description=description,
            main_department=main_department,
            work_dir=work_dir,
            deadline=deadline,
            tags=tags,
        )

        # Add additional departments
        if departments:
            for dept in departments:
                dept_id = dept.get("id", "")
                if dept_id and dept_id != main_department:
                    project.add_department(
                        dept_id=dept_id,
                        role=dept.get("role", ""),
                        is_main=False,
                    )

        # Add goals
        if goals:
            for goal in goals:
                title = goal.get("title", "")
                if title:
                    project.add_goal(
                        title=title,
                        description=goal.get("description", ""),
                    )

        self.config.save_project(project)
        return project

    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        work_dir: str | None = None,
        deadline: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Project | None:
        """Update project fields."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if status is not None:
            try:
                project.status = ProjectStatus(status)
            except ValueError:
                # Unknown status string — leave previous value intact
                pass
        if priority is not None:
            project.priority = priority
        if work_dir is not None:
            project.work_dir = work_dir
        if deadline is not None:
            project.deadline = deadline
        if tags is not None:
            project.tags = tags

        project.updated_at = _now()
        self.config.save_project(project)
        return project

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project. Only user can do this!
        Tasks with this project_id will have their project_id set to None.
        """
        # Load project to get department list
        project = self.config.load_project(project_id)
        if not project:
            return False

        # Unlink tasks from this project before deletion
        try:
            from ..kanban.service import KanbanService
            kanban = KanbanService(self.config.projects_dir.parent)
            tasks = kanban.list_tasks(project_id=project_id)
            for task in tasks:
                task.project_id = None
                task.project_goal_id = None
                kanban.save_task(task)
        except Exception:
            pass  # If kanban service unavailable, just delete the project

        # Delete the project directory
        return self.config.delete_project(project_id)

    # ── Department management ───────────────────────────────────────────

    def add_department(
        self,
        project_id: str,
        dept_id: str,
        role: str = "",
        is_main: bool = False,
    ) -> Project | None:
        """Add a department to a project."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        project.add_department(dept_id, role, is_main)

        if is_main:
            project.main_department = dept_id

        self.config.save_project(project)
        return project

    def remove_department(self, project_id: str, dept_id: str) -> Project | None:
        """Remove a department from a project."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        project.remove_department(dept_id)

        # If removed main department, clear it
        if project.main_department == dept_id:
            project.main_department = ""

        self.config.save_project(project)
        return project

    def update_department_role(
        self,
        project_id: str,
        dept_id: str,
        role: str,
    ) -> Project | None:
        """Update department's role in project."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        for dept in project.departments:
            if dept.id == dept_id:
                dept.role = role
                break

        self.config.save_project(project)
        return project

    def set_main_department(self, project_id: str, dept_id: str) -> Project | None:
        """Set the main department of a project."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        # Ensure department is in the project
        dept_found = False
        for dept in project.departments:
            if dept.id == dept_id:
                dept.is_main = True
                dept_found = True
            else:
                dept.is_main = False

        if not dept_found:
            project.add_department(dept_id, role="Основной", is_main=True)

        project.main_department = dept_id
        self.config.save_project(project)
        return project

    # ── Goals management ────────────────────────────────────────────────

    def add_goal(
        self,
        project_id: str,
        title: str,
        description: str = "",
    ) -> tuple[Project, Any] | None:
        """Add a goal to a project."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        goal = project.add_goal(title, description)
        self.config.save_project(project)
        return project, goal

    def update_goal(
        self,
        project_id: str,
        goal_id: str,
        title: str | None = None,
        status: str | None = None,
        description: str | None = None,
    ) -> Project | None:
        """Update a goal."""
        from .models import GoalStatus

        project = self.config.load_project(project_id)
        if not project:
            return None

        for goal in project.goals:
            if goal.id == goal_id:
                if title is not None:
                    goal.title = title
                if status is not None:
                    # Validate via enum so unknown values don't sneak in
                    try:
                        goal.status = GoalStatus(status)
                        if goal.status == GoalStatus.COMPLETED:
                            goal.completed_at = _now()
                    except ValueError:
                        pass
                if description is not None:
                    goal.description = description
                break

        self.config.save_project(project)
        return project

    def remove_goal(self, project_id: str, goal_id: str) -> Project | None:
        """Remove a goal."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        project.remove_goal(goal_id)
        self.config.save_project(project)
        return project

    # ── Archive management ──────────────────────────────────────────────

    def archive_task(
        self,
        project_id: str,
        task_id: str,
        title: str,
        department: str = "",
        reason: str = "",
    ) -> tuple[Project, Any] | None:
        """Archive a single task."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        entry = project.archive_task(task_id, title, department, reason)
        self.config.save_project(project)
        return project, entry

    def archive_milestone(
        self,
        project_id: str,
        title: str,
        task_ids: list[str],
        summary: str = "",
    ) -> tuple[Project, Any] | None:
        """Archive a milestone."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        entry = project.archive_milestone(title, task_ids, summary)
        self.config.save_project(project)
        return project, entry

    def remove_archive_entry(self, project_id: str, entry_id: str) -> Project | None:
        """Remove an archive entry."""
        project = self.config.load_project(project_id)
        if not project:
            return None

        project.archive = [a for a in project.archive if a.id != entry_id]
        self.config.save_project(project)
        return project

    # ── Project head ────────────────────────────────────────────────────

    def get_project_head_department(self, project: Project) -> str | None:
        """
        Get the main department ID of a project.

        Returns dept_id of the main department, or None if no department
        is assigned.
        """
        main_dept = project.get_head_department()
        if not main_dept:
            return None
        return main_dept.id

    def get_project_head_agent(self, project: Project) -> str | None:
        """
        Get the head agent ID of a project.

        Walks project → main department → head of that department
        (loaded from data/otdels/{id}/otdel.yaml). Returns None if any
        link in the chain is missing.

        Replaces the legacy get_project_head() which returned dept_id
        despite its name — that was a real source of UI confusion.
        """
        from ..agents.names import read_otdel
        dept_id = self.get_project_head_department(project)
        if not dept_id:
            return None
        otdel_yaml = read_otdel(dept_id)
        if not otdel_yaml:
            return None
        head_id = otdel_yaml.get("head")
        return head_id or None

    # ── Statistics ──────────────────────────────────────────────────────

    def get_project_stats(self, project: Project, tasks: list[Any]) -> dict:
        """Calculate project statistics from tasks."""
        total = len(tasks)
        done = sum(1 for t in tasks if getattr(t, 'status', None) == 'done')
        in_progress = sum(1 for t in tasks if getattr(t, 'status', None) == 'in_progress')
        overdue = sum(
            1 for t in tasks
            if getattr(t, 'deadline', None) and
            getattr(t, 'deadline', None) < _now() and
            getattr(t, 'status', None) != 'done'
        )

        # Stats by department
        by_department = {}
        for dept in project.departments:
            dept_tasks = [t for t in tasks if getattr(t, 'department', None) == dept.id]
            by_department[dept.id] = {
                "total": len(dept_tasks),
                "done": sum(1 for t in dept_tasks if getattr(t, 'status', None) == 'done'),
                "in_progress": sum(1 for t in dept_tasks if getattr(t, 'status', None) == 'in_progress'),
            }

        # Goals progress
        goals_progress = {}
        for goal in project.goals:
            # Goals don't have direct task links yet
            goals_progress[goal.id] = {
                "status": goal.status,
                "completed": goal.status == "completed",
            }

        return {
            "project_id": project.id,
            "total_tasks": total,
            "done": done,
            "in_progress": in_progress,
            "overdue": overdue,
            "progress_percent": (done / total * 100) if total > 0 else 0,
            "by_department": by_department,
            "goals_progress": goals_progress,
            "archive_count": len(project.archive),
        }