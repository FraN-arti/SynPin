"""Base definitions for SynPin tools engine.

Every tool handler must be an async function that accepts a params dict
and returns a ToolResult dict.
"""
from __future__ import annotations

from typing import Any, Callable, Awaitable

# Standard result returned by every tool handler.
ToolResult = dict[str, Any]
"""
Expected shape:
{
    "success": bool,
    "output": str,
    "error": str | None,    # only present when success is False
}
"""


# Type alias for an async tool handler function.
# Signature: async def handler(params: dict[str, Any]) -> ToolResult
ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]


def make_success(output: str) -> ToolResult:
    """Create a successful result."""
    return {"success": True, "output": output}


def make_error(error: str) -> ToolResult:
    """Create an error result."""
    return {"success": False, "output": "", "error": error}
