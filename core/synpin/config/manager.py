"""Config manager for reading/writing YAML configuration files."""
import yaml
import threading
import os
from pathlib import Path
from typing import Any

_CONFIG_DIR = None
_LOCK = threading.Lock()


def _get_config_dir() -> Path:
    """Resolve config directory.
    SYNPIN_DEV=1 → always use dev path (core/synpin/config/)
    Otherwise → ~/.synpin/config/ (prod) with fallback to dev.
    On first prod run, copies templates to user home."""
    global _CONFIG_DIR
    if _CONFIG_DIR is not None:
        return _CONFIG_DIR

    prod = Path.home() / ".synpin" / "config"
    dev = Path(__file__).resolve().parent.parent / "config"

    # Dev mode: always use project directory
    if os.environ.get("SYNPIN_DEV") == "1":
        _CONFIG_DIR = dev
        return _CONFIG_DIR

    if not prod.exists():
        # First run — copy templates to user home
        templates_dir = dev / "templates"
        if templates_dir.exists():
            prod.mkdir(parents=True, exist_ok=True)
            import shutil
            for tpl in templates_dir.glob("*.yaml"):
                shutil.copy2(str(tpl), str(prod / tpl.name))

    if prod.exists():
        _CONFIG_DIR = prod
    else:
        _CONFIG_DIR = dev

    return _CONFIG_DIR


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
