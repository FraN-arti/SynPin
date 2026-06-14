"""Head Protocol: interact with Kanban tasks.

Tool for heads to create tasks, write history, reassign, complete, etc.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import ToolResult, make_success, make_error


async def kanban_task(params: dict[str, Any]) -> ToolResult:
    """
    Interact with kanban tasks.

    Commands:
      create   — create a new task
      history  — write a history entry
      reassign — transfer to another department
      complete — mark task as done
      rework   — send back for rework
      status   — get task status

    Params:
      command: str — one of the above
      ...command-specific params (see below)
    """
    command = params.get("command", "")
    if not command:
        return make_error("command required: create, history, reassign, complete, rework, status")

    try:
        if command == "create":
            return await _create(params)
        elif command == "history":
            return await _history(params)
        elif command == "reassign":
            return await _reassign(params)
        elif command == "complete":
            return await _complete(params)
        elif command == "rework":
            return await _rework(params)
        elif command == "status":
            return await _status(params)
        else:
            return make_error(f"Unknown command: {command}. Use: create, history, reassign, complete, rework, status")
    except Exception as e:
        return make_error(f"kanban_task error: {e}")


# ── create ──────────────────────────────────────────────────────────────────

async def _create(params: dict[str, Any]) -> ToolResult:
    """
    Create a new kanban task.

    Params:
      title: str (required)
      description: str
      department: str (required) — department ID
      priority: str (low/medium/high/critical)
      deadline: str (ISO date)
      tags: list[str]
    """
    import httpx

    title = params.get("title", "")
    if not title:
        return make_error("title required")

    department = params.get("department", "")
    if not department:
        return make_error("department required (department ID)")

    payload = {
        "title": title,
        "description": params.get("description", ""),
        "department": department,
        "priority": params.get("priority", "medium"),
        "tags": params.get("tags", []),
    }

    deadline = params.get("deadline")
    if deadline:
        payload["deadline"] = deadline

    async with httpx.AsyncClient() as client:
        res = await client.post("http://127.0.0.1:2088/api/kanban/tasks", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to create task: {res.text}")
        task = res.json()

    return make_success({
        "task_id": task["id"],
        "status": task["status"],
        "message": f"Task created in column '{task['status']}'",
    })


# ── history ─────────────────────────────────────────────────────────────────

async def _history(params: dict[str, Any]) -> ToolResult:
    """
    Write a history entry to an existing task.

    Params:
      task_id: str (required)
      action: str (required) — delegated/responded/rework/completed/comment
      detail: str (required) — what happened
      target_agent: str — if delegating to a specific agent
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    action = params.get("action", "")
    if not action:
        return make_error("action required (delegated/responded/rework/completed/comment)")

    detail = params.get("detail", "")
    if not detail:
        return make_error("detail required")

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"http://127.0.0.1:2088/api/kanban/tasks/{task_id}/history",
            json={
                "actor": params.get("actor", "head"),
                "action": action,
                "detail": detail,
                "target_agent": params.get("target_agent"),
                "target_department": params.get("target_department"),
            },
        )
        if res.status_code != 200:
            return make_error(f"Failed to add history: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "history_count": len(task.get("history", [])),
    })


# ── reassign ────────────────────────────────────────────────────────────────

async def _reassign(params: dict[str, Any]) -> ToolResult:
    """
    Reassign task to another department.

    Params:
      task_id: str (required)
      target_department: str (required) — new department ID
      reason: str (required) — why reassigning
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    target = params.get("target_department", "")
    if not target:
        return make_error("target_department required")

    reason = params.get("reason", "")
    if not reason:
        return make_error("reason required")

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"http://127.0.0.1:2088/api/kanban/tasks/{task_id}/summon",
            json={
                "target_department": target,
                "reason": reason,
                "actor": params.get("actor", "head"),
            },
        )
        if res.status_code != 200:
            return make_error(f"Failed to reassign: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "new_department": task.get("current_department"),
        "summon_chain": task.get("summon_chain", []),
    })


# ── complete ────────────────────────────────────────────────────────────────

async def _complete(params: dict[str, Any]) -> ToolResult:
    """
    Mark task as done.

    Params:
      task_id: str (required)
      summary: str — completion summary
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    summary = params.get("summary", "")

    # Add history entry
    await _history({
        "task_id": task_id,
        "action": "completed",
        "detail": summary or "Task completed",
        "actor": params.get("actor", "head"),
    })

    # Update status to done
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"http://127.0.0.1:2088/api/kanban/tasks/{task_id}",
            json={"status": "done"},
        )
        if res.status_code != 200:
            return make_error(f"Failed to complete task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "status": "done",
        "completed_at": task.get("completed_at"),
    })


# ── rework ──────────────────────────────────────────────────────────────────

async def _rework(params: dict[str, Any]) -> ToolResult:
    """
    Send task back for rework (stays in revision column).

    Params:
      task_id: str (required)
      reason: str (required) — what needs to be redone
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    reason = params.get("reason", "")
    if not reason:
        return make_error("reason required")

    # Add history entry
    await _history({
        "task_id": task_id,
        "action": "rework",
        "detail": reason,
        "actor": params.get("actor", "head"),
    })

    # Update status to revision
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"http://127.0.0.1:2088/api/kanban/tasks/{task_id}",
            json={"status": "revision"},
        )
        if res.status_code != 200:
            return make_error(f"Failed to send for rework: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "status": "revision",
        "history_count": len(task.get("history", [])),
    })


# ── status ──────────────────────────────────────────────────────────────────

async def _status(params: dict[str, Any]) -> ToolResult:
    """
    Get current task status.

    Params:
      task_id: str (required)
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    async with httpx.AsyncClient() as client:
        res = await client.get(f"http://127.0.0.1:2088/api/kanban/tasks/{task_id}")
        if res.status_code != 200:
            return make_error(f"Task {task_id} not found")
        task = res.json()

    history = task.get("history", [])
    last = history[-1] if history else None

    return make_success({
        "task_id": task["id"],
        "title": task["title"],
        "status": task["status"],
        "department": task.get("department"),
        "assigned_workers": task.get("assigned_workers", []),
        "history_count": len(history),
        "last_history": last,
    })


__all__ = ["kanban_task"]
