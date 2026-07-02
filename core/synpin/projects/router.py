"""
Project router — API endpoints for project management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..paths import get_data_dir
from ..agents.names import read_otdel, read_otdel_name, read_agent_name
from .models import ProjectStatus
from .config import ProjectConfig
from .service import ProjectService


# Re-exports for backward compatibility — older callers may still import these
# private names from this module. Keep them as thin wrappers around the canonical
# implementations in agents/names.py.
_read_otdel = read_otdel
_read_otdel_name = read_otdel_name
_read_agent_name = read_agent_name


# ── Department / agent name enrichment ────────────────────────────────────

# Implementation moved to synpin/agents/names.py (single source of truth).
# This module re-imports the helpers above for backward compatibility with
# any callers that imported them as private names.


def _enrich_project(payload: dict) -> dict:
    """Inject human-readable names into a project payload (runtime-only).

    Enriches:
      - departments[].name                  (otdel name)
      - departments[].head_name             (head agent name)
      - departments[].workers_names[]       (per-worker agent name)
      - main_department_name                (top-level convenience)

    Source of truth for head/workers is the department YAML, not the
    ProjectDepartment payload (which only stores id/role/is_main).
    """
    departments = payload.get("departments") or []
    for dept in (d for d in departments if isinstance(d, dict)):
        did = dept.get("id", "")
        if "name" not in dept:
            n = read_otdel_name(did)
            if n is not None:
                dept["name"] = n

        otdel_yaml = read_otdel(did) if did else None
        if otdel_yaml:
            if "head_name" not in dept and otdel_yaml.get("head"):
                hn = read_agent_name(otdel_yaml["head"])
                if hn is not None:
                    dept["head_name"] = hn
            if "workers_names" not in dept and otdel_yaml.get("workers"):
                workers = otdel_yaml["workers"]
                if isinstance(workers, list):
                    dept["workers_names"] = [
                        {"id": w, "name": read_agent_name(w)} if read_agent_name(w)
                        else {"id": w}
                        for w in workers
                    ]

    main_id = payload.get("main_department", "")
    if main_id and "main_department_name" not in payload:
        mn = read_otdel_name(main_id)
        if mn is not None:
            payload["main_department_name"] = mn
    return payload


# ── Request/Response models ─────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    """Request to create a new project."""
    name: str
    description: str = ""
    main_department: str = ""
    departments: list[dict[str, Any]] = []
    goals: list[dict[str, Any]] = []
    work_dir: str | None = None
    deadline: datetime | None = None
    tags: list[str] = []


class UpdateProjectRequest(BaseModel):
    """Request to update a project."""
    name: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    work_dir: str | None = None
    deadline: datetime | None = None
    tags: list[str] | None = None


class AddDepartmentRequest(BaseModel):
    """Request to add a department to a project."""
    dept_id: str
    role: str = ""
    is_main: bool = False


class UpdateDepartmentRoleRequest(BaseModel):
    """Request to update department role."""
    role: str


class SetMainDepartmentRequest(BaseModel):
    """Request to set main department."""
    dept_id: str


class UpdateProjectStatusRequest(BaseModel):
    """Request to update project status (caller-validated via otdel_id)."""
    status: str
    otdel_id: str | None = None  # If set, require this otdel to be the project's main department.


class AddGoalRequest(BaseModel):
    """Request to add a goal."""
    title: str
    description: str = ""


class UpdateGoalRequest(BaseModel):
    """Request to update a goal."""
    title: str | None = None
    status: str | None = None
    description: str | None = None


class ArchiveTaskRequest(BaseModel):
    """Request to archive a task."""
    task_id: str
    title: str
    department: str = ""
    reason: str = ""


class ArchiveMilestoneRequest(BaseModel):
    """Request to archive a milestone."""
    title: str
    task_ids: list[str]
    summary: str = ""


class UpdateTogleRequest(BaseModel):
    """Request to update TOGLE.md."""
    content: str


class AppendTogleRequest(BaseModel):
    """Request to append to TOGLE.md."""
    entry: str
    entry_type: str = "note"


# ── Helper for WS broadcast ────────────────────────────────────────────────

async def _broadcast(event_type: str, data: dict[str, Any] | None = None):
    """Broadcast WebSocket event."""
    try:
        from ..chat.ws_manager import ws_manager
        payload = {"type": event_type}
        if data:
            payload.update(data)
        await ws_manager.broadcast(payload)
    except Exception:
        pass


# ── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_service() -> ProjectService:
    """Get project service instance."""
    data_dir = get_data_dir()
    config = ProjectConfig(data_dir)
    return ProjectService(config)


@router.get("")
async def list_projects(dept_id: str | None = Query(default=None, description="Filter by department ID — only projects that include this department")):
    """Get all projects, or projects for a specific department if dept_id is given."""
    service = get_service()
    projects = service.get_all_projects()

    if dept_id:
        # A project includes dept_id if its departments[] entry has matching id
        # (we don't restrict on is_main — both main and supporting depts see it).
        projects = [p for p in projects if any(d.id == dept_id for d in p.departments)]

    return {
        "projects": [_enrich_project(p.model_dump()) for p in projects]
    }


@router.post("")
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    service = get_service()

    project = service.create_project(
        name=request.name,
        description=request.description,
        main_department=request.main_department,
        departments=request.departments,
        goals=request.goals,
        work_dir=request.work_dir,
        deadline=request.deadline,
        tags=request.tags,
    )

    await _broadcast("project:created", {"project_id": project.id})

    return {"project": _enrich_project(project.model_dump())}


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get a project by ID."""
    service = get_service()
    project = service.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"project": _enrich_project(project.model_dump())}


