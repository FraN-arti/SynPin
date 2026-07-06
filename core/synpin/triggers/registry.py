"""
Triggers — registry: pairs .yaml (metadata) with .py (plugin) into a
single runtime definition. Hot-reloadable.

Discovery rule: for each `<type>.yaml` in `definitions/`, look for a
sibling `<type>.py` exposing a subclass of `TriggerPlugin`. Pair them
into a `Definition` namedtuple.
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from .base import TriggerPlugin

logger = logging.getLogger("synpin.triggers.registry")

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


@dataclass
class Definition:
    type: str
    metadata: dict[str, Any]    # parsed YAML
    plugin_cls: type[TriggerPlugin]
    module: ModuleType          # kept so we can reload it on hot-reload


def _load_module(name: str, path: Path) -> ModuleType:
    """Import a Python file as a uniquely-named module."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_one(yaml_path: Path) -> Definition | None:
    """Pair one .yaml with its .py sibling."""
    type_name = yaml_path.stem
    py_path = yaml_path.with_suffix(".py")
    if not py_path.exists():
        logger.warning("trigger registry: %s has no .py sibling, skipping", yaml_path.name)
        return None

    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.error("trigger registry: failed to parse %s: %s", yaml_path, e)
        return None

    if metadata.get("type") != type_name:
        logger.warning(
            "trigger registry: %s has type=%s in YAML, expected %s — skipping",
            yaml_path.name, metadata.get("type"), type_name,
        )
        return None

    module_name = f"synpin.triggers.definitions.{type_name}"
    try:
        module = _load_module(module_name, py_path)
    except Exception as e:  # noqa: BLE001
        logger.error("trigger registry: failed to load %s: %s", py_path, e)
        return None

    # Find a TriggerPlugin subclass in the module.
    plugin_cls: type[TriggerPlugin] | None = None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, TriggerPlugin)
            and attr is not TriggerPlugin
        ):
            plugin_cls = attr
            break
    if plugin_cls is None:
        logger.warning("trigger registry: no TriggerPlugin subclass in %s", py_path)
        return None

    # Validate plugin.type matches file basename.
    if plugin_cls.type != type_name:
        logger.warning(
            "trigger registry: %s declares type=%s, expected %s — using filename",
            py_path, plugin_cls.type, type_name,
        )
        plugin_cls.type = type_name

    return Definition(
        type=type_name,
        metadata=metadata,
        plugin_cls=plugin_cls,
        module=module,
    )


def scan() -> dict[str, Definition]:
    """Scan definitions/ and return a type → Definition map.

    Used at engine startup and on hot-reload. Errors are logged and
    skipped — one bad plugin must not break the rest.
    """
    out: dict[str, Definition] = {}
    if not DEFINITIONS_DIR.exists():
        return out
    for yaml_path in sorted(DEFINITIONS_DIR.glob("*.yaml")):
        defn = _load_one(yaml_path)
        if defn is not None:
            out[defn.type] = defn
    return out


def has_changed(prev: dict[str, Definition], new: dict[str, Definition]) -> bool:
    """True if the registry contents differ in a way that requires reload.

    Adding a new type, removing one, or changing the plugin class
    reference (e.g. after a .py edit) all count as changes.
    """
    if set(prev.keys()) != set(new.keys()):
        return True
    for k, v in new.items():
        if k not in prev:
            return True
        if prev[k].module is not v.module:
            return True
    return False
