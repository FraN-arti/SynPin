"""
Triggers — `kanban_revision` source plugin.

Watches tasks in the `revision` stage and emits an event for any
task that has not been updated in `idle_minutes`. Rework cycles
should be tight — if a task is in revision too long, the head needs
a nudge.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..base import Event, TriggerContext, TriggerPlugin

logger = logging.getLogger("synpin.triggers.kanban_revision")


def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _task_age_minutes(task, now: datetime) -> int:
    last = getattr(task, "updated_at", None) or getattr(task, "created_at", None)
    if not last:
        return 0
    return int((now - _to_utc(last)).total_seconds() // 60)


class KanbanRevisionPlugin(TriggerPlugin):
    type = "kanban_revision"
    tick_interval = 300  # 5 minutes

    async def tick(self, ctx: TriggerContext) -> list[Event]:
        idle_min: int = int(ctx.config.get("idle_minutes", 60))
        events: list[Event] = []

        try:
            from synpin.kanban.service import KanbanService
            all_tasks = KanbanService().list_tasks()
        except Exception as e:  # noqa: BLE001
            logger.warning("kanban_revision: failed to list tasks: %s", e)
            return events

        for task in all_tasks:
            stage = task.status.value if hasattr(task.status, "value") else str(task.status)
            if stage != "revision":
                continue
            age = _task_age_minutes(task, now=ctx.now)
            if age < idle_min:
                continue
            events.append(Event(
                type="kanban_revision",
                payload={
                    "task_id": task.id,
                    "task_title": getattr(task, "title", "") or "",
                    "stage": stage,
                    "department": getattr(task, "department", "") or "",
                    "assigned_head": getattr(task, "assigned_head", "") or "",
                    "idle_minutes": age,
                },
            ))
        return events
