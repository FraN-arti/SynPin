"""Centralized thread-safe WS broadcast utility.

All modules should use broadcast() instead of directly calling ws_manager.
Handles the AnyIO worker thread problem in one place.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

_log = logging.getLogger(__name__)

_ws_loop: asyncio.AbstractEventLoop | None = None


def init(loop: asyncio.AbstractEventLoop) -> None:
    """Call once at startup with the main event loop."""
    global _ws_loop
    _ws_loop = loop


def broadcast(event: dict[str, Any]) -> None:
    """Thread-safe broadcast to all connected WS clients.

    Works from any thread — schedules on the main event loop.
    """
    if _ws_loop is None:
        _log.warning("broadcast: no event loop set, event=%s", event.get("type"))
        return
    try:
        from .chat.ws_manager import ws_manager

        _log.debug("broadcast: %s (clients=%d)", event.get("type"), ws_manager.active_count)

        async def _send():
            await ws_manager.broadcast(event)

        asyncio.run_coroutine_threadsafe(_send(), _ws_loop)
    except Exception as e:
        _log.warning("broadcast failed: %s", e)
