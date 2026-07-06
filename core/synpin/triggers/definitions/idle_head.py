"""
Triggers — `idle_head` source plugin.

Scans otdels every `tick_interval` seconds and emits an event for each
otdel whose head agent has not produced a chat response within
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
        otdel_filter: str = ctx.config.get("otdel_filter", "")
        threshold_seconds = idle_minutes * 60
        events: list[Event] = []

        try:
            # Call via module attribute so tests can monkeypatch
            # `synpin.agents.manager.load_otdels` directly.
            otdels = agents_manager.load_otdels()
        except Exception as e:  # noqa: BLE001 — logged and skipped, not fatal
            logger.warning("idle_head: failed to load otdels: %s", e)
            return events

        for otdel in otdels:
            otdel_id = otdel.get("otdelid", "")
            if otdel_filter and otdel_id != otdel_filter:
                continue
            head_slug = otdel.get("head", "")
            if not head_slug:
                continue
            last = _last_response_at(head_slug)
            if last is None:
                # No history yet — treat as fresh activity, not idle.
                continue
            idle_seconds = (ctx.now - last).total_seconds()
            if idle_seconds >= threshold_seconds:
                events.append(Event(
                    type="idle_head",
                    payload={
                        "otdel_id": otdel_id,
                        "otdel_name": otdel.get("name", ""),
                        "head_slug": head_slug,
                        "idle_minutes": int(idle_seconds // 60),
                    },
                ))
        return events
