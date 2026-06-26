"""memory_read — read agent's own memory (MEMORY.md / USER.md / facts/).

Built-in tool: always enabled, not shown in agent UI.

Thin wrapper around MemoryManager (synpin.memory). Live entries are returned
(the same state tools/memory_write mutates), so an agent that just wrote
something will see it on the next read without waiting for any TTL.
"""
from typing import Any

from ..memory import get_manager


async def memory_read(params: dict[str, Any]) -> dict[str, Any]:
    """Read agent memory.

    Params:
        target (str): "memory" for MEMORY.md, "user" for USER.md,
            "facts" for the list of dated fact files.
        agent_id (str): Agent slug/id. Injected by execute_tool().
        filename (str, optional): For target='facts', specific filename to read.
        limit (int, optional): For target='facts', max files to list. Default 20.

    Returns:
        ToolResult dict: {"success": bool, "output": str, "error": str|None}.
    """
    target = params.get("target", "memory")
    agent_id = params.get("agent_id", "")
    filename = params.get("filename", "")
    limit = int(params.get("limit", 20))

    if not agent_id:
        return {"success": False, "output": "", "error": "agent_id is required"}

    try:
        manager = get_manager(agent_id)
    except Exception as e:
        return {"success": False, "output": "", "error": f"memory subsystem unavailable: {e}"}

    if target in ("memory", "user"):
        result = manager.read(target)
        if not result.get("success"):
            return {"success": False, "output": "", "error": result.get("error", "read failed")}
        entries = result.get("entries", [])
        usage = result.get("usage", "")
        if not entries:
            return {"success": True, "output": f"(empty — {usage})", "error": None}
        body = "\n§\n".join(entries)
        return {"success": True, "output": f"{body}\n\n[{usage}]", "error": None}

    if target == "facts":
        if filename:
            result = manager.read_fact(filename)
            if not result.get("success"):
                return {"success": False, "output": "", "error": result.get("error", "fact not found")}
            return {
                "success": True,
                "output": f"{result.get('content', '')}\n\n[{result.get('size', 0)} bytes]",
                "error": None,
            }
        result = manager.list_facts(limit)
        if not result.get("success"):
            return {"success": False, "output": "", "error": result.get("error", "list failed")}
        facts = result.get("facts", [])
        if not facts:
            return {"success": True, "output": "(no facts)", "error": None}
        # Compact listing: filename + date + size
        lines = []
        for f in facts:
            name = f.get("filename", "?")
            size = f.get("size", 0)
            lines.append(f"- {name} ({size} B)")
        return {
            "success": True,
            "output": f"{len(facts)} fact file(s):\n" + "\n".join(lines),
            "error": None,
        }

    return {"success": False, "output": "", "error": f"Unknown target: {target}"}