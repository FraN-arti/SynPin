"""
Triggers — `kanban_stuck` source plugin.

Scans kanban tasks every `tick_interval` seconds and emits an event
for each task that has not been updated in `idle_minutes`. The watcher
only emits — it does NOT move tasks or change status. Movement is
the head agent's job (via head_decide / head_approve / etc.). This
plugin is a polite reminder: it tells the head "task X has been
sitting in stage Y for too long, take a look."

By default it watches tasks in `in_progress`, `review`, and
`revision` stages — the stages that benefit most from a nudge.
Tasks in `done`, `archived`, `blocked` (handled by auto_approval),
or `backlog` are ignored (low signal, high noise).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..base import Event, TriggerContext, TriggerPlugin

logger = logging.getLogger("synpin.triggers.kanban_stuck")

# Stages the watcher cares about. Other stages have their own
# handling (block escalation, manual archive) or are not work in
# flight (backlog, done, archived).
WATCHED_STAGES: tuple[str, ...] = ("in_progress", "review", "revision")


def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _task_age_minutes(task, now: datetime) -> int:
    last = getattr(task, "updated_at", None) or getattr(task, "created_at", None)
    if not last:
        return 0
    return int((now - _to_utc(last)).total_seconds() // 60)


class KanbanStuckPlugin(TriggerPlugin):
    type = "kanban_stuck"
    tick_interval = 300  # 5 minutes — quiet enough to not bother

    async def tick(self, ctx: TriggerContext) -> list[Event]:
        idle_min: int = int(ctx.config.get("idle_minutes", 120))
        events: list[Event] = []

        try:
            # Local import — patchable via monkeypatch in tests, and
            # avoids pulling kanban at module-load time.
            from synpin.kanban.service import KanbanService
            all_tasks = KanbanService().list_tasks()
        except Exception as e:  # noqa: BLE001 — log and skip
            logger.warning("kanban_stuck: failed to list tasks: %s", e)
            return events

        for task in all_tasks:
            stage = task.status.value if hasattr(task.status, "value") else str(task.status)
            if stage not in WATCHED_STAGES:
                continue
            age = _task_age_minutes(task, now=ctx.now)
            if age < idle_min:
                continue
            events.append(Event(
                type="kanban_stuck",
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
