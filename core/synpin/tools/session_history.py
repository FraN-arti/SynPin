"""session_history — read archived session conversations.

Allows agents to look up what was discussed in previous sessions.
This is how agents remember past conversations after session reset.
"""
import json
from pathlib import Path
from typing import Any
from ._registry import register_tool

from ..paths import get_data_dir as _get_data_dir



@register_tool(
    name='session_history',
    description='Поиск в архивах прошлых сессий. Используй когда пользователь ссылается на старые разговоры.',
    category='memory',
    scope='builtin',
    dangerous=False,
)
async def session_history(params: dict[str, Any]) -> dict[str, Any]:
    """Read archived session history.

    Params:
        agent_id (str): Agent slug/id.
        channel (str, optional): Channel to search in (default: all channels).
            Common values: "web", "cron", otdel_id.
        action (str): "list" to list archives, "read" to read one, "search" to search content.
        filename (str, optional): For "read" action — specific archive filename.
        query (str, optional): For "search" action — text to search for in archives.
        limit (int, optional): Max archives to return (default: 10).
    """
    agent_id = params.get("agent_id", "")
    channel = params.get("channel", "")
    action = params.get("action", "list")
    filename = params.get("filename", "")
    query = params.get("query", "")
    limit = params.get("limit", 10)

    if not agent_id:
        return {"success": False, "output": "", "error": "agent_id is required"}

    data_dir = _get_data_dir()
    archive_dir = data_dir / "agents" / agent_id / "sessions" / "archive"

    if not archive_dir.exists():
        return {"success": True, "output": "(нет архивов сессий)", "error": None}

    if action == "list":
        return _list_archives(archive_dir, channel, limit)
    elif action == "read":
        return _read_archive(archive_dir, filename)
    elif action == "search":
        return _search_archives(archive_dir, channel, query, limit)
    else:
        return {"success": False, "output": "", "error": f"Unknown action: {action}"}


def _list_archives(archive_dir: Path, channel: str, limit: int) -> dict:
    """List archive files, optionally filtered by channel."""
    archives = sorted(archive_dir.glob("*.json"), reverse=True)

    if channel:
        archives = [a for a in archives if a.stem.startswith(channel)]

    if not archives:
        return {"success": True, "output": "(нет архивов сессий)", "error": None}

    result_lines = []
    for f in archives[:limit]:
        size_kb = f.stat().st_size / 1024
        # Extract timestamp from filename: channel_YYYYMMDD_HHMMSS.json
        parts = f.stem.split("_")
        if len(parts) >= 3:
            date_str = f"{parts[-2][:4]}-{parts[-2][4:6]}-{parts[-2][6:]} {parts[-1][:2]}:{parts[-1][2:4]}"
        else:
            date_str = "unknown date"

        # Try to get message count and first user message
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            msgs = data.get("messages", []) if isinstance(data, dict) else data
            msg_count = len(msgs) if isinstance(msgs, list) else 0
            first_user = ""
            for m in (msgs if isinstance(msgs, list) else []):
                if isinstance(m, dict) and m.get("role") == "user":
                    first_user = m.get("content", "")[:80]
                    break
        except Exception:
            msg_count = 0
            first_user = ""

        line = f"{f.name} — {date_str}, {size_kb:.1f}KB, {msg_count} msgs"
        if first_user:
            line += f'\n  "{first_user}"'
        result_lines.append(line)

    return {"success": True, "output": "\n".join(result_lines), "error": None}


def _read_archive(archive_dir: Path, filename: str) -> dict:
    """Read a specific archive file."""
    if not filename:
        return {"success": False, "output": "", "error": "filename is required for 'read' action"}

    path = archive_dir / filename
    if not path.exists():
        return {"success": False, "output": "", "error": f"Archive not found: {filename}"}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        # New format: {"channel_id": ..., "messages": [...], "archived_at": ...}
        if isinstance(data, dict) and "messages" in data:
            messages = data["messages"]
            archived_at = data.get("archived_at", "")
            channel = data.get("channel_id", "")
        elif isinstance(data, list):
            messages = data
            archived_at = ""
            channel = ""
        else:
            return {"success": False, "output": "", "error": "Unknown archive format"}

        # Format output
        lines = []
        if channel:
            lines.append(f"Channel: {channel}")
        if archived_at:
            lines.append(f"Archived: {archived_at}")
        lines.append(f"Messages: {len(messages)}")
        lines.append("---")

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            if content:
                ts = f" [{timestamp[:19]}]" if timestamp else ""
                lines.append(f"[{role}]{ts} {content[:500]}")

        output = "\n".join(lines)
        # Truncate if too large for agent context
        if len(output) > 8000:
            output = output[:8000] + "\n... (truncated)"

        return {"success": True, "output": output, "error": None}

    except Exception as e:
        return {"success": False, "output": "", "error": f"Failed to read archive: {e}"}


def _search_archives(archive_dir: Path, channel: str, query: str, limit: int) -> dict:
    """Search for text across archived sessions."""
    if not query:
        return {"success": False, "output": "", "error": "query is required for 'search' action"}

    archives = sorted(archive_dir.glob("*.json"), reverse=True)
    if channel:
        archives = [a for a in archives if a.stem.startswith(channel)]

    query_lower = query.lower()
    matches = []

    for archive_file in archives:
        if len(matches) >= limit:
            break
        try:
            data = json.loads(archive_file.read_text(encoding="utf-8"))
            messages = data.get("messages", []) if isinstance(data, dict) else data

            for msg in (messages if isinstance(messages, list) else []):
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", "")
                if query_lower in content.lower():
                    role = msg.get("role", "?")
                    ts = msg.get("timestamp", "")[:19]
                    # Show context around the match
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 100)
                    end = min(len(content), idx + len(query) + 100)
                    snippet = content[start:end]
                    matches.append(
                        f"[{archive_file.name}] [{ts}] {role}: ...{snippet}..."
                    )
                    if len(matches) >= limit:
                        break
        except Exception:
            continue

    if not matches:
        return {"success": True, "output": f"Ничего не найдено по запросу '{query}'", "error": None}

    return {"success": True, "output": "\n\n".join(matches), "error": None}