@router.put("/{project_id}")
async def update_project(project_id: str, request: UpdateProjectRequest):
    """Update a project."""
    service = get_service()
    
    project = service.update_project(
        project_id=project_id,
        name=request.name,
        description=request.description,
        status=request.status,
        priority=request.priority,
        work_dir=request.work_dir,
        deadline=request.deadline,
        tags=request.tags,
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await _broadcast("project:updated", {"project_id": project_id})
    
    return {"project": _enrich_project(project.model_dump())}


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project. Only user can do this!"""
    service = get_service()
    
    success = service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await _broadcast("project:deleted", {"project_id": project_id})
    
    return {"success": True}


# ── Department endpoints ────────────────────────────────────────────────────

@router.post("/{project_id}/departments")
async def add_department(project_id: str, request: AddDepartmentRequest):
    """Add a department to a project."""
    service = get_service()
    
    project = service.add_department(
        project_id=project_id,
        dept_id=request.dept_id,
        role=request.role,
        is_main=request.is_main,
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await _broadcast("project:department_added", {
        "project_id": project_id,
        "dept_id": request.dept_id,
    })
    
    return {"project": _enrich_project(project.model_dump())}


@router.delete("/{project_id}/departments/{dept_id}")
async def remove_department(project_id: str, dept_id: str):
    """Remove a department from a project."""
    service = get_service()
    
    project = service.remove_department(project_id, dept_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await _broadcast("project:department_removed", {
        "project_id": project_id,
        "dept_id": dept_id,
    })
    
    return {"project": _enrich_project(project.model_dump())}


@router.put("/{project_id}/departments/{dept_id}")
async def update_department_role(project_id: str, dept_id: str, request: UpdateDepartmentRoleRequest):
    """Update department's role in project."""
    service = get_service()
    
    project = service.update_department_role(project_id, dept_id, request.role)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"project": _enrich_project(project.model_dump())}


@router.put("/{project_id}/main-department")
async def set_main_department(project_id: str, request: SetMainDepartmentRequest):
    """Set the main department of a project."""
    service = get_service()

    project = service.set_main_department(project_id, request.dept_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await _broadcast("project:updated", {"project_id": project_id})

    return {"project": _enrich_project(project.model_dump())}


@router.put("/{project_id}/status")
async def update_project_status(project_id: str, request: UpdateProjectStatusRequest):
    """Update project status.

    Two paths:
      1. Primary agent (no otdel_id) → full access, no further checks.
      2. Department head (otdel_id supplied) → allowed ONLY when that otdel
         is the project's main department. Used by the head-UI / head-tool
         to act on a project they are responsible for.

    Status must be a valid ProjectStatus value (active / paused /
    completed / archived).
    """
    service = get_service()
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Permission check: if otdel_id is provided, this is a non-primary caller.
    if request.otdel_id:
        main_dept = project.get_head_department()
        if not main_dept or main_dept.id != request.otdel_id:
            raise HTTPException(
                status_code=403,
                detail="Only the project's main department head can change status",
            )

    try:
        new_status = ProjectStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {request.status}. Must be one of: "
                   f"{', '.join(s.value for s in ProjectStatus)}",
        )

    updated = service.update_project(project_id, status=new_status.value)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update status")

    await _broadcast("project:updated", {"project_id": project_id, "status": new_status.value})

    return {"project": _enrich_project(updated.model_dump())}


