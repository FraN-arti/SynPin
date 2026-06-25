"""Stats API Router — system statistics and usage data.

Endpoints:
- GET /api/stats/overview  — summary cards (agent count, messages, uptime)
- GET /api/stats/usage     — token usage by model/agent (placeholder)
- GET /api/stats/tools     — tool usage breakdown
- GET /api/stats/sessions  — session list with stats
"""

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])

# ── Path Resolution ──────────────────────────────────────────────────────────

from ..paths import get_config_dir as _get_config_dir, get_data_dir_or_none as _get_data_dir

CONFIG_DIR: Path | None = _get_config_dir()
DATA_DIR: Path | None = _get_data_dir()


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ── Server start time ───────────────────────────────────────────────────────

_SERVER_START = time.time()


def _count_messages_in_session(path: Path) -> int:
    """Count messages in a JSON session file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)  # JSON is valid YAML
            if isinstance(data, list):
                return len(data)
    except Exception:
        pass
    return 0


def _get_all_session_files() -> list[Path]:
    """Find all session JSON files across all agents."""
    if not DATA_DIR:
        return []
    sessions_dir = DATA_DIR / "agents"
    if not sessions_dir.exists():
        return []
    files = []
    for agent_dir in sessions_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        sess_dir = agent_dir / "sessions"
        if sess_dir.exists():
            for f in sess_dir.glob("*.json"):
                files.append(f)
            # Check archive too
            archive_dir = sess_dir / "archive"
            if archive_dir.exists():
                for f in archive_dir.glob("*.json"):
                    files.append(f)
    return files


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/overview")
async def get_overview():
    """System overview — summary cards."""
    # Agent count
    agent_count = 0
    external_count = 0
    if CONFIG_DIR:
        agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
        agent_count = len(agents_cfg.get("agents", {}))
        ext_cfg = _load_yaml(CONFIG_DIR / "external_agents.yaml")
        external_count = len([
            a for a in ext_cfg.get("agents", {}).values()
            if a.get("enabled", True)
        ])

    # Total messages across all sessions
    total_messages = 0
    session_files = _get_all_session_files()
    for sf in session_files:
        total_messages += _count_messages_in_session(sf)

    # Uptime
    uptime_seconds = int(time.time() - _SERVER_START)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    if days > 0:
        uptime_str = f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    else:
        uptime_str = f"{minutes}m"

    # Config files count
    config_count = 0
    if CONFIG_DIR:
        config_count = len(list(CONFIG_DIR.glob("*.yaml")))

    return {
        "agents": agent_count + external_count,
        "agents_internal": agent_count,
        "agents_external": external_count,
        "total_messages": total_messages,
        "total_sessions": len(session_files),
        "config_files": config_count,
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "started_at": datetime.fromtimestamp(_SERVER_START, tz=timezone.utc).isoformat(),
    }


@router.get("/system")
async def get_system():
    """System info: hostname, IP, platform, version, uptime, time."""
    try:
        from ..time import get_system_info
        return get_system_info()
    except Exception as e:
        logger.warning("Failed to get system info: %s", e)
        return {"error": str(e)}


@router.get("/usage")
async def get_usage():
    """Token usage breakdown — by model and agent.

    For now returns session-based stats. Token tracking will be
    added when response logging is implemented.
    """
    # Parse session files to extract model usage
    model_counts: dict[str, int] = {}
    agent_counts: dict[str, int] = {}
    total_user_msgs = 0
    total_assistant_msgs = 0

    session_files = _get_all_session_files()
    for sf in session_files:
        try:
            with open(sf, "r", encoding="utf-8") as f:
                messages = yaml.safe_load(f)
            if not isinstance(messages, list):
                continue
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "")
                if role == "user":
                    total_user_msgs += 1
                elif role == "assistant":
                    total_assistant_msgs += 1
                    model = msg.get("model", "unknown")
                    model_counts[model] = model_counts.get(model, 0) + 1
                    agent = msg.get("agent_name", "")
                    if agent:
                        agent_counts[agent] = agent_counts.get(agent, 0) + 1
        except Exception:
            continue

    return {
        "user_messages": total_user_msgs,
        "assistant_messages": total_assistant_msgs,
        "by_model": [
            {"model": m, "count": c}
            for m, c in sorted(model_counts.items(), key=lambda x: -x[1])
        ],
        "by_agent": [
            {"agent": a, "count": c}
            for a, c in sorted(agent_counts.items(), key=lambda x: -x[1])
        ],
    }


@router.get("/tools")
async def get_tools():
    """Tool usage breakdown — from state files."""
    tool_counts: dict[str, int] = {}

    if not DATA_DIR:
        return {"tools": []}

    agents_dir = DATA_DIR / "agents"
    if not agents_dir.exists():
        return {"tools": []}

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        state_file = agent_dir / "state.json"
        if not state_file.exists():
            continue
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = yaml.safe_load(f)
            if isinstance(state, dict):
                tools_used = state.get("tools_used", {})
                if isinstance(tools_used, dict):
                    for tool_name, count in tools_used.items():
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + (
                            count if isinstance(count, int) else 1
                        )
        except Exception:
            continue

    return {
        "tools": [
            {"tool": t, "count": c}
            for t, c in sorted(tool_counts.items(), key=lambda x: -x[1])
        ]
    }


@router.get("/sessions")
async def get_sessions():
    """List recent sessions with basic stats."""
    sessions = []

    session_files = _get_all_session_files()
    for sf in session_files:
        try:
            with open(sf, "r", encoding="utf-8") as f:
                messages = yaml.safe_load(f)
            if not isinstance(messages, list) or not messages:
                continue

            # Extract agent slug from path: .../agents/{slug}/sessions/{channel}.json
            parts = sf.parts
            agent_slug = "unknown"
            channel = sf.stem
            for i, part in enumerate(parts):
                if part == "agents" and i + 1 < len(parts):
                    agent_slug = parts[i + 1]
                    break

            msg_count = len(messages)
            user_msgs = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
            assistant_msgs = msg_count - user_msgs

            # Get last message time
            last_time = None
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("timestamp"):
                    last_time = msg["timestamp"]
                    break

            sessions.append({
                "agent_slug": agent_slug,
                "channel": channel,
                "messages": msg_count,
                "user_messages": user_msgs,
                "assistant_messages": assistant_msgs,
                "last_activity": last_time,
                "file": sf.name,
            })
        except Exception:
            continue

    # Sort by last activity
    sessions.sort(key=lambda s: s.get("last_activity") or "", reverse=True)

    return {"sessions": sessions[:20]}  # Last 20 sessions
