"""
Triggers — `kanban_in_review` source plugin.

Watches tasks in the `review` stage for the bound otdel and emits an
event for any task that has not been updated in `idle_minutes`.

Why a separate plugin from kanban_stuck: per-stage timeouts differ.
Review should be tight (heads check quickly), in_progress is more
forgiving. Splitting plugins lets each otdel tune its own thresholds.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..base import Event, TriggerContext, TriggerPlugin

logger = logging.getLogger("synpin.triggers.kanban_in_review")


def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _task_age_minutes(task, now: datetime) -> int:
    last = getattr(task, "updated_at", None) or getattr(task, "created_at", None)
    if not last:
        return 0
    return int((now - _to_utc(last)).total_seconds() // 60)


class KanbanInReviewPlugin(TriggerPlugin):
    type = "kanban_in_review"
    tick_interval = 300  # 5 minutes

    async def tick(self, ctx: TriggerContext) -> list[Event]:
        idle_min: int = int(ctx.config.get("idle_minutes", 60))
        events: list[Event] = []

        otdel_id = ctx.otdel_id
        if not otdel_id:
            return events

        try:
            from synpin.kanban.service import KanbanService
            tasks = KanbanService().list_tasks()
        except Exception as e:  # noqa: BLE001
            logger.warning("kanban_in_review: failed to list tasks: %s", e)
            return events

        for task in tasks:
            stage = task.status.value if hasattr(task.status, "value") else str(task.status)
            if stage != "review":
                continue
            # Per-otdel scope — instance is bound to one otdel.
            dept = getattr(task, "department", "") or ""
            if dept not in (otdel_id, f"otdel:{otdel_id}"):
                continue
            age = _task_age_minutes(task, now=ctx.now)
            if age < idle_min:
                continue
            events.append(Event(
                type="kanban_in_review",
                payload={
                    "task_id": task.id,
                    "task_title": getattr(task, "title", "") or "",
                    "stage": stage,
                    "department": otdel_id,
                    "assigned_head": getattr(task, "assigned_head", "") or "",
                    "idle_minutes": age,
                    "otdel_id": otdel_id,
                },
            ))
        return events
