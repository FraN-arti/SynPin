"""Config manager for reading/writing YAML configuration files."""
import yaml
import os
from pathlib import Path
from typing import Any

from ..paths_legacy import _get_config_dir as _get_config_dir  # re-export


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
