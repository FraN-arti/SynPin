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
    """Save data to a YAML config file atomically.

    Always uses indent=2 and round-trip-safe defaults so re-reads
    produce exactly the same structure. This avoids the indent
    drift bug where nested dict keys get written with 4-space
    indentation and break subsequent loads.
    """
    import io
    with _LOCK:
        path = _resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Sanity check — don't save if the data shape would round-trip
        # to invalid YAML. Catches bugs early.
        buf = io.StringIO()
        yaml.safe_dump(data, buf, default_flow_style=False,
                       allow_unicode=True, sort_keys=False, indent=2)
        yaml_text = buf.getvalue()
        try:
            yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            raise RuntimeError(
                f"Refusing to save {filename}: round-trip produced invalid YAML: {e}"
            ) from e
        # Write to temp file then rename for atomicity
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(yaml_text)
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
    """Remove a provider from providers.yaml."""
    data = get_providers()
    if "providers" in data and name in data["providers"]:
        del data["providers"][name]
        save_providers(data)
        return True
    return False


# ── Tools — global enable/disable list (settings.yaml:tools.disabled) ──────────
#
# Single source of truth for which tools are turned OFF. Read on every LLM call
# (via get_all_tool_names() in chat/router.py) so changes take effect immediately
# without server restart. Format in settings.yaml:
#
#   tools:
#     disabled: ["terminal", "code_exec"]
#
# Empty/missing list = everything enabled (default).

def get_disabled_tools() -> list[str]:
    """Return globally disabled tool names from settings.yaml.

    Always returns a fresh read — settings can change at runtime via the
    UI (api/tools_router.py) and we want to honor that immediately.
    """
    try:
        data = load_yaml("settings.yaml")
        tools_cfg = (data or {}).get("tools", {}) or {}
        disabled = tools_cfg.get("disabled", [])
        # Normalize to list[str], drop empty/None
        return [str(t) for t in disabled if t]
    except Exception:
        return []


def set_disabled_tool(name: str, disabled: bool) -> bool:
    """Add or remove `name` from the disabled list. Returns True on change.

    Persists to settings.yaml. UI calls this when toggling a tool.
    """
    try:
        data = load_yaml("settings.yaml") or {}
    except Exception:
        data = {}
    if "tools" not in data or not isinstance(data.get("tools"), dict):
        data["tools"] = {}
    current = set(str(t) for t in data["tools"].get("disabled", []) if t)
    if disabled:
        if name in current:
            return False
        current.add(name)
    else:
        if name not in current:
            return False
        current.discard(name)
    data["tools"]["disabled"] = sorted(current)
    save_yaml("settings.yaml", data)
    return True


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
