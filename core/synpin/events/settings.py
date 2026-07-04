"""In-app event settings persistence.

Reads/writes events.yaml in the user config dir. Falls back to
hard-coded defaults when the file is missing (typical fresh install
or dev mode). Settings persist across restarts; events themselves
live in memory only (see EventBus).
"""
from __future__ import annotations

from typing import Any

from ..config.manager import load_yaml, save_yaml

DEFAULT_IN_APP_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "auto_fade_seconds": 8,
    "max_visible": 4,
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "in_app": dict(DEFAULT_IN_APP_SETTINGS),
    "channels": [],  # reserved for future telegram/desktop/email channels
}


def _coerce_in_app(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a user-provided in_app dict on top of defaults, with type coercion.

    Defensive against malformed YAML (missing keys, wrong types) — the
    UI never crashes, just falls back to the default for that key.
    """
    out = dict(DEFAULT_IN_APP_SETTINGS)
    if not isinstance(raw, dict):
        return out
    if "enabled" in raw:
        out["enabled"] = bool(raw["enabled"])
    if "auto_fade_seconds" in raw:
        try:
            v = int(raw["auto_fade_seconds"])
            out["auto_fade_seconds"] = max(1, min(60, v))
        except (TypeError, ValueError):
            pass
    if "max_visible" in raw:
        try:
            v = int(raw["max_visible"])
            out["max_visible"] = max(1, min(20, v))
        except (TypeError, ValueError):
            pass
    return out


def get_in_app_settings() -> dict[str, Any]:
    """Return effective in-app settings.

    Reads events.yaml from config dir if present; merges on top of
    DEFAULT_IN_APP_SETTINGS with type coercion. Always returns a fully
    populated dict.
    """
    data = load_yaml("events.yaml") or {}
    in_app = data.get("in_app")
    return _coerce_in_app(in_app if isinstance(in_app, dict) else None)


def update_in_app_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Apply `updates` to events.yaml and return the new effective settings.

    Only known keys (`enabled`, `auto_fade_seconds`, `max_visible`) are
    accepted; unknown keys are silently dropped to keep the schema
    future-proof.
    """
    allowed = {"enabled", "auto_fade_seconds", "max_visible"}
    clean: dict[str, Any] = {k: v for k, v in (updates or {}).items() if k in allowed}

    data = load_yaml("events.yaml") or {}
    in_app = data.get("in_app")
    if not isinstance(in_app, dict):
        in_app = {}
    in_app.update(clean)
    data["in_app"] = in_app
    data.setdefault("channels", [])
    save_yaml("events.yaml", data)

    return _coerce_in_app(in_app)