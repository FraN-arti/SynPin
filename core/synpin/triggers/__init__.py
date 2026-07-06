"""
Triggers — event-driven automation layer.

Public surface:
  - `TriggerEngine`  (engine.get_engine / engine.TriggerEngine)
  - `register_action` / `emit` / `start` / `stop` via engine instance
  - Definitions under `definitions/` (idle_head, etc.) are loaded by the
    registry, not by this package.
"""
from .engine import TriggerEngine, get_engine

__all__ = ["TriggerEngine", "get_engine"]
