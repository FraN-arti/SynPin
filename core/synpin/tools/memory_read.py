"""memory_read — read agent's own memory (MEMORY.md or USER.md).

Built-in tool: always enabled, not shown in agent UI.
"""
from pathlib import Path
from typing import Any

from ..paths import get_data_dir as _get_data_dir


async def memory_read(params: dict[str, Any]) -> dict[str, Any]:
    """Read agent memory.

    Params:
        target (str): "memory" for MEMORY.md, "user" for USER.md, "facts" for list of fact files.
        agent_id (str): Agent slug/id.
        filename (str, optional): For facts, specific filename to read.
    """
    target = params.get("target", "memory")
    agent_id = params.get("agent_id", "")
    filename = params.get("filename", "")

    if not agent_id:
        return {"success": False, "output": "", "error": "agent_id is required"}

    data_dir = _get_data_dir()
    agent_dir = data_dir / "agents" / agent_id

    if target == "memory":
        path = agent_dir / "MEMORY.md"
        if not path.exists():
            return {"success": True, "output": "(пусто — нет записей)", "error": None}
        content = path.read_text(encoding="utf-8").strip()
        return {"success": True, "output": content or "(пусто)", "error": None}

    if target == "user":
        # Global USER.md — shared across all agents
        path = data_dir / "shared" / "USER.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            return {"success": True, "output": "(пусто — нет данных о пользователе)", "error": None}
        content = path.read_text(encoding="utf-8").strip()
        return {"success": True, "output": content or "(пусто)", "error": None}

    elif target == "facts":
        facts_dir = agent_dir / "facts"
        if not facts_dir.exists():
            return {"success": True, "output": "(нет фактов)", "error": None}
        files = sorted(facts_dir.glob("*.md"), reverse=True)
        if not files:
            return {"success": True, "output": "(нет фактов)", "error": None}
        if filename:
            # Read specific fact
            fact_path = facts_dir / filename
            if not fact_path.exists():
                return {"success": False, "output": "", "error": f"Fact not found: {filename}"}
            content = fact_path.read_text(encoding="utf-8").strip()
            return {"success": True, "output": content, "error": None}
        else:
            # List all facts
            listing = "\n".join(f.name for f in files[:20])
            return {"success": True, "output": listing, "error": None}

    return {"success": False, "output": "", "error": f"Unknown target: {target}"}
