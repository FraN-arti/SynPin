"""
Triggers — `idle_head` source plugin.

Scans every `tick_interval` seconds and emits an event when the head
agent of the bound otdel has not produced a chat response within
`idle_minutes`. Reads the last assistant message timestamp from
`core/synpin/data/agents/{head_slug}/sessions/web.json`.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from synpin.agents import manager as agents_manager
from ..base import Event, TriggerContext, TriggerPlugin

logger = logging.getLogger("synpin.triggers.idle_head")

DATA_DIR = Path("core/synpin/data/agents")
SESSIONS_FILE = "sessions/web.json"


def _last_response_at(head_slug: str) -> datetime | None:
    """Return the most recent assistant timestamp for an agent, or None."""
    if not head_slug:
        return None
    path = DATA_DIR / head_slug / SESSIONS_FILE
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            messages = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("idle_head: cannot read %s: %s", path, e)
        return None
    if not isinstance(messages, list):
        return None
    # Walk backwards — last assistant message is what we want.
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("timestamp"):
            try:
                ts = datetime.fromisoformat(msg["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
            except ValueError:
                continue
    return None


class IdleHeadPlugin(TriggerPlugin):
    type = "idle_head"
    tick_interval = 60  # seconds; one watcher tick per minute

    async def tick(self, ctx: TriggerContext) -> list[Event]:
        idle_minutes: int = int(ctx.config.get("idle_minutes", 30))
        threshold_seconds = idle_minutes * 60
        events: list[Event] = []

        # Instance is bound directly to an otdel.
        otdel_id = ctx.otdel_id
        if not otdel_id:
            return events

        try:
            otdels = agents_manager.load_otdels()
        except Exception as e:  # noqa: BLE001
            logger.warning("idle_head: failed to load otdels: %s", e)
            return events

        target_otdel = next(
            (o for o in otdels if o.get("otdelid") == otdel_id),
            None,
        )
        if not target_otdel:
            return events

        head_slug = target_otdel.get("head", "")
        if not head_slug:
            return events

        last = _last_response_at(head_slug)
        if last is None:
            # No history yet — treat as fresh activity, not idle.
            return events
        idle_seconds = (ctx.now - last).total_seconds()
        if idle_seconds < threshold_seconds:
            return events

        # Skip if the otdel has no active tasks — the head has nothing
        # to act on, so a nudge would just be noise. Silent no-op.
        active_tasks = _count_active_tasks_for_otdel(otdel_id)
        if active_tasks == 0:
            logger.debug(
                "idle_head: %s head idle %dm but no active tasks — silent",
                otdel_id, int(idle_seconds // 60),
            )
            return events

        events.append(Event(
            type="idle_head",
            payload={
                "otdel_id": otdel_id,
                "otdel_name": target_otdel.get("name", ""),
                "head_slug": head_slug,
                "idle_minutes": int(idle_seconds // 60),
                "active_tasks": active_tasks,
            },
        ))
        return events


def _count_active_tasks_for_otdel(otdel_id: str) -> int:
    """How many non-done, non-archived tasks the otdel currently has.

    Pulled from the kanban service. We do this defensively — if the
    service can't be imported or fails, we fall back to "assume work
    exists" (i.e. don't suppress) rather than wrongly silencing.
    """
    try:
        from synpin.kanban.service import KanbanService
        tasks = KanbanService().list_tasks()
    except Exception as e:  # noqa: BLE001
        logger.debug("idle_head: cannot list tasks, assume active: %s", e)
        return 1
    active = 0
    for t in tasks:
        dept = getattr(t, "department", "") or ""
        if dept not in (otdel_id, f"otdel:{otdel_id}"):
            continue
        status = t.status.value if hasattr(t.status, "value") else str(t.status)
        if status in ("done", "archived"):
            continue
        active += 1
    return active
