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
from pydantic import BaseModel

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

class MemoryConfigUpdate(BaseModel):
    """Partial update for memory.yaml config sections."""
    context_window: Optional[Dict[str, Any]] = None
    compaction: Optional[Dict[str, Any]] = None
    sessions: Optional[Dict[str, Any]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/memory")
async def get_memory_config():
    """Read global memory configuration."""
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
    }


@router.put("/memory")
async def update_memory_config(req: MemoryConfigUpdate):
    """Update global memory configuration (partial deep merge)."""
    path = CONFIG_DIR / "memory.yaml"
    full = _load_yaml(path)

    # Deep merge each section that was provided
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

    _save_yaml(path, full)
    logger.info("memory.yaml updated via API")

    # Return updated config
    return {
        "success": True,
        "context_window": full.get("context_window"),
        "compaction": full.get("compaction"),
        "sessions": full.get("sessions"),
    }
