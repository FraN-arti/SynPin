"""Project status update for department heads (scope='head').

Lets a head of the project's MAIN department change the project status.
The API enforces the same permission check (otdel_id must equal the
project's main department) — this tool is a thin wrapper that resolves
the otdel_id automatically.

otdel_id resolution priority (matches project_view.py):
  1. params["otdel_id"]      explicit override
  2. params["agent_slug"]    router injection
  3. params["_agent_slug"]   alt router injection name
  4. scan data/otdels/*/otdel.yaml for head == agent_slug
"""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool
from .project_view import _resolve_otdel_id

_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")


@register_tool(
    name='project_status_update',
    description='Смена статуса проекта главой отдела (только если её отдел — главный в проекте). Глава не передаёт otdel_id — tool находит её отдел сам.',
    category='other',
    scope='head',
    dangerous=False,
)
async def project_status_update(params: dict[str, Any]) -> ToolResult:
    """
    Update a project's status as the head of its main department.

    Args (via params dict):
        project_id  — id of the project
        status      — one of: active, paused, completed, archived

    otdel_id is auto-resolved from the calling head's context. The
    API still verifies that the resolved otdel is the project's
    main department.
    """
    project_id = params.get("project_id", "")
    new_status = params.get("status", "")

    if not project_id:
        return make_error("project_id required")
    if not new_status:
        return make_error("status required (active | paused | completed | archived)")

    otdel_id = _resolve_otdel_id(params)
    if not otdel_id:
        return make_error(
            "Could not resolve otdel_id: pass otdel_id explicitly, or "
            "make sure the chat router injects agent_slug for the head."
        )

    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.put(
            f"{_API_BASE}/api/projects/{project_id}/status",
            json={"status": new_status, "otdel_id": otdel_id},
        )
        if res.status_code == 403:
            return make_error(
                "Forbidden: only the main department's head can change project status"
            )
        if res.status_code == 404:
            return make_error(f"Project not found: {project_id}")
        if res.status_code == 400:
            return make_error(f"Invalid status: {res.text}")
        if res.status_code != 200:
            return make_error(f"Failed to update status: {res.text}")

    project = res.json().get("project", res.json())
    return make_success({
        "id": project.get("id", ""),
        "name": project.get("name", ""),
        "status": project.get("status", ""),
        "message": f"Project '{project.get('name', project_id)}' status → {new_status}",
    })


__all__ = ["project_status_update"]