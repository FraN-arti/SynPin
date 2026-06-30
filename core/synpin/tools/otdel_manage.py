"""Manage departments — CRUD operations for the main agent."""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool

_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")



@register_tool(
    name='otdel_manage',
    description='Управление отделами (otdels) — чат-комнаты для общения. Список, просмотр, создание, обновление, удаление. Узнай кто глава отдела и сколько агентов.',
    category='other',
    scope='primary',
    dangerous=False,
)
async def otdel_manage(params: dict[str, Any]) -> ToolResult:
    """
    Управление отделами (otdels) — чат-комнаты для общения.

    Commands:
      list   — список всех отделов (с главой и количеством агентов)
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
    """Список всех отделов (otdels) — чат-комнаты для общения."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/otdels")
        if res.status_code != 200:
            return make_error(f"Failed to list otdels: {res.text}")
        data = res.json()

    otdels = data.get("otdels", [])
    result = []
    for o in otdels:
        head = o.get("head", "")
        head_name = ""
        if head:
            try:
                from ..agents.manager import get_agent
                agent = get_agent(head)
                head_name = agent.get("name", head) if agent else head
            except Exception:
                head_name = head
        result.append({
            "id": o.get("otdelid", ""),
            "name": o.get("name", ""),
            "description": o.get("description", ""),
            "head": head_name or head,
            "agent_count": o.get("agent_count", 0),
        })

    return make_success({"otdels": result, "count": len(result)})


async def _get(params: dict[str, Any]) -> ToolResult:
    """Получить отдел по ID."""
    import httpx

    otdel_id = params.get("otdel_id", "") or params.get("dept_id", "") or params.get("id", "")
    if not otdel_id:
        return make_error("otdel_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/otdels/{otdel_id}")
        if res.status_code != 200:
            return make_error(f"Otdel not found: {otdel_id}")
        otdel = res.json()

    head = otdel.get("head", "")
    head_name = ""
    if head:
        try:
            from ..agents.manager import get_agent
            agent = get_agent(head)
            head_name = agent.get("name", head) if agent else head
        except Exception:
            head_name = head

    return make_success({
        "id": otdel.get("otdelid", ""),
        "name": otdel.get("name", ""),
        "description": otdel.get("description", ""),
        "color": otdel.get("color", ""),
        "head": head_name or head,
        "workers": otdel.get("workers", []),
        "agent_count": otdel.get("agent_count", 0),
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
        res = await client.post(f"{_API_BASE}/api/otdels", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to create otdel: {res.text}")
        otdel = res.json()

    return make_success({
        "id": otdel.get("otdelid", ""),
        "name": otdel.get("name", ""),
        "status": "created",
    })


async def _update(params: dict[str, Any]) -> ToolResult:
    """Обновить отдел."""
    import httpx

    otdel_id = params.get("otdel_id", "") or params.get("id", "")
    if not otdel_id:
        return make_error("otdel_id required")

    payload = {}
    for key in ("name", "description", "color"):
        if key in params:
            payload[key] = params[key]
    if not payload:
        return make_error("Nothing to update")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.put(f"{_API_BASE}/api/otdels/{otdel_id}", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to update otdel: {res.text}")

    return make_success({"status": "updated", "otdel_id": otdel_id})


async def _delete(params: dict[str, Any]) -> ToolResult:
    """Удалить отдел."""
    import httpx

    otdel_id = params.get("otdel_id", "") or params.get("id", "")
    if not otdel_id:
        return make_error("otdel_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.delete(f"{_API_BASE}/api/otdels/{otdel_id}")
        if res.status_code != 200:
            return make_error(f"Failed to delete otdel: {res.text}")

    return make_success({"status": "deleted", "otdel_id": otdel_id})
