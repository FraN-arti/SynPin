"""Config API Router — global configuration management.

Endpoints:
- GET  /api/config/memory    — read memory config (compaction, sessions, context_window)
- PUT  /api/config/memory    — update memory config (partial update, deep merge)
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from fastapi import APIRouter, HTTPException
from ._base import BaseRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

# ── Config Path Resolution ────────────────────────────────────────────────

_config_candidates = [
    Path.home() / ".synpin" / "config",
    Path(__file__).resolve().parent.parent / "config",
]

CONFIG_DIR: Optional[Path] = None
for candidate in _config_candidates:
    if candidate.exists():
        CONFIG_DIR = candidate
        break

if CONFIG_DIR is None:
    CONFIG_DIR = _config_candidates[0]
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> dict:
    """Load YAML file safely."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to load %s: %s", path, e)
        return {}


def _save_yaml(path: Path, data: dict):
    """Save YAML file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=".config_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base (override wins)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ── Request Model ─────────────────────────────────────────────────────────

class MemoryConfigUpdate(BaseRequest):
    """Partial update for memory.yaml config sections."""
    context_window: Optional[Dict[str, Any]] = None
    compaction: Optional[Dict[str, Any]] = None
    sessions: Optional[Dict[str, Any]] = None
    otdel_compaction: Optional[Dict[str, Any]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/memory")
async def get_memory_config():
    """Read global memory configuration."""
    try:
        path = CONFIG_DIR / "memory.yaml"
        full = _load_yaml(path)

        # Return only the sections we expose for editing
        return {
            "context_window": full.get("context_window", {"default": 128000}),
            "compaction": full.get("compaction", {
                "enabled": True,
                "trigger_percent": 80,
                "keep_recent": 10,
                "strategy": "truncate",
                "summary_max_tokens": 500,
            }),
            "sessions": full.get("sessions", {
                "auto_reset": {"enabled": True, "mode": "daily", "reset_time": "00:00", "interval_hours": 24},
                "archive_on_reset": True,
                "max_history": 100,
            }),
            "otdel_compaction": full.get("otdel_compaction", {
                "enabled": True,
                "compaction_limit": 100,
            }),
        }
    except Exception as e:
        logger.error("Failed to read memory config: %s", e)
        raise HTTPException(500, "Failed to read memory config")


@router.put("/memory")
async def update_memory_config(req: MemoryConfigUpdate):
    """Update global memory configuration (partial deep merge)."""
    try:
        path = CONFIG_DIR / "memory.yaml"
        full = _load_yaml(path)

        if req.context_window is not None:
            full["context_window"] = _deep_merge(
                full.get("context_window", {"default": 128000}),
                req.context_window,
            )

        if req.compaction is not None:
            full["compaction"] = _deep_merge(
                full.get("compaction", {
                    "enabled": True, "trigger_percent": 80,
                    "keep_recent": 10, "strategy": "truncate",
                }),
                req.compaction,
            )

        if req.sessions is not None:
            full["sessions"] = _deep_merge(
                full.get("sessions", {
                    "auto_reset": {"enabled": True, "mode": "daily"},
                    "archive_on_reset": True, "max_history": 100,
                }),
                req.sessions,
            )

        if req.otdel_compaction is not None:
            full["otdel_compaction"] = _deep_merge(
                full.get("otdel_compaction", {
                    "enabled": True, "compaction_limit": 100,
                }),
                req.otdel_compaction,
            )

        _save_yaml(path, full)
        logger.info("memory.yaml updated via API")

        return {
            "success": True,
            "context_window": full.get("context_window"),
            "compaction": full.get("compaction"),
            "sessions": full.get("sessions"),
            "otdel_compaction": full.get("otdel_compaction"),
        }
    except Exception as e:
        logger.error("Failed to update memory config: %s", e)
        raise HTTPException(500, "Failed to update memory config")


# ── Primary Agent ───────────────────────────────────────────────────

class PrimaryAgentUpdate(BaseRequest):
    slug: str


@router.get("/primary-agent")
async def get_primary_agent():
    """Get the primary agent slug."""
    try:
        path = CONFIG_DIR / "settings.yaml"
        full = _load_yaml(path)
        return {"slug": full.get("primary_agent_slug", "")}
    except Exception as e:
        logger.error("Failed to get primary agent: %s", e)
        raise HTTPException(500, "Failed to get primary agent")


@router.put("/primary-agent")
async def set_primary_agent(req: PrimaryAgentUpdate):
    """Set the primary agent slug. Empty string clears it."""
    try:
        path = CONFIG_DIR / "settings.yaml"
        full = _load_yaml(path)
        full["primary_agent_slug"] = req.slug
        _save_yaml(path, full)
        logger.info("Primary agent set to: %s", req.slug or "(none)")
        return {"success": True, "slug": req.slug}
    except Exception as e:
        logger.error("Failed to set primary agent: %s", e)
        raise HTTPException(500, "Failed to set primary agent")


# ── General Settings CRUD ────────────────────────────────────────────────────


class SettingsUpdate(BaseRequest):
    """Partial update for settings.yaml."""
    server: Optional[Dict[str, Any]] = None
    ui: Optional[Dict[str, Any]] = None
    feed: Optional[Dict[str, Any]] = None
    kanban: Optional[Dict[str, Any]] = None


_SETTINGS_DEFAULTS: dict[str, Any] = {
    "primary_agent_slug": "",
    "server": {"host": "0.0.0.0", "port": 2088, "dev_port": 2099},
    "ui": {
        "theme": "dark",
        "language": "ru",
        "border_radius": 8,
        "sidebar": {"default_open": True, "show_icons": True},
        "chat": {
            "show_metadata": True,
            "metadata_delay_ms": 500,
            "max_message_length": 4000,
            "auto_scroll": True,
            "streaming_border": True,
        },
    },
    "models": {
        "vision": "",
        "image_gen": "",
        "web_search": "",
        "web_extract": "",
        "summarization": "",
    },
    "feed": {
        "enabled": True,
        "max_items": 50,
        "time_range": "24h",
        "filters": {
            "new_ideas": True,
            "task_updates": True,
            "memory_updates": True,
            "board_updates": True,
        },
        "sort": "newest",
        "group_by": "none",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into a copy of *base*."""
    out = {**base}
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@router.get("/settings")
async def get_settings():
    """Read full settings.yaml, merged with defaults."""
    try:
        path = CONFIG_DIR / "settings.yaml"
        full = _load_yaml(path)
        return _deep_merge(_SETTINGS_DEFAULTS, full)
    except Exception as e:
        logger.error("Failed to read settings: %s", e)
        raise HTTPException(500, "Failed to read settings")


@router.put("/settings")
async def update_settings(req: SettingsUpdate):
    """Update settings.yaml (partial deep merge)."""
    try:
        path = CONFIG_DIR / "settings.yaml"
        full = _load_yaml(path)

        if req.server is not None:
            full["server"] = _deep_merge(full.get("server", {}), req.server)
        if req.ui is not None:
            full["ui"] = _deep_merge(full.get("ui", {}), req.ui)
        if req.feed is not None:
            full["feed"] = _deep_merge(full.get("feed", {}), req.feed)
        if req.kanban is not None:
            full["kanban"] = _deep_merge(full.get("kanban", {}), req.kanban)

        _save_yaml(path, full)
        logger.info("settings.yaml updated via API")
        return {"success": True, "settings": full}
    except Exception as e:
        logger.error("Failed to update settings: %s", e)
        raise HTTPException(500, "Failed to update settings")
