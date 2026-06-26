"""Config manager for reading/writing YAML configuration files."""
import yaml
import os
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

from ..paths import get_config_dir as _get_config_dir


def _resolve_path(filename: str) -> Path:
    """Get full path for a config file."""
    return _get_config_dir() / filename


def load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML config file."""
    path = _resolve_path(filename)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(filename: str, data: dict[str, Any]) -> None:
    """Save data to a YAML config file atomically."""
    with _LOCK:
        path = _resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to temp file then rename for atomicity
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(str(tmp_path), str(path))


def get_providers() -> dict[str, Any]:
    """Get all providers from providers.yaml."""
    return load_yaml("providers.yaml")


def save_providers(data: dict[str, Any]) -> None:
    """Save providers to providers.yaml."""
    save_yaml("providers.yaml", data)


def get_provider(name: str) -> dict[str, Any] | None:
    """Get a single provider by name."""
    data = get_providers()
    return data.get("providers", {}).get(name)


def add_provider(name: str, config: dict[str, Any]) -> dict[str, Any]:
    """Add or update a provider."""
    data = get_providers()
    if "providers" not in data:
        data["providers"] = {}
    data["providers"][name] = config
    save_providers(data)
    return config


def remove_provider(name: str) -> bool:
    """Remove a provider by name."""
    data = get_providers()
    if "providers" in data and name in data["providers"]:
        del data["providers"][name]
        save_providers(data)
        return True
    return False


class ConfigManager:
    """Manager class wrapping config functions."""
    def get_providers(self):
        return get_providers()
    def save_providers(self, data):
        save_providers(data)
    def get_provider(self, name):
        return get_provider(name)
    def add_provider(self, name, config):
        return add_provider(name, config)
    def remove_provider(self, name):
        return remove_provider(name)


manager = ConfigManager()


# ── Memory Config Defaults ─────────────────────────────────────────────────
#
# Single source of truth for default memory limits. Used by:
#   - api/config_router.py (GET /api/config/memory returns these as fallback)
#   - memory/manager.py (limits when memory.yaml is missing or incomplete)
#
# If you change these, also update config/templates/memory.yaml.

DEFAULT_MEMORY_LIMITS: dict[str, Any] = {
    # MEMORY.md (agent notes) — per-agent curated knowledge
    "memory_max_chars": 2200,
    # USER.md (shared user profile) — kept short on purpose
    "user_max_chars": 1375,
    # Hard ceiling enforced by MemoryStore (regardless of UI value)
    "memory_max_chars_hard_limit": 1_000_000,
    "user_max_chars_hard_limit": 100_000,
}


def get_memory_limits() -> dict[str, Any]:
    """Read effective memory limits from memory.yaml, falling back to defaults.

    Returns a dict with keys:
        memory_max_chars     — limit for MEMORY.md per agent
        user_max_chars       — limit for USER.md (shared profile)
        auto_refactor        — whether to LLM-summarize on overflow
        memory_enabled       — master switch
        provider             — "built-in" | "byterover" | ... (string)

    Falls back to DEFAULT_MEMORY_LIMITS on any error (missing file,
    malformed YAML, missing keys). Callers must always get usable numbers.
    """
    out = dict(DEFAULT_MEMORY_LIMITS)
    try:
        data = load_yaml("memory.yaml")
        mem = data.get("memory", {}) or {}
        prov = data.get("memory_provider", {}) or {}

        out["memory_enabled"] = bool(mem.get("enabled", True))
        out["memory_max_chars"] = int(mem.get("max_chars", DEFAULT_MEMORY_LIMITS["memory_max_chars"]))
        out["user_max_chars"] = int(mem.get("max_chars_user", DEFAULT_MEMORY_LIMITS["user_max_chars"]))
        out["auto_refactor"] = bool(mem.get("auto_refactor", False))

        out["provider"] = str(prov.get("provider", "built-in"))

    except Exception:
        # Stay on defaults — never crash the caller
        pass

    # Clamp to hard limits so a UI typo can't blow memory
    out["memory_max_chars"] = min(
        max(100, out["memory_max_chars"]),
        DEFAULT_MEMORY_LIMITS["memory_max_chars_hard_limit"],
    )
    out["user_max_chars"] = min(
        max(100, out["user_max_chars"]),
        DEFAULT_MEMORY_LIMITS["user_max_chars_hard_limit"],
    )

    return out
