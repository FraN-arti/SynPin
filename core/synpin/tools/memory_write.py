"""memory_write — write to agent's own memory (MEMORY.md or USER.md).

Built-in tool: always enabled, not shown in agent UI.

Thin wrapper around MemoryManager (synpin.memory). All persistence, locking,
char-limit checks, auto-compaction, and search re-indexing live in one place
(memory/store.py + memory/manager.py). This module just translates the
tool-call schema into MemoryManager method calls.
"""
import logging
from typing import Any
from ._registry import register_tool

from ..memory import get_manager

logger = logging.getLogger("synpin.memory")



@register_tool(
    name='memory_write',
    description='Запись в память агента. Используй чтобы запомнить важную информацию на будущее.',
    category='memory',
    scope='builtin',
    dangerous=False,
)
async def memory_write(params: dict[str, Any]) -> dict[str, Any]:
    """Write to agent memory.

    Params:
        action (str): "add", "remove", "replace", "fact".
        target (str): "memory" for MEMORY.md, "user" for USER.md.
            Not used for action='fact'.
        agent_id (str): Agent slug/id. Injected by execute_tool().
        content (str): New entry text (for add/replace/fact).
        old_text (str): Text to find and replace/remove.
        topic (str): Topic for action='fact'. Used in the filename.

    Returns:
        ToolResult dict: {"success": bool, "output": str, "error": str|None}.
    """
    action = params.get("action", "add")
    target = params.get("target", "memory")
    agent_id = params.get("agent_id", "")
    content = params.get("content", "")
    old_text = params.get("old_text", "")
    topic = params.get("topic", "")

    if not agent_id:
        return {"success": False, "output": "", "error": "agent_id is required"}

    try:
        manager = get_manager(agent_id)
    except Exception as e:
        logger.error("Failed to get MemoryManager for %s: %s", agent_id, e)
        return {"success": False, "output": "", "error": f"memory subsystem unavailable: {e}"}

    if action == "add":
        if target not in ("memory", "user"):
            return {"success": False, "output": "", "error": f"Unknown target: {target}"}
        result = manager.add(target, content)
        return _format_result(result)

    elif action == "remove":
        if target not in ("memory", "user"):
            return {"success": False, "output": "", "error": f"Unknown target: {target}"}
        result = manager.remove(target, old_text)
        return _format_result(result)

    elif action == "replace":
        if target not in ("memory", "user"):
            return {"success": False, "output": "", "error": f"Unknown target: {target}"}
        result = manager.replace(target, old_text, content)
        return _format_result(result)

    elif action == "fact":
        if not topic.strip():
            return {"success": False, "output": "", "error": "topic is required for fact"}
        if not content.strip():
            return {"success": False, "output": "", "error": "content is required for fact"}
        result = manager.add_fact(topic, content)
        if result.get("success"):
            return {
                "success": True,
                "output": f"Fact saved: {result.get('filename', '?')} — {content[:80]}",
                "error": None,
            }
        return {
            "success": False,
            "output": "",
            "error": result.get("error", "Failed to save fact"),
        }

    return {"success": False, "output": "", "error": f"Unknown action: {action}"}


def _format_result(result: dict) -> dict:
    """Convert MemoryManager result → ToolResult shape.

    MemoryManager returns {"success", "target", "entries", "usage", "entry_count", "message"}.
    Tools expect {"success", "output", "error"}.
    """
    if not result.get("success"):
        return {
            "success": False,
            "output": "",
            "error": result.get("error", "unknown error"),
            # Echo back useful context when over-limit / multiple-match errors fire
            "current_entries": result.get("current_entries"),
            "matches": result.get("matches"),
            "usage": result.get("usage"),
        }
    msg = result.get("message", "Done.")
    usage = result.get("usage", "")
    output = f"{msg} [{usage}]" if usage else msg
    out = {
        "success": True,
        "output": output,
        "warning": None,
        "error": None,
    }
    # Pass-through for MemoryManager-side flags the caller may want to inspect
    if result.get("refactored"):
        out["refactored"] = True
        out["output"] = f"{output} (refactored)"
    return out