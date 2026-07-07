"""
Triggers — base types for the trigger engine.

A trigger is a 3-part machine:
  source → condition → action

Definitions in `core/synpin/triggers/definitions/` are the templates
(user-editable metadata + execution logic). Instances in
`data/triggers/{otdel_id}.yaml` are the user's per-otdel
config — engine binds templates to instances at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .engine import TriggerEngine


@dataclass
class Event:
    """An event the engine can match against triggers.

    Payload is intentionally loose — each trigger plugin knows its own
    shape. Engine doesn't introspect.
    """
    type: str                       # matches TriggerInstance.type
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TriggerContext:
    """Read-only context passed to plugin tick() and action run().

    Plugins use this to read user config, current state, and emit
    downstream side effects (e.g. agent_prompt action sends a message).
    """
    engine: "TriggerEngine"
    now: datetime
    config: dict[str, Any]          # user config from instance
    action_config: dict[str, Any]    # user config for the action
    otdel_id: str = ""              # which otdel this instance is bound to


class TriggerPlugin:
    """Base class for trigger source plugins.

    Two flavors:
    - State-based: subclass sets `tick_interval`. Engine calls tick() on
      a schedule. Plugin scans state and returns events.
    - Reactive: subclass sets `tick_interval = 0`. Engine subscribes to
      external sources (webhook handler calls engine.emit() directly).

    Subclasses MUST set `type` (string) and SHOULD set `tick_interval`.
    Subclasses MUST implement `async def tick(ctx) -> list[Event]`.
    """
    type: str = ""
    tick_interval: int = 0           # seconds; 0 = reactive only

    async def tick(self, ctx: TriggerContext) -> list[Event]:
        """Called every tick_interval. Return 0+ events to enqueue."""
        return []


# ── Action plugins ─────────────────────────────────────────────────────

class ActionPlugin:
    """Base class for action plugins.

    Actions are simpler than triggers — they receive a single event and
    a config, do their thing, return. Engine has direct references to
    action classes (no plugin-style registry for actions — only a few,
    and they don't change often).
    """
    type: str = ""

    async def run(
        self,
        ctx: TriggerContext,
        event: Event,
    ) -> None:
        raise NotImplementedError
