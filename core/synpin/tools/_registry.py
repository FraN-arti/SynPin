"""Lightweight registry for auto-discovered SynPin tools.

Single source of truth: every handler in this package that should be
exposed to the LLM must be wrapped in `@register_tool(...)`. The chat
router reads from `all_tools()` to build the JSON-schema sent to the
model, and `get_tool(name)` returns the callable for execution.

Migration plan (incremental, no big-bang):
  1. This file exists in isolation — nothing imports it yet.
  2. Handlers adopt @register_tool one by one, alongside the existing
     _tool_handlers dict in tools/__init__.py.
  3. Once all 30 handlers migrated, __init__.py drops its manual dict
     and tools/__init__.py only re-exports for back-compat.
  4. chat/router.py:_NATIVE_TOOL_DEFS migrates from a hand-written dict
     to all_tools() at module load.

Scope classification is intentionally minimal — the role policy
(BUILTINS / HEAD_TOOLS / PRIMARY_TOOLS in chat/router.py) is a separate
concern and will move to its own metadata alongside this file once
all handlers carry @register_tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .base import ToolHandler

# Valid scope values for @register_tool. Mirrors the BUILTINS / HEAD /
# PRIMARY constants in chat/router.py so we can do a 1:1 mapping during
# migration without touching every call site at once.
Scope = Literal["all", "head", "primary", "builtin"]


@dataclass(frozen=True)
class ToolSpec:
    """Static metadata for one tool, captured by @register_tool."""

    name: str
    description: str
    category: str
    scope: Scope
    dangerous: bool
    func: ToolHandler
    # Optional pydantic-style parameters schema. When None, the chat
    # router derives parameters from the function signature via
    # introspection. Most tools don't need this for the first cut.
    parameters: dict[str, Any] | None = field(default=None)


# Module-level registry. Populated by @register_tool decorators at
# import time. Single dict — last writer wins for a given name.
_registry: dict[str, ToolSpec] = {}


def register_tool(
    *,
    name: str,
    description: str,
    category: str,
    scope: Scope = "all",
    dangerous: bool = False,
    parameters: dict[str, Any] | None = None,
) -> Callable[[ToolHandler], ToolHandler]:
    """Decorator that registers an async tool handler in the global registry.

    Usage:
        @register_tool(
            name="cron_manage",
            description="Управление запланированными задачами (cron).",
            category="head_protocol",
            scope="head",
            dangerous=False,
        )
        async def cron_manage(params: dict) -> ToolResult:
            ...

    Returns the original function unchanged — callers can still
    `from tools.cron_manage import cron_manage` and call it directly.
    """

    def decorator(func: ToolHandler) -> ToolHandler:
        if name in _registry:
            existing = _registry[name]
            # Allow re-export during reloads (uvicorn --reload re-imports
            # the module → re-runs decorator). Only warn when the actual
            # callable differs — same callable re-registering is a no-op.
            if existing.func is not func:
                import warnings
                warnings.warn(
                    f"register_tool: name={name!r} already registered; "
                    f"overwriting {existing.func!r} with {func!r}",
                    stacklevel=2,
                )
        _registry[name] = ToolSpec(
            name=name,
            description=description,
            category=category,
            scope=scope,
            dangerous=dangerous,
            func=func,
            parameters=parameters,
        )
        return func

    return decorator


def get_tool(name: str) -> ToolSpec | None:
    """Look up a tool by name. Returns None if not registered."""
    return _registry.get(name)


def all_tools() -> dict[str, ToolSpec]:
    """Return the registry dict (key=name, value=ToolSpec). Read-only."""
    return _registry
