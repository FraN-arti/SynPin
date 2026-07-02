"""Head Protocol: interact with Kanban tasks.

Tool for heads to create tasks, write history, reassign, complete, etc.
"""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool
# Configurable API base URL (defaults to standard dev port)
_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")



@register_tool(
    name='kanban_task',
    description='Работа с канбан-тасками: создание, список, редактирование, удаление, архивация, история, переназначение, завершение, доработка, блокировка, начало работы, отправка на ревью, одобрение, статус.',
    category='other',
    scope='head',
    dangerous=False,
)
async def kanban_task(params: dict[str, Any]) -> ToolResult:
    """
    Interact with kanban tasks.

    Commands:
      create   — create a new task
      list     — list tasks for your department
      update   — edit title, description, priority, deadline, or tags
      delete   — permanently delete a task
      archive  — move task to archive
      history  — write a history entry
      reassign — transfer to another department
      complete — mark task as done
      rework   — send back for rework
      block    — mark task as blocked
      unblock  — unblock a blocked task
      start    — move task to in_progress
      submit   — submit work for review
      approve  — approve completed work
      status   — get task status

    Params:
      command: str — one of the above
      ...command-specific params (see below)
    """
    command = params.get("command", "")
    if not command:
        return make_error("command required: create, list, update, delete, archive, history, reassign, complete, rework, block, unblock, start, submit, approve, status")

    try:
        if command == "create":
            return await _create(params)
        elif command == "list":
            return await _list(params)
        elif command == "update":
            return await _update(params)
        elif command == "delete":
            return await _delete(params)
        elif command == "archive":
            return await _archive(params)
        elif command == "history":
            return await _history(params)
        elif command == "reassign":
            return await _reassign(params)
        elif command == "complete":
            return await _complete(params)
        elif command == "rework":
            return await _rework(params)
        elif command == "block":
            return await _block(params)
        elif command == "unblock":
            return await _unblock(params)
        elif command == "start":
            return await _start(params)
        elif command == "submit":
            return await _submit(params)
        elif command == "approve":
            return await _approve(params)
        elif command == "status":
            return await _status(params)
        else:
            return make_error(f"Unknown command: {command}. Use: create, list, update, delete, archive, history, reassign, complete, rework, block, unblock, start, submit, approve, status")
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

    department = params.get("department", "") or params.get("otdel_id", "")
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

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(f"{_API_BASE}/api/kanban/tasks", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to create task: {res.text}")
        task = res.json()

    return make_success({
        "task_id": task["id"],
        "status": task["status"],
        "message": f"Task created in column '{task['status']}'",
    })


# ── list ────────────────────────────────────────────────────────────────

async def _list(params: dict[str, Any]) -> ToolResult:
    """
    List tasks for a department.

    Params:
      department: str (optional) — department ID (otdel slug).
                  Falls back to otdel_id (auto-injected by system for head agents).
      status: str (optional) — filter by status (backlog/todo/in_progress/review/done/blocked)
    """
    import httpx

    # Accept both 'department' and 'otdel_id' (system-injected for head agents)
    department = params.get("department", "") or params.get("otdel_id", "")
    if not department:
        return make_error("department required (department ID / otdel slug)")

    status_filter = params.get("status", "")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/kanban/tasks/board")
        if res.status_code != 200:
            return make_error(f"Failed to get tasks: {res.text}")

        board = res.json()

    # Collect tasks for this department
    tasks = []
    for status_key, status_tasks in board.items():
        if isinstance(status_tasks, list):
            for t in status_tasks:
                if t.get("department") == department or t.get("current_department") == department:
                    if status_filter and status_key != status_filter:
                        continue
                    tasks.append({
                        "id": t.get("id", ""),
                        "title": t.get("title", ""),
                        "status": status_key,
                        "priority": t.get("priority", "medium"),
                        "assigned_head": t.get("assigned_head"),
                    })

    if not tasks:
        return make_success({"tasks": [], "message": f"No tasks found for department {department}"})

    return make_success({
        "tasks": tasks,
        "count": len(tasks),
        "department": department,
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

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"{_API_BASE}/api/kanban/tasks/{task_id}/history",
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

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"{_API_BASE}/api/kanban/tasks/{task_id}/summon",
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.patch(
            f"{_API_BASE}/api/kanban/tasks/{task_id}",
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.patch(
            f"{_API_BASE}/api/kanban/tasks/{task_id}",
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


# ── block ──────────────────────────────────────────────────────────────────

async def _block(params: dict[str, Any]) -> ToolResult:
    """
    Mark task as blocked — needs human help or external dependency.

    Params:
      task_id: str (required)
      reason: str (required) — why blocked
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
        "action": "blocked",
        "detail": reason,
        "actor": params.get("actor", "head"),
    })

    # Update status to blocked
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.patch(
            f"{_API_BASE}/api/kanban/tasks/{task_id}",
            json={"status": "blocked"},
        )
        if res.status_code != 200:
            return make_error(f"Failed to block task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "status": "blocked",
        "history_count": len(task.get("history", [])),
    })


# ── unblock ────────────────────────────────────────────────────────────────

async def _unblock(params: dict[str, Any]) -> ToolResult:
    """
    Unblock a blocked task — resume work.

    Params:
      task_id: str (required)
      reason: str — why unblocked
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    reason = params.get("reason", "Task unblocked")

    # Add history entry
    await _history({
        "task_id": task_id,
        "action": "unblocked",
        "detail": reason,
        "actor": params.get("actor", "head"),
    })

    # Update status to in_progress
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.patch(
            f"{_API_BASE}/api/kanban/tasks/{task_id}",
            json={"status": "in_progress"},
        )
        if res.status_code != 200:
            return make_error(f"Failed to unblock task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "status": "in_progress",
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

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{_API_BASE}/api/kanban/tasks/{task_id}")
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


# ── update ─────────────────────────────────────────────────────────────────

async def _update(params: dict[str, Any]) -> ToolResult:
    """
    Edit a task's fields.

    Params:
      task_id: str (required)
      title: str (optional)
      description: str (optional)
      priority: str (optional) — low/medium/high/critical
      deadline: str (optional) — ISO date
      tags: list[str] (optional)
      status: str (optional) — move to a different column/status
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    payload = {}
    for key in ("title", "description", "priority", "deadline", "tags", "status"):
        if key in params and params[key] is not None:
            payload[key] = params[key]

    if not payload:
        return make_error("Nothing to update — provide at least one of: title, description, priority, deadline, tags, status")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.patch(f"{_API_BASE}/api/kanban/tasks/{task_id}", json=payload)
        if res.status_code != 200:
            return make_error(f"Failed to update task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "task_id": task["id"],
        "status": task["status"],
        "title": task["title"],
        "updated_fields": list(payload.keys()),
    })


# ── delete ─────────────────────────────────────────────────────────────────

async def _delete(params: dict[str, Any]) -> ToolResult:
    """
    Permanently delete a task.

    Params:
      task_id: str (required)
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.delete(f"{_API_BASE}/api/kanban/tasks/{task_id}")
        if res.status_code != 200:
            return make_error(f"Failed to delete task: {res.text}")

    return make_success({
        "success": True,
        "deleted": task_id,
        "message": f"Task {task_id} permanently deleted",
    })


# ── archive ────────────────────────────────────────────────────────────────

async def _archive(params: dict[str, Any]) -> ToolResult:
    """
    Move task to archive.

    Params:
      task_id: str (required)
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(f"{_API_BASE}/api/kanban/tasks/{task_id}/archive")
        if res.status_code != 200:
            return make_error(f"Failed to archive task: {res.text}")

    return make_success({
        "success": True,
        "archived": task_id,
        "message": f"Task {task_id} archived",
    })


# ── start ──────────────────────────────────────────────────────────────────

async def _start(params: dict[str, Any]) -> ToolResult:
    """
    Mark task as in_progress (start working on it).

    Params:
      task_id: str (required)
      actor: str — who is starting (default: "head")
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"{_API_BASE}/api/kanban/tasks/{task_id}/start",
            json={"actor": params.get("actor", "head"), "detail": params.get("detail", "")},
        )
        if res.status_code != 200:
            return make_error(f"Failed to start task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "task_id": task["id"],
        "status": task["status"],
        "message": f"Task {task_id} now in progress",
    })


# ── submit ─────────────────────────────────────────────────────────────────

async def _submit(params: dict[str, Any]) -> ToolResult:
    """
    Submit completed work for review.

    Params:
      task_id: str (required)
      actor: str — who is submitting (default: "head")
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"{_API_BASE}/api/kanban/tasks/{task_id}/submit-review",
            json={"actor": params.get("actor", "head"), "detail": params.get("detail", "")},
        )
        if res.status_code != 200:
            return make_error(f"Failed to submit task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "task_id": task["id"],
        "status": task["status"],
        "message": f"Task {task_id} submitted for review",
    })


# ── approve ────────────────────────────────────────────────────────────────

async def _approve(params: dict[str, Any]) -> ToolResult:
    """
    Approve completed work — task moves to done.

    Params:
      task_id: str (required)
      actor: str — who is approving (default: "head")
      summary: str — optional completion summary
    """
    import httpx

    task_id = params.get("task_id", "")
    if not task_id:
        return make_error("task_id required")

    summary = params.get("summary", "")

    # Add history entry if summary provided
    if summary:
        await _history({
            "task_id": task_id,
            "action": "completed",
            "detail": summary,
            "actor": params.get("actor", "head"),
        })

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"{_API_BASE}/api/kanban/tasks/{task_id}/approve",
            json={"actor": params.get("actor", "head"), "detail": summary or "Approved"},
        )
        if res.status_code != 200:
            return make_error(f"Failed to approve task: {res.text}")
        task = res.json()

    return make_success({
        "success": True,
        "task_id": task["id"],
        "status": task["status"],
        "completed_at": task.get("completed_at"),
        "message": f"Task {task_id} approved and done",
    })


__all__ = ["kanban_task"]
