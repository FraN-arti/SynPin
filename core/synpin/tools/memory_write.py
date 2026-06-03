"""memory_write — write to agent's own memory (MEMORY.md or USER.md).

Built-in tool: always enabled, not shown in agent UI.
"""
import os
import tempfile
from pathlib import Path
from typing import Any

# Character limits
MEMORY_CHAR_LIMIT = 2200
USER_CHAR_LIMIT = 1375

_DATA_DIR: Path | None = None


def _get_data_dir() -> Path:
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR
    candidates = [
        Path.home() / ".synpin" / "data",
        Path(__file__).resolve().parent.parent.parent.parent / "data",
    ]
    for c in candidates:
        if c.exists():
            _DATA_DIR = c
            return _DATA_DIR
    _DATA_DIR = candidates[0]
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


def _read_entries(path: Path) -> list[str]:
    """Read MEMORY.md/USER.md into a list of entries (separated by §)."""
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [e.strip() for e in content.split("\n§\n") if e.strip()]


def _write_entries(path: Path, entries: list[str]) -> None:
    """Write entries list back to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n§\n".join(entries) + "\n" if entries else ""
    # Atomic write: temp file + rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=".memory_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


async def memory_write(params: dict[str, Any]) -> dict[str, Any]:
    """Write to agent memory.

    Params:
        action (str): "add", "remove", "replace".
        target (str): "memory" for MEMORY.md, "user" for USER.md.
        agent_id (str): Agent slug/id.
        content (str): New entry text (for add/replace).
        old_text (str): Text to find and replace/remove.
    """
    action = params.get("action", "add")
    target = params.get("target", "memory")
    agent_id = params.get("agent_id", "")
    content = params.get("content", "")
    old_text = params.get("old_text", "")

    if not agent_id:
        return {"success": False, "output": "", "error": "agent_id is required"}

    data_dir = _get_data_dir()
    agent_dir = data_dir / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    if target == "memory":
        path = agent_dir / "MEMORY.md"
    elif target == "user":
        # Global USER.md — shared across all agents
        path = data_dir / "shared" / "USER.md"
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        return {"success": False, "output": "", "error": f"Unknown target: {target}"}

    entries = _read_entries(path)

    if action == "add":
        if not content.strip():
            return {"success": False, "output": "", "error": "content is required for add"}
        entries.append(content.strip())
        _write_entries(path, entries)
        # Check char limit
        written = path.read_text(encoding="utf-8")
        limit = USER_CHAR_LIMIT if target == "user" else MEMORY_CHAR_LIMIT
        if len(written) > limit:
            return {"success": True, "output": f"Added. Total entries: {len(entries)}", "warning": f"Memory ({len(written):,} chars) exceeds limit ({limit:,} chars).", "error": None}
        return {"success": True, "output": f"Added. Total entries: {len(entries)}", "error": None}

    elif action == "remove":
        if not old_text.strip():
            return {"success": False, "output": "", "error": "old_text is required for remove"}
        new_entries = [e for e in entries if old_text.strip() not in e]
        if len(new_entries) == len(entries):
            return {"success": False, "output": f"Not found: {old_text[:50]}", "error": None}
        _write_entries(path, new_entries)
        return {"success": True, "output": f"Removed. Total entries: {len(new_entries)}", "error": None}

    elif action == "replace":
        if not old_text.strip():
            return {"success": False, "output": "", "error": "old_text is required for replace"}
        if not content.strip():
            return {"success": False, "output": "", "error": "content is required for replace"}
        found = False
        new_entries = []
        for e in entries:
            if old_text.strip() in e and not found:
                new_entries.append(content.strip())
                found = True
            else:
                new_entries.append(e)
        if not found:
            return {"success": False, "output": f"Not found: {old_text[:50]}", "error": None}
        _write_entries(path, new_entries)
        return {"success": True, "output": f"Replaced. Total entries: {len(new_entries)}", "error": None}

    return {"success": False, "output": "", "error": f"Unknown action: {action}"}
