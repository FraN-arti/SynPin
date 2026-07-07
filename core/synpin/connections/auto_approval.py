"""Auto-approval worker — approves blocked tasks via connections.

Runs every 5 minutes (configurable via AUTO_APPROVAL_INTERVAL_S env var).
On each tick:
  1. Loads all connections with auto_trigger configured.
  2. For each approval connection, finds tasks in the source department
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

logger = logging.getLogger("synpin.connections.auto_approval")


async def _run_approval_pass() -> int:
    """Single pass: check all connections for auto-approval triggers."""
    from .config import load_connections
    from .models import ConnectionType
    from .service import escalate_task

    connections = load_connections()
    escalated = 0

    for conn in connections:
        if not conn.active or conn.type != ConnectionType.APPROVAL:
            continue
        if not conn.auto_trigger:
            continue

        trigger_status = conn.auto_trigger.on_status
        timeout_s = conn.auto_trigger.timeout_s

        # Auto-approval only makes sense when the source is an otdel
        # (tasks have a `department` field, agents don't). If the
        # connection source is the primary agent, skip — it would
        # never match any task.
        from .refs import parse_ref
        from .resolve import resolve_ref
        from_kind, _ = parse_ref(conn.from_otdel)
        if from_kind == "agent":
            logger.debug(
                "[auto-approval] skip conn %s: source is primary agent, no tasks to escalate",
                conn.id,
            )
            continue
        source_otdel = resolve_ref(conn.from_otdel).id

        # Find tasks in source department with matching status
        tasks = _find_triggerable_tasks(source_otdel, trigger_status, timeout_s)
        for task in tasks:
            try:
                record = escalate_task(
                    task_id=task.id,
                    from_otdel=conn.from_otdel,
                    to_otdel=conn.to_otdel,
                    reason=f"Auto-approval: task in '{trigger_status}' for >{timeout_s}s",
                    report=f"Automatically approved via connection {conn.id}",
                )
                if record:
                    escalated += 1
                    logger.info(
                        "[auto-approval] %s: %s → %s via %s",
                        task.id, conn.from_otdel, conn.to_otdel, conn.id,
                    )
            except Exception as e:
                logger.warning("[auto-approval] failed for %s: %s", task.id, e)

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


async def _auto_approval_loop(interval_s: float) -> None:
    """Background task: run approval check every interval_s seconds."""
    try:
        # First check 60s after startup
        await asyncio.sleep(60)
        while True:
            try:
                n = await _run_approval_pass()
                if n > 0:
                    logger.info("[auto-approval] this pass: %d task(s) approved", n)
            except Exception as e:
                logger.warning("[auto-approval] pass failed: %s", e)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        return


def schedule_auto_approval(interval_s: float | None = None) -> "asyncio.Task | None":
    """Start the background auto-approval worker."""
    if interval_s is None:
        try:
            interval_s = float(os.environ.get("AUTO_APPROVAL_INTERVAL_S", "300"))  # 5 min
        except ValueError:
            interval_s = 300.0
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(_auto_approval_loop(interval_s))
