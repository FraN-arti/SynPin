"""SynPin tools engine — async tool implementations for AI agents.

Each tool is an async function that accepts a params dict and returns
a ToolResult dict with {"success": bool, "output": str, "error": str|None}.

Usage:
    from synpin.tools import registry

    # Initialize (loads tools.yaml)
    registry.load()

    # Call a tool
    result = await registry.call("terminal", {"command": "echo hello"})

    # Or use a handler directly
    from synpin.tools.terminal import terminal
    result = await terminal({"command": "ls"})
"""
from __future__ import annotations

from .base import ToolResult, ToolHandler, make_success, make_error
from .registry import ToolRegistry

# Create the default registry instance
registry = ToolRegistry()

# Export individual tool handlers for direct use
from .terminal import terminal
from .file_read import file_read
from .file_write import file_write
from .search_files import search_files
from .web_search import web_search
from .code_exec import code_exec
from .memory_read import memory_read
from .memory_write import memory_write
from .head_delegate import head_delegate
from .head_await import head_await
from .head_evaluate import head_evaluate
from .head_retry import head_retry
from .head_decide import head_decide
from .head_block import head_block
from .head_escalate import head_escalate, head_escalation_status
from .kanban_task import kanban_task
from .image_analyze import image_analyze
from .summarize import summarize
from .otdel_manage import otdel_manage
from .project_manage import project_manage

# Registry dict mapping tool names to handler functions (loaded lazily)
_tool_handlers: dict[str, ToolHandler] | None = None


def get_tool_registry() -> dict[str, ToolHandler]:
    """Get a dict mapping tool names to their handler functions.

    This is the "registry dict" that maps tool names to async handlers.
    The registry is loaded lazily on first access.
    """
    global _tool_handlers
    if _tool_handlers is None:
        _tool_handlers = {
            "terminal": terminal,
            "file_read": file_read,
            "file_write": file_write,
            "search_files": search_files,
            "web_search": web_search,
            "code_exec": code_exec,
            "memory_read": memory_read,
            "memory_write": memory_write,
            "head_delegate": head_delegate,
            "head_await": head_await,
            "head_evaluate": head_evaluate,
            "head_retry": head_retry,
            "head_decide": head_decide,
            "head_block": head_block,
            "head_escalate": head_escalate,
            "head_escalation_status": head_escalation_status,
            "kanban_task": kanban_task,
            "image_analyze": image_analyze,
            "summarize": summarize,
            "otdel_manage": otdel_manage,
            "project_manage": project_manage,
        }
    return _tool_handlers


__all__ = [
    # Core
    "registry",
    "get_tool_registry",
    "ToolResult",
    "ToolHandler",
    "make_success",
    "make_error",
    # Tool handlers
    "terminal",
    "file_read",
    "file_write",
    "search_files",
    "web_search",
    "code_exec",
    "memory_read",
    "memory_write",
    "head_delegate",
    "head_await",
    "head_evaluate",
    "head_retry",
    "head_block",
    "head_escalate",
    "head_escalation_status",
    "kanban_task",
    "image_analyze",
    "summarize",
    "otdel_manage",
    "project_manage",
]
