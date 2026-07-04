"""EventBus — in-memory event store with WS fan-out.

Events are short-lived messages about things that happened in SynPin
(main agent finished, otdel completed, cron ran, etc). The bus:

  1) Stores events in memory (insertion-ordered dict).
  2) Broadcasts each new event to all connected WS clients via
     ws_broadcast (existing utility).
  3) Tracks read state per event id.

No persistence by design — events die with the process. Settings
live separately in events/settings.py.

The term "events" (not "notifications") is intentional: notifications
are one possible delivery channel (in-app toast today, Telegram /
desktop / email tomorrow). The bus is the umbrella concept.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class Event:
    id: str
    title: str
    body: str
    level: str  # 'info' | 'success' | 'warning' | 'error'
    source: str  # 'main_agent' | 'agent' | 'otdel' | 'cron' | 'system'
    source_ref: str | None
    created_at: float
    read_at: float | None = None


def _new_event(
    title: str,
    body: str,
    level: str = "info",
    source: str = "system",
    source_ref: str | None = None,
) -> Event:
    return Event(
        id=str(uuid.uuid4()),
        title=title,
        body=body,
        level=level,
        source=source,
        source_ref=source_ref,
        created_at=time.time(),
    )


class EventBus:
    """Thread-safe in-memory event store with WS fan-out."""

    def __init__(self) -> None:
        self._events: dict[str, Event] = {}
        self._lock = RLock()

    # ── Publish ──────────────────────────────────────────────────────
    def publish(
        self,
        title: str,
        body: str,
        level: str = "info",
        source: str = "system",
        source_ref: str | None = None,
    ) -> Event:
        """Create an event, store it, and broadcast it to WS clients."""
        ev = _new_event(title, body, level, source, source_ref)
        with self._lock:
            self._events[ev.id] = ev
        self._broadcast_new(ev)
        return ev

    # ── Queries ──────────────────────────────────────────────────────
    def list_unread(self) -> list[Event]:
        with self._lock:
            return [e for e in self._events.values() if e.read_at is None]

    def list_all(self, limit: int = 50) -> list[Event]:
        with self._lock:
            items = list(self._events.values())
        # Newest first; cap at `limit`.
        items.sort(key=lambda e: e.created_at, reverse=True)
        return items[:limit]

    def unread_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._events.values() if e.read_at is None)

    def get(self, event_id: str) -> Event | None:
        with self._lock:
            return self._events.get(event_id)

    # ── Mutations ────────────────────────────────────────────────────
    def mark_read(self, event_id: str) -> Event | None:
        with self._lock:
            ev = self._events.get(event_id)
            if ev is None or ev.read_at is not None:
                return ev
            ev.read_at = time.time()
        self._broadcast_read(ev)
        return ev

    def mark_all_read(self) -> int:
        now = time.time()
        with self._lock:
            targets = [e for e in self._events.values() if e.read_at is None]
            for e in targets:
                e.read_at = now
        for e in targets:
            self._broadcast_read(e)
        return len(targets)

    def clear(self) -> int:
        with self._lock:
            n = len(self._events)
            self._events.clear()
        _log.info("EventBus.clear: removed %d events", n)
        return n

    # ── WS fan-out ───────────────────────────────────────────────────
    def _broadcast_new(self, ev: Event) -> None:
        # Protocol fix (2026-07-04): frontend reads ev.id flat, so we flatten
        # the payload instead of wrapping in {"data": ...}. Matches the shape
        # that REST _serialize() returns, so handlers stay uniform.
        payload = asdict(ev)
        payload["type"] = "event:new"
        self._broadcast(payload)

    def _broadcast_read(self, ev: Event) -> None:
        # Same fix: flat shape (id + read_at on top level, with type tag).
        self._broadcast({
            "type": "event:read",
            "id": ev.id,
            "read_at": ev.read_at,
        })

    def _broadcast(self, event: dict[str, Any]) -> None:
        """Send to WS via the existing thread-safe broadcaster.

        Uses the same `..ws_broadcast` import pattern as every other
        module (api/widgets_router.py, agents/manager.py, etc).
        """
        from ..ws_broadcast import broadcast
        broadcast(event)


# ── Singleton + convenience helper ─────────────────────────────────
_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def publish_event(
    title: str,
    body: str,
    level: str = "info",
    source: str = "system",
    source_ref: str | None = None,
) -> Event:
    """Module-level helper for the common case: just publish, get the Event back."""
    return get_bus().publish(title, body, level, source, source_ref)