"""Manage departments — CRUD operations for the main agent."""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error

_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")


async def otdel_manage(params: dict[str, Any]) -> ToolResult:
    """
    Управление отделами.

    Commands:
      list   — список всех отделов
      get    — получить отдел по ID
      create — создать отдел
      update — обновить отдел
      delete — удалить отдел
    """
    command = params.get("command", "")
    if not command:
        return make_error("command required: list, get, create, update, delete")

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
        else:
            return make_error(f"Unknown command: {command}. Use: list, get, create, update, delete")
    except Exception as e:
        return make_error(f"otdel_manage error: {e}")


async def _list(params: dict[str, Any]) -> ToolResult:
    """Список всех отделов."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/departments")
        if res.status_code != 200:
            return make_error(f"Failed to list departments: {res.text}")
        data = res.json()

    departments = data.get("departments", [])
    result = []
    for d in departments:
        result.append({
            "id": d.get("id", ""),
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "agent_count": d.get("agent_count", 0),
        })

    return make_success({"departments": result, "count": len(result)})


async def _get(params: dict[str, Any]) -> ToolResult:
    """Получить отдел по ID."""
    import httpx

    dept_id = params.get("dept_id", "") or params.get("id", "")
    if not dept_id:
        return make_error("dept_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/departments/{dept_id}")
        if res.status_code != 200:
            return make_error(f"Department not found: {dept_id}")
        dept = res.json()

    return make_success({
        "id": dept.get("id", ""),
        "name": dept.get("name", ""),
        "description": dept.get("description", ""),
        "color": dept.get("color", ""),
        "agents": dept.get("agents", []),
        "agent_count": dept.get("agent_count", 0),
    })


async def _create(params: dict[str, Any]) -> ToolResult:
    """Создать новый отдел."""
    import httpx

    name = params.get("name", "")
    if not name:
        return make_error("name required")

    payload = {
        "name": name,
        "description": params.get("description", ""),
        "color": params.get("color", "#f97316"),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(f"{_API_BASE}/api/departments", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to create department: {res.text}")
        dept = res.json()

    return make_success({
        "id": dept.get("id", ""),
        "name": dept.get("name", ""),
        "message": f"Department '{name}' created",
    })


async def _update(params: dict[str, Any]) -> ToolResult:
    """Обновить отдел."""
    import httpx

    dept_id = params.get("dept_id", "") or params.get("id", "")
    if not dept_id:
        return make_error("dept_id required")

    payload = {}
    for field in ("name", "description", "color"):
        if field in params and params[field] is not None:
            payload[field] = params[field]

    if not payload:
        return make_error("Nothing to update — provide name, description, or color")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.put(f"{_API_BASE}/api/departments/{dept_id}", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to update department: {res.text}")
        dept = res.json()

    return make_success({
        "id": dept.get("id", ""),
        "name": dept.get("name", ""),
        "message": f"Department updated",
    })


async def _delete(params: dict[str, Any]) -> ToolResult:
    """Удалить отдел."""
    import httpx

    dept_id = params.get("dept_id", "") or params.get("id", "")
    if not dept_id:
        return make_error("dept_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.delete(f"{_API_BASE}/api/departments/{dept_id}")
        if res.status_code != 200:
            return make_error(f"Failed to delete department: {res.text}")

    return make_success({"message": f"Department {dept_id} deleted"})


__all__ = ["otdel_manage"]
