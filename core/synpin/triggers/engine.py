"""
Triggers — runtime engine.

Lifecycle:
  1. `start()` — load definitions from registry, load instances from
     `data/triggers/`, spawn one watcher task per plugin (state-based
     triggers only), spawn one event-processor task.
  2. Watchers call `tick()` on their interval and emit events via
     `engine.emit(event)`.
  3. Event processor matches each event against enabled instances of
     the same type, then runs the configured action in a background
     task.
  4. Definitions are rescanned periodically (hot-reload). New types
     appear in the registry; existing watcher tasks are cancelled and
     replaced when a plugin's tick_interval changes.

Reactive plugins (tick_interval = 0) don't get a watcher — they emit
events through the same `emit()` API, typically from a webhook
handler in `api/`.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from . import registry as registry_mod
from . import store
from .base import Event, TriggerContext, TriggerPlugin

logger = logging.getLogger("synpin.triggers.engine")


# Hard cap to keep memory bounded if a runaway trigger floods events.
QUEUE_MAX = 1000
# How often the definitions directory is rescanned for new plugins.
RESCAN_INTERVAL = 30  # seconds


class TriggerEngine:
    def __init__(self) -> None:
        self.definitions: dict[str, registry_mod.Definition] = {}
        # List of {instance dict} loaded from data/triggers/*.yaml.
        self.instances: list[dict[str, Any]] = []
        # Resolved (type → plugin instance) for the current registry.
        self._plugins: dict[str, TriggerPlugin] = {}
        # Background tasks: one per plugin watcher + one event processor.
        self._watcher_tasks: dict[str, asyncio.Task] = {}
        self._processor_task: asyncio.Task | None = None
        self._rescan_task: asyncio.Task | None = None
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=QUEUE_MAX)
        # Set by event processor so actions can attribute the current
        # trigger instance to their logs / follow-up events.
        self._current_trigger_id: str | None = None
        # Set by the engine during start; lets callers `await start()`.
        self._started = False
        # Action class registry (not plugin-style — small, fixed set).
        self._actions: dict[str, Any] = {}

    # ── Public API ────────────────────────────────────────────────

    def register_action(self, action: Any) -> None:
        """Register an ActionPlugin instance.

        Engine reuses the same instance for every dispatch of this
        action type, so subclasses can keep state on `self` (e.g. a
        counter, last-fire timestamp, in-memory buffer for tests).
        """
        self._actions[action.type] = action

    async def start(self) -> None:
        if self._started:
            return
        self.definitions = registry_mod.scan()
        logger.info(
            "trigger engine: loaded %d definitions: %s",
            len(self.definitions), list(self.definitions.keys()),
        )
        self._instantiate_plugins()
        self._load_instances()
        self._processor_task = asyncio.create_task(self._process_events())
        self._spawn_watchers()
        self._rescan_task = asyncio.create_task(self._rescan_loop())
        self._started = True

    async def stop(self) -> None:
        for t in self._watcher_tasks.values():
            t.cancel()
        if self._processor_task:
            self._processor_task.cancel()
        if self._rescan_task:
            self._rescan_task.cancel()
        for t in list(self._watcher_tasks.values()) + [self._processor_task, self._rescan_task]:
            if t is None:
                continue
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._started = False

    async def emit(self, event: Event) -> None:
        """Enqueue an event. Called by watchers and external sources."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "trigger engine: queue full (size=%d), dropping event type=%s",
                self._queue.maxsize, event.type,
            )

    def reload_instances(self) -> None:
        """Re-read instance YAMLs. Call after PUT /api/triggers/..."""
        self._load_instances()
        logger.info("trigger engine: reloaded %d instances", len(self.instances))

    # ── Internals ─────────────────────────────────────────────────

    def _instantiate_plugins(self) -> None:
        self._plugins = {
            t: d.plugin_cls() for t, d in self.definitions.items()
        }

    def _load_instances(self) -> None:
        self.instances = store.all_instances()

    def _spawn_watchers(self) -> None:
        # Cancel any stale tasks first.
        for t in self._watcher_tasks.values():
            t.cancel()
        self._watcher_tasks.clear()
        for type_name, plugin in self._plugins.items():
            if plugin.tick_interval <= 0:
                continue
            task = asyncio.create_task(self._watcher_loop(type_name, plugin))
            self._watcher_tasks[type_name] = task

    async def _watcher_loop(self, type_name: str, plugin: TriggerPlugin) -> None:
        # Stagger initial ticks so all watchers don't fire at the same time.
        await asyncio.sleep(min(plugin.tick_interval, 5))
        while True:
            try:
                ctx = TriggerContext(
                    engine=self,
                    now=datetime.now(timezone.utc),
                    config={},  # per-instance config injected below
                    action_config={},
                )
                # Pass the config from the first matching instance, or empty
                # if none. The plugin uses config in `ctx.config`; we run
                # the tick once per instance to get per-otdel results.
                events: list[Event] = []
                matching_instances = [i for i in self.instances if i.get("type") == type_name and i.get("enabled", True)]
                for inst in matching_instances:
                    ctx.config = inst.get("config", {}) or {}
                    ctx.action_config = (inst.get("action") or {}).get("config", {}) or {}
                    ctx.engine._current_trigger_id = inst.get("id", "")
                    try:
                        events.extend(await plugin.tick(ctx))
                    except Exception as e:  # noqa: BLE001 — keep watcher alive
                        logger.exception("trigger %s tick failed: %s", type_name, e)
                for ev in events:
                    await self.emit(ev)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.exception("trigger watcher %s loop error: %s", type_name, e)
            await asyncio.sleep(plugin.tick_interval)

    async def _process_events(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                await self._dispatch(event)
            except Exception as e:  # noqa: BLE001
                logger.exception("event dispatch failed for type=%s: %s", event.type, e)

    async def _dispatch(self, event: Event) -> None:
        for inst in self.instances:
            if inst.get("type") != event.type:
                continue
            if not inst.get("enabled", True):
                continue
            action_def = inst.get("action") or {}
            action_type = action_def.get("type", "log")
            action = self._actions.get(action_type)
            if action is None:
                logger.warning(
                    "trigger instance %s: unknown action type=%s",
                    inst.get("id", "?"), action_type,
                )
                continue
            ctx = TriggerContext(
                engine=self,
                now=event.timestamp,
                config=inst.get("config", {}) or {},
                action_config=action_def.get("config", {}) or {},
            )
            self._current_trigger_id = inst.get("id", "")
            try:
                await action.run(ctx, event)
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "trigger action %s failed for instance %s: %s",
                    action_type, inst.get("id", "?"), e,
                )
            finally:
                self._current_trigger_id = None

    async def _rescan_loop(self) -> None:
        while True:
            await asyncio.sleep(RESCAN_INTERVAL)
            try:
                new_defs = registry_mod.scan()
                if registry_mod.has_changed(self.definitions, new_defs):
                    logger.info(
                        "trigger engine: definitions changed, hot-reloading (%s → %s)",
                        list(self.definitions.keys()),
                        list(new_defs.keys()),
                    )
                    self.definitions = new_defs
                    self._instantiate_plugins()
                    self._spawn_watchers()
            except Exception as e:  # noqa: BLE001
                logger.exception("trigger rescan failed: %s", e)


# ── Module-level singleton ────────────────────────────────────────────

_engine: TriggerEngine | None = None


def get_engine() -> TriggerEngine:
    global _engine
    if _engine is None:
        _engine = TriggerEngine()
    return _engine
