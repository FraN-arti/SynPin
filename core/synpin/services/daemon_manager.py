"""DaemonManager — unified background service manager.

Replaces scattered daemon threads with a single registry.
Each service implements a run() coroutine, and DaemonManager
takes care of the loop, error handling, and lifecycle.

Usage:
    dm = DaemonManager()
    dm.register("cron", start_cron_scheduler)      # asyncio task
    dm.register("session-reset", session_reset_fn)  # sync threaded
    dm.start()
"""

from __future__ import annotations
import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class DaemonService:
    """A registered background service."""

    def __init__(
        self,
        name: str,
        callback: Callable[[], Awaitable[None]] | Callable[[], None],
        interval: float = 60.0,
        is_async: bool = True,
    ):
        self.name = name
        self.callback = callback
        self.interval = interval
        self.is_async = is_async
        self._task: asyncio.Task | None = None
        self._thread: threading.Thread | None = None


class DaemonManager:
    """Central manager for all background daemons."""

    def __init__(self):
        self._services: dict[str, DaemonService] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(
        self,
        name: str,
        callback: Callable[[], Awaitable[None]] | Callable[[], None],
        interval: float = 60.0,
        is_async: bool = True,
    ) -> DaemonService:
        """Register a background service.

        Args:
            name: Unique service name
            callback: Async or sync callable that performs one tick
            interval: Seconds between ticks
            is_async: True for asyncio tasks, False for thread daemon
        """
        svc = DaemonService(name, callback, interval, is_async)
        self._services[name] = svc
        logger.debug("[daemon] Registered: %s (interval=%ss, async=%s)", name, interval, is_async)
        return svc

    def start(self) -> None:
        """Start all registered services."""
        for name, svc in self._services.items():
            self._start_one(svc)

    def _start_one(self, svc: DaemonService) -> None:
        """Start a single service."""
        if svc.is_async:
            try:
                loop = asyncio.get_running_loop()
                svc._task = loop.create_task(self._async_loop(svc))
                logger.debug("[daemon] Started async task: %s", svc.name)
            except RuntimeError:
                logger.warning("[daemon] No running event loop, deferring: %s", svc.name)
        else:
            svc._thread = threading.Thread(
                target=self._sync_loop,
                args=(svc,),
                daemon=True,
                name=f"daemon-{svc.name}",
            )
            svc._thread.start()
            logger.debug("[daemon] Started thread: %s", svc.name)

    async def _async_loop(self, svc: DaemonService) -> None:
        """Run an async service loop."""
        while True:
            try:
                await svc.callback()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[daemon] %s error: %s", svc.name, e)
            await asyncio.sleep(svc.interval)

    def _sync_loop(self, svc: DaemonService) -> None:
        """Run a sync (threaded) service loop."""
        while True:
            try:
                result = svc.callback()
                if asyncio.iscoroutine(result):
                    logger.warning("[daemon] %s returned coroutine but registered as sync", svc.name)
            except Exception as e:
                logger.error("[daemon] %s error: %s", svc.name, e)
            time.sleep(svc.interval)

    def stop(self) -> None:
        """Stop all services."""
        for name, svc in self._services.items():
            if svc._task and not svc._task.done():
                svc._task.cancel()
            # Threads are daemon, no need to join
        logger.info("[daemon] All services stopped")
