"""Tool registry — loads tool definitions from tools.yaml and resolves handlers.

Usage:
    registry = ToolRegistry()
    handler = registry.get("terminal")
    result = await handler({"command": "echo hello"})
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import ToolHandler, ToolResult, make_error

logger = logging.getLogger("synpin.tools.registry")


class ToolRegistry:
    """Registry that maps tool names to their async handler functions.

    Reads tools.yaml to discover which tools are defined, then resolves
    each tool name to its corresponding async handler function.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._tool_defs: dict[str, dict[str, Any]] = {}
        self._config_dir = config_dir
        self._loaded = False

    def _load_config(self) -> dict[str, Any]:
        """Load tools.yaml from the config directory."""
        try:
            from ..config.manager import load_yaml
            return load_yaml("tools.yaml")
        except ImportError:
            # Fallback: direct YAML loading
            import yaml

            if self._config_dir is None:
                self._config_dir = (
                    Path(__file__).resolve().parent.parent.parent / "config"
                )
            tools_path = self._config_dir / "tools.yaml"
            if not tools_path.exists():
                logger.warning("tools.yaml not found at %s", tools_path)
                return {}
            with open(tools_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

    def _import_handler(self, tool_name: str) -> ToolHandler | None:
        """Dynamically import a tool handler by name."""
        # Map tool names to module paths
        _MODULE_MAP: dict[str, str] = {
            "terminal": ".terminal",
            "file_read": ".file_read",
            "file_write": ".file_write",
            "search_files": ".search_files",
            "web_search": ".web_search",
            "code_exec": ".code_exec",
            "memory_read": ".memory_read",
            "memory_write": ".memory_write",
        }

        module_path = _MODULE_MAP.get(tool_name)
        if not module_path:
            return None

        try:
            import importlib
            module = importlib.import_module(module_path, package=__package__)
            handler = getattr(module, tool_name, None)
            if handler is None:
                # Some modules might export under a different name
                # Try to find any async callable
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and attr_name == tool_name:
                        handler = attr
                        break
            return handler
        except Exception as e:
            logger.error("Failed to import tool '%s': %s", tool_name, e)
            return None

    def load(self) -> None:
        """Load tool definitions from tools.yaml and resolve handlers."""
        if self._loaded:
            return

        config = self._load_config()
        self._tool_defs = config.get("tools", {})

        for tool_name in self._tool_defs:
            handler = self._import_handler(tool_name)
            if handler:
                self._handlers[tool_name] = handler
                logger.debug("Loaded tool: %s", tool_name)
            else:
                logger.warning(
                    "Tool '%s' defined in tools.yaml but handler not found.", tool_name
                )

        self._loaded = True
        logger.info(
            "Tool registry loaded: %d tools (%d with handlers)",
            len(self._tool_defs),
            len(self._handlers),
        )

    def get(self, name: str) -> ToolHandler | None:
        """Get a tool handler by name. Returns None if not found."""
        if not self._loaded:
            self.load()
        return self._handlers.get(name)

    async def call(self, name: str, params: dict[str, Any]) -> ToolResult:
        """Call a tool by name with params. Returns error if tool not found."""
        handler = self.get(name)
        if handler is None:
            available = ", ".join(sorted(self._handlers.keys()))
            return make_error(
                f"Tool '{name}' not found. Available tools: {available}"
            )
        try:
            return await handler(params)
        except Exception as e:
            logger.error("Tool '%s' raised exception: %s", name, e, exc_info=True)
            return make_error(f"Tool '{name}' failed with error: {e}")

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tool metadata from tools.yaml."""
        if not self._loaded:
            self.load()
        result = []
        for name, meta in self._tool_defs.items():
            entry = {"name": name}
            entry.update(meta)
            entry["has_handler"] = name in self._handlers
            result.append(entry)
        return result

    def list_handlers(self) -> list[str]:
        """Return names of all tools with registered handlers."""
        if not self._loaded:
            self.load()
        return sorted(self._handlers.keys())

    def register(self, name: str, handler: ToolHandler) -> None:
        """Manually register a tool handler (for runtime registration)."""
        self._handlers[name] = handler
        logger.debug("Manually registered tool: %s", name)
