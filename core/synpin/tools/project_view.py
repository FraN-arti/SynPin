"""Read-only view of projects for department heads (scope='head').

Lets a head agent see which projects include their department and read
project details. Cannot create / delete / modify projects.

Permission model:
- list_my_projects() → all projects where the calling head's department
  participates. otdel_id is resolved automatically from agent_slug (the
  head's own slug is the head of one department).
- get_project_for_dept(project_id) → returns project only if the head's
  department is in its departments[]. Otherwise 403.

The caller MAY still pass otdel_id explicitly (used by execute_tool
injection when the chat layer already knows it), but if absent we
resolve it via:
  1. params["otdel_id"]        (explicit override)
  2. params["agent_slug"]      (injected by router from caller context)
  3. params["_agent_slug"]     (alt injection name from router)
  4. search data/otdels/*/otdel.yaml for head == <agent_slug>

The head can see a project even if their otdel is NOT the main one. To
change project status the head must be the main otdel — that's handled
by the /api/projects/{id}/status endpoint and the project_status_update
tool, not here.
"""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool

_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")


@register_tool(
    name='project_view',
    description='Просмотр проектов для главы отдела: список проектов, в которых участвует её отдел, и детали проекта. Не изменяет ничего. Глава не передаёт otdel_id — tool находит её отдел сам.',
    category='other',
    scope='head',
    dangerous=False,
)
async def project_view(params: dict[str, Any]) -> ToolResult:
    """
    Read-only project operations for a department head.

    Commands:
      list_my_projects     — список проектов, где участвует её отдел
      get_project_for_dept — детали проекта (только если отдел участник)
    """
    command = params.get("command", "")
    if not command:
        return make_error(
            "command required: list_my_projects, get_project_for_dept"
        )

    otdel_id = _resolve_otdel_id(params)
    if not otdel_id:
        return make_error(
            "Could not resolve otdel_id: pass otdel_id explicitly, or "
            "make sure the chat router injects agent_slug for the head."
        )

    try:
        if command == "list_my_projects":
            return await _list_my_projects(otdel_id)
        elif command == "get_project_for_dept":
            project_id = params.get("project_id", "")
            if not project_id:
                return make_error("project_id required for get_project_for_dept")
            return await _get_project_for_dept(project_id, otdel_id)
        else:
            return make_error(f"Unknown command: {command}")
    except Exception as e:
        return make_error(f"project_view error: {e}")


def _resolve_otdel_id(params: dict[str, Any]) -> str:
    """Resolve the head's department id from various sources.

    Priority:
      1. params["otdel_id"]            explicit override (legacy)
      2. params["agent_slug"]          router injection
      3. params["_agent_slug"]         alt router injection name
      4. scan data/otdels/*/otdel.yaml and find one with head == agent_slug
    """
    explicit = params.get("otdel_id", "")
    if explicit:
        return explicit

    agent_slug = (
        params.get("agent_slug", "")
        or params.get("_agent_slug", "")
    )
    if not agent_slug:
        return ""

    # Last resort: scan otdel YAMLs for head == agent_slug.
    # Lazy import to avoid pulling agents/manager at module load.
    try:
        from ..paths import get_otdels_dir
        otdels_dir = get_otdels_dir()
        if not otdels_dir.exists():
            return ""
        import yaml
        for entry in otdels_dir.iterdir():
            if not entry.is_dir():
                continue
            otdel_yaml = entry / "otdel.yaml"
            if not otdel_yaml.exists():
                continue
            try:
                data = yaml.safe_load(otdel_yaml.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("head") == agent_slug:
                return data.get("otdelid") or entry.name
    except Exception:
        pass
    return ""


async def _list_my_projects(otdel_id: str) -> ToolResult:
    """List all projects where this otdel participates."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/projects", params={"dept_id": otdel_id})
        if res.status_code != 200:
            return make_error(f"Failed to list projects: {res.text}")
        data = res.json()

    projects = data.get("projects", []) if isinstance(data, dict) else data
    result = []
    for p in projects:
        raw_id = p.get("id", "")
        result.append({
            "id": raw_id,
            "short_id": raw_id[:8] if raw_id else "",
            "name": p.get("name", ""),
            "description": p.get("description", ""),
            "status": p.get("status", ""),
            "priority": p.get("priority", ""),
            "deadline": p.get("deadline"),
            "tags": p.get("tags", []),
            "work_dir": p.get("work_dir"),
            "main_department": p.get("main_department", ""),
            "main_department_name": p.get("main_department_name", ""),
            "role": next(
                (d.get("role", "") for d in p.get("departments", [])
                 if d.get("id") == otdel_id),
                "",
            ),
            "is_main_in_project": any(
                d.get("id") == otdel_id and d.get("is_main")
                for d in p.get("departments", [])
            ),
            "updated_at": p.get("updated_at"),
        })

    return make_success({
        "projects": result,
        "count": len(result),
        "dept_id": otdel_id,
    })


async def _get_project_for_dept(project_id: str, otdel_id: str) -> ToolResult:
    """Get project details — only if otdel_id is in project.departments."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/projects/{project_id}")
        if res.status_code == 404:
            return make_error(f"Project not found: {project_id}")
        if res.status_code != 200:
            return make_error(f"Failed to get project: {res.text}")
        project = res.json().get("project", res.json())

    if not any(d.get("id") == otdel_id for d in project.get("departments", [])):
        return make_error(
            f"otdel_id {otdel_id} is not a participant of project {project_id}"
        )

    raw_id = project.get("id", "")
    # short_id: first 8 chars of the hash, useful for showing in chat
    # without dumping the full 32-char identifier.
    short_id = raw_id[:8] if raw_id else ""

    return make_success({
        "id": raw_id,
        "short_id": short_id,
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "status": project.get("status", ""),
        "priority": project.get("priority", ""),
        "deadline": project.get("deadline"),
        "tags": project.get("tags", []),
        "work_dir": project.get("work_dir"),
        "created_at": project.get("created_at"),
        "updated_at": project.get("updated_at"),
        "created_by": project.get("created_by"),
        "main_department": project.get("main_department", ""),
        "main_department_name": project.get("main_department_name", ""),
        "departments": [
            {"id": d.get("id"), "name": d.get("name"), "role": d.get("role"),
             "is_main": d.get("is_main")}
            for d in project.get("departments", [])
        ],
        "goals": project.get("goals", []),
        "archive": project.get("archive", []),
    })


__all__ = ["project_view"]