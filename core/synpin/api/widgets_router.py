"""Widgets API — manage widget layout (which widgets are in which panel)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/api/widgets", tags=["widgets"])

# Config path — same dir as other YAML configs
_config_dir: Path | None = None


def _get_config_dir() -> Path:
    global _config_dir
    if _config_dir is None:
        from ..paths import get_config_dir
        _config_dir = get_config_dir()
    return _config_dir


def _yaml_path() -> Path:
    return _get_config_dir() / "widget_layout.yaml"


def _load_layout() -> dict[str, Any]:
    path = _yaml_path()
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"left": ["otdels"], "right": ["kanban"]}


def _save_layout(data: dict[str, Any]) -> None:
    path = _yaml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")
    # Broadcast change
    _broadcast_layout_change()


def _broadcast_layout_change() -> None:
    try:
        import asyncio
        from ..kanban.config import _ws_loop
        from ..chat.ws_manager import ws_manager

        async def _do_broadcast():
            await ws_manager.broadcast({
                "type": "widgets:layout_changed",
                "layout": _load_layout(),
            })

        if _ws_loop is not None:
            asyncio.run_coroutine_threadsafe(_do_broadcast(), _ws_loop)
        else:
            import logging
            logging.getLogger(__name__).warning("Widget layout broadcast: no event loop")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Widget layout broadcast failed: %s", e)


@router.get("/layout")
def get_layout() -> dict[str, Any]:
    """Get current widget layout."""
    return _load_layout()


@router.put("/layout")
def set_layout(req: dict[str, Any]) -> dict[str, Any]:
    """Update widget layout."""
    layout = {
        "left": req.get("left", []),
        "right": req.get("right", []),
    }
    _save_layout(layout)
    return layout
