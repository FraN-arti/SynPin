"""Auto-escalation worker — escalates blocked tasks via connections.

Runs every 5 minutes (configurable via AUTO_ESCALATION_INTERVAL_S env var).
On each tick:
  1. Loads all connections with auto_trigger configured.
  2. For each escalation connection, finds tasks in the source department
     that match the trigger status (e.g. 'blocked').
  3. If a task has been in that status longer than timeout_s, escalates it
     to the target department.

Pattern follows deadline.py and auto_delete.py.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("synpin.connections.auto_escalation")


async def _run_escalation_pass() -> int:
    """Single pass: check all connections for auto-escalation triggers."""
    from .config import load_connections
    from .models import ConnectionType
    from .service import escalate_task

    connections = load_connections()
    escalated = 0

    for conn in connections:
        if not conn.active or conn.type != ConnectionType.ESCALATION:
            continue
        if not conn.auto_trigger:
            continue

        trigger_status = conn.auto_trigger.on_status
        timeout_s = conn.auto_trigger.timeout_s

        # Find tasks in source department with matching status
        tasks = _find_triggerable_tasks(conn.from_otdel, trigger_status, timeout_s)
        for task in tasks:
            try:
                record = escalate_task(
                    task_id=task.id,
                    from_otdel=conn.from_otdel,
                    to_otdel=conn.to_otdel,
                    reason=f"Auto-escalation: task in '{trigger_status}' for >{timeout_s}s",
                    report=f"Automatically escalated via connection {conn.id}",
                )
                if record:
                    escalated += 1
                    logger.info(
                        "[auto-escalation] %s: %s → %s via %s",
                        task.id, conn.from_otdel, conn.to_otdel, conn.id,
                    )
            except Exception as e:
                logger.warning("[auto-escalation] failed for %s: %s", task.id, e)

    return escalated


def _find_triggerable_tasks(otdel_slug: str, status: str, timeout_s: int) -> list:
    """Find tasks in otdel that have been in the given status longer than timeout."""
    try:
        from ..kanban.service import KanbanService
        from ..kanban.models import TaskStatus

        svc = KanbanService()
        tasks = svc.list_tasks()

        # Map status string to enum
        status_enum = None
        for s in TaskStatus:
            if s.value == status:
                status_enum = s
                break
        if not status_enum:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_s)
        result = []

        for task in tasks:
            if task.department != otdel_slug:
                continue
            if task.status != status_enum:
                continue
            # Check if task has been in this status long enough
            updated = task.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated < cutoff:
                result.append(task)

        return result
    except Exception as e:
        logger.warning("[auto-escalation] failed to find tasks: %s", e)
        return []


async def _auto_escalation_loop(interval_s: float) -> None:
    """Background task: run escalation check every interval_s seconds."""
    try:
        # First check 60s after startup
        await asyncio.sleep(60)
        while True:
            try:
                n = await _run_escalation_pass()
                if n > 0:
                    logger.info("[auto-escalation] this pass: %d task(s) escalated", n)
            except Exception as e:
                logger.warning("[auto-escalation] pass failed: %s", e)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        return


def schedule_auto_escalation(interval_s: float | None = None) -> "asyncio.Task | None":
    """Start the background auto-escalation worker."""
    if interval_s is None:
        try:
            interval_s = float(os.environ.get("AUTO_ESCALATION_INTERVAL_S", "300"))  # 5 min
        except ValueError:
            interval_s = 300.0
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(_auto_escalation_loop(interval_s))
