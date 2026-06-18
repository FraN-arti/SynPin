"""Deadline checker — periodic scan of kanban tasks for approaching/overdue deadlines.

Runs every 5 minutes (configurable via DEADLINE_CHECK_INTERVAL_S env var).
On each tick:
  1. Loads all tasks with a deadline set.
  2. For tasks approaching deadline (< 1 hour, not yet warned):
     - Broadcasts WS event 'kanban:deadline_warning' so the frontend can
       highlight the task and show a notification.
  3. For overdue tasks (deadline passed, not done/blocked):
     - Auto-escalates: status → BLOCKED, adds history entry.
     - Broadcasts WS event 'kanban:deadline_overdue'.

Pattern follows auto_delete.py — same async loop, same WS broadcast.

Frontend listens for:
  - kanban:deadline_warning  — {task_id, title, deadline, minutes_left}
  - kanban:deadline_overdue  — {task_id, title, deadline, overdue_hours}
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("synpin.kanban.deadline")

# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_iso(dt_str: str | datetime | None) -> datetime | None:
    """Best-effort ISO timestamp parser (same as auto_delete)."""
    if not dt_str:
        return None
    if isinstance(dt_str, datetime):
        if dt_str.tzinfo is None:
            return dt_str.replace(tzinfo=timezone.utc)
        return dt_str
    s = str(dt_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


# ── Core logic ──────────────────────────────────────────────────────────────

# Track which tasks we've already warned about (so we don't spam every 5 min)
_warned: set[str] = set()
_overdue: set[str] = set()


async def _run_deadline_check(svc: Any) -> tuple[list[dict], list[dict]]:
    """Single pass: check all tasks for deadline issues.

    Returns (warnings, overdues) — each is a list of event payloads
    ready to broadcast via WS.
    """
    from .models import TaskStatus

    warnings: list[dict] = []
    overdues: list[dict] = []

    now = datetime.now(timezone.utc)
    warn_threshold = now + timedelta(hours=1)  # warn 1 hour before

    # Scan all tasks (not just one status — deadline applies everywhere)
    all_tasks = svc.list_tasks()

    for task in all_tasks:
        deadline = _parse_iso(getattr(task, "deadline", None))
        if deadline is None:
            continue

        # Normalize: ensure timezone-aware (some tasks store naive datetimes)
        try:
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        task_id = task.id
        status = getattr(task, "status", "")

        # Skip completed/blocked tasks
        if status in (TaskStatus.DONE, TaskStatus.BLOCKED):
            _warned.discard(task_id)
            _overdue.discard(task_id)
            continue

        # ── Overdue check ───────────────────────────────────────────
        if deadline < now:
            if task_id not in _overdue:
                _overdue.add(task_id)
                overdue_hours = round((now - deadline).total_seconds() / 3600, 1)

                # Auto-escalate: move to blocked
                try:
                    task.status = TaskStatus.BLOCKED
                    task.escalation_reason = f"Дедлайн просрочен на {overdue_hours}ч"
                    task.add_history(
                        actor="system",
                        action="escalated",
                        detail=f"Автоматическая эскалация: дедлайн {deadline.isoformat()} просрочен на {overdue_hours}ч",
                    )
                    svc.save_task(task)
                    logger.info("[deadline] OVERDUE: %s (%s) — escalated to blocked", task_id, task.title[:40])
                except Exception as e:
                    logger.warning("[deadline] failed to escalate %s: %s", task_id, e)

                overdues.append({
                    "task_id": task_id,
                    "title": task.title,
                    "deadline": deadline.isoformat(),
                    "overdue_hours": overdue_hours,
                    "department": getattr(task, "department", ""),
                })
            continue

        # ── Warning check (approaching deadline) ────────────────────
        if deadline < warn_threshold and task_id not in _warned and task_id not in _overdue:
            _warned.add(task_id)
            minutes_left = round((deadline - now).total_seconds() / 60)

            logger.info("[deadline] WARNING: %s (%s) — %d min left", task_id, task.title[:40], minutes_left)

            warnings.append({
                "task_id": task_id,
                "title": task.title,
                "deadline": deadline.isoformat(),
                "minutes_left": minutes_left,
                "department": getattr(task, "department", ""),
            })

    return warnings, overdues


# ── WS broadcast ────────────────────────────────────────────────────────────

async def _broadcast(events: list[dict], event_type: str) -> None:
    """Push events to all WS clients."""
    if not events:
        return
    try:
        from ..chat.ws_manager import ws_manager
        for evt in events:
            evt["type"] = event_type
            await ws_manager.broadcast(evt)
    except Exception as e:
        logger.warning("[deadline] WS broadcast failed: %s", e)


# ── Background loop ─────────────────────────────────────────────────────────

async def _deadline_loop(svc: Any, interval_s: float) -> None:
    """Background task: check deadlines every interval_s seconds."""
    # First check 30s after startup
    try:
        await asyncio.sleep(30)
        while True:
            try:
                warnings, overdues = await _run_deadline_check(svc)
                if warnings:
                    await _broadcast(warnings, "kanban:deadline_warning")
                    logger.info("[deadline] %d warning(s) sent", len(warnings))
                if overdues:
                    await _broadcast(overdues, "kanban:deadline_overdue")
                    logger.info("[deadline] %d overdue task(s) escalated", len(overdues))
            except Exception as e:
                logger.warning("[deadline] check pass failed: %s", e)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        return


def schedule_deadline_checker(svc: Any, interval_s: float | None = None) -> "asyncio.Task | None":
    """Start the background deadline checker.

    Returns the asyncio.Task so the caller can cancel it on shutdown.
    """
    if interval_s is None:
        try:
            interval_s = float(os.environ.get("DEADLINE_CHECK_INTERVAL_S", "300"))  # 5 min default
        except ValueError:
            interval_s = 300.0
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(_deadline_loop(svc, interval_s))
