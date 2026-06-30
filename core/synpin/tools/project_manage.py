"""Manage projects — CRUD operations for the main agent."""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool

_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")



@register_tool(
    name='project_manage',
    description='Управление проектами: создание, редактирование, удаление, управление отделами в проекте. Используй для создания проектов и связывания их с отделами.',
    category='other',
    scope='primary',
    dangerous=False,
)
async def project_manage(params: dict[str, Any]) -> ToolResult:
    """
    Управление проектами.

    Commands:
      list            — список всех проектов
      get             — получить проект по ID (с отделами и целями)
      create          — создать проект
      update          — обновить проект
      delete          — удалить проект
      add_department  — добавить отдел в проект
      remove_department — убрать отдел из проекта
    """
    command = params.get("command", "")
    if not command:
        return make_error("command required: list, get, create, update, delete, add_department, remove_department")

    try:
        if command == "list":
            return await _list(params)
        elif command == "get":
            return await _get(params)
        elif command == "create":
            return await _create(params)
        elif command == "update":
            return await _update(params)
        elif command == "delete":
            return await _delete(params)
        elif command == "add_department":
            return await _add_department(params)
        elif command == "remove_department":
            return await _remove_department(params)
        else:
            return make_error(f"Unknown command: {command}")
    except Exception as e:
        return make_error(f"project_manage error: {e}")


async def _list(params: dict[str, Any]) -> ToolResult:
    """Список всех проектов."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/projects")
        if res.status_code != 200:
            return make_error(f"Failed to list projects: {res.text}")
        data = res.json()

    projects = data if isinstance(data, list) else data.get("projects", [])
    result = []
    for p in projects:
        result.append({
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "status": p.get("status", ""),
            "priority": p.get("priority", ""),
            "deadline": p.get("deadline"),
            "departments": [d.get("name", d.get("dept_id", "")) for d in p.get("departments", [])],
        })

    return make_success({"projects": result, "count": len(result)})


async def _get(params: dict[str, Any]) -> ToolResult:
    """Получить проект по ID."""
    import httpx

    project_id = params.get("project_id", "") or params.get("id", "")
    if not project_id:
        return make_error("project_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/projects/{project_id}")
        if res.status_code != 200:
            return make_error(f"Project not found: {project_id}")
        project = res.json()

    return make_success({
        "id": project.get("id", ""),
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "status": project.get("status", ""),
        "priority": project.get("priority", ""),
        "deadline": project.get("deadline"),
        "tags": project.get("tags", []),
        "departments": project.get("departments", []),
        "goals": project.get("goals", []),
    })


async def _create(params: dict[str, Any]) -> ToolResult:
    """Создать новый проект."""
    import httpx

    name = params.get("name", "")
    if not name:
        return make_error("name required")

    payload = {
        "name": name,
        "description": params.get("description", ""),
        "tags": params.get("tags", []),
    }

    deadline = params.get("deadline")
    if deadline:
        payload["deadline"] = deadline

    departments = params.get("departments", [])
    if departments:
        payload["departments"] = departments

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(f"{_API_BASE}/api/projects", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to create project: {res.text}")
        project = res.json()

    return make_success({
        "id": project.get("id", ""),
        "name": project.get("name", ""),
        "message": f"Project '{name}' created",
    })


async def _update(params: dict[str, Any]) -> ToolResult:
    """Обновить проект."""
    import httpx

    project_id = params.get("project_id", "") or params.get("id", "")
    if not project_id:
        return make_error("project_id required")

    payload = {}
    for field in ("name", "description", "status", "priority", "deadline", "tags"):
        if field in params and params[field] is not None:
            payload[field] = params[field]

    if not payload:
        return make_error("Nothing to update — provide name, description, status, priority, deadline, or tags")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.put(f"{_API_BASE}/api/projects/{project_id}", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to update project: {res.text}")
        project = res.json()

    return make_success({
        "id": project.get("id", ""),
        "name": project.get("name", ""),
        "message": f"Project updated",
    })


async def _delete(params: dict[str, Any]) -> ToolResult:
    """Удалить проект."""
    import httpx

    project_id = params.get("project_id", "") or params.get("id", "")
    if not project_id:
        return make_error("project_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.delete(f"{_API_BASE}/api/projects/{project_id}")
        if res.status_code != 200:
            return make_error(f"Failed to delete project: {res.text}")

    return make_success({"message": f"Project {project_id} deleted"})


async def _add_department(params: dict[str, Any]) -> ToolResult:
    """Добавить отдел в проект."""
    import httpx

    project_id = params.get("project_id", "") or params.get("id", "")
    if not project_id:
        return make_error("project_id required")

    dept_id = params.get("dept_id", "")
    if not dept_id:
        return make_error("dept_id required")

    payload = {
        "dept_id": dept_id,
        "role": params.get("role", ""),
        "is_main": params.get("is_main", False),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(f"{_API_BASE}/api/projects/{project_id}/departments", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to add department: {res.text}")
        project = res.json()

    return make_success({
        "project_id": project_id,
        "departments": project.get("departments", []),
        "message": f"Department {dept_id} added to project",
    })


async def _remove_department(params: dict[str, Any]) -> ToolResult:
    """Убрать отдел из проекта."""
    import httpx

    project_id = params.get("project_id", "") or params.get("id", "")
    if not project_id:
        return make_error("project_id required")

    dept_id = params.get("dept_id", "")
    if not dept_id:
        return make_error("dept_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.delete(f"{_API_BASE}/api/projects/{project_id}/departments/{dept_id}")
        if res.status_code != 200:
            return make_error(f"Failed to remove department: {res.text}")
        project = res.json()

    return make_success({
        "project_id": project_id,
        "departments": project.get("departments", []),
        "message": f"Department {dept_id} removed from project",
    })


__all__ = ["project_manage"]