# ── Goals endpoints ─────────────────────────────────────────────────────────

@router.get("/{project_id}/goals")
async def list_goals(project_id: str):
    """Get all goals of a project."""
    service = get_service()
    project = service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"goals": [g.model_dump() for g in project.goals]}


@router.post("/{project_id}/goals")
async def add_goal(project_id: str, request: AddGoalRequest):
    """Add a goal to a project."""
    service = get_service()
    
    result = service.add_goal(
        project_id=project_id,
        title=request.title,
        description=request.description,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project, goal = result
    
    await _broadcast("project:goal_added", {
        "project_id": project_id,
        "goal": goal.model_dump(),
    })
    
    return {"goal": goal.model_dump()}


@router.put("/{project_id}/goals/{goal_id}")
async def update_goal(project_id: str, goal_id: str, request: UpdateGoalRequest):
    """Update a goal."""
    service = get_service()
    
    project = service.update_goal(
        project_id=project_id,
        goal_id=goal_id,
        title=request.title,
        status=request.status,
        description=request.description,
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await _broadcast("project:goal_updated", {
        "project_id": project_id,
        "goal_id": goal_id,
    })
    
    return {"project": _enrich_project(project.model_dump())}


@router.delete("/{project_id}/goals/{goal_id}")
async def delete_goal(project_id: str, goal_id: str):
    """Delete a goal."""
    service = get_service()
    
    project = service.remove_goal(project_id, goal_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"project": _enrich_project(project.model_dump())}


# ── Archive endpoints ───────────────────────────────────────────────────────

@router.get("/{project_id}/archive")
async def list_archive(project_id: str):
    """Get archive entries."""
    service = get_service()
    project = service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"archive": [a.model_dump() for a in project.archive]}


@router.post("/{project_id}/archive/task")
async def archive_task(project_id: str, request: ArchiveTaskRequest):
    """Archive a single task."""
    service = get_service()
    
    result = service.archive_task(
        project_id=project_id,
        task_id=request.task_id,
        title=request.title,
        department=request.department,
        reason=request.reason,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project, entry = result
    
    await _broadcast("project:archived", {
        "project_id": project_id,
        "entry": entry.model_dump(),
    })
    
    return {"entry": entry.model_dump()}


@router.post("/{project_id}/archive/milestone")
async def archive_milestone(project_id: str, request: ArchiveMilestoneRequest):
    """Archive a milestone."""
    service = get_service()
    
    result = service.archive_milestone(
        project_id=project_id,
        title=request.title,
        task_ids=request.task_ids,
        summary=request.summary,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project, entry = result
    
    await _broadcast("project:archived", {
        "project_id": project_id,
        "entry": entry.model_dump(),
    })
    
    return {"entry": entry.model_dump()}


@router.delete("/{project_id}/archive/{entry_id}")
async def delete_archive_entry(project_id: str, entry_id: str):
    """Delete an archive entry."""
    service = get_service()
    
    project = service.remove_archive_entry(project_id, entry_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"project": _enrich_project(project.model_dump())}


# ── TOGLE endpoints ─────────────────────────────────────────────────────────

@router.get("/{project_id}/togle")
async def get_togle(project_id: str):
    """Get TOGLE.md content."""
    service = get_service()
    project = service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    content = service.config.read_togle(project_id)
    return {"content": content}


@router.put("/{project_id}/togle")
async def update_togle(project_id: str, request: UpdateTogleRequest):
    """Update TOGLE.md content. Only project head can do this!"""
    service = get_service()
    project = service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    service.config.write_togle(project_id, request.content)
    
    await _broadcast("project:togle_updated", {"project_id": project_id})
    
    return {"success": True}


@router.post("/{project_id}/togle/append")
async def append_togle(project_id: str, request: AppendTogleRequest):
    """Append to TOGLE.md."""
    service = get_service()
    project = service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    service.config.append_togle(project_id, request.entry)
    
    await _broadcast("project:togle_updated", {"project_id": project_id})
    
    return {"success": True}
