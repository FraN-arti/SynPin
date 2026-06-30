"""Model resolution — unified logic for specialized model fallback.

When a specialized model (vision, summarization, etc.) is not configured
in Settings, tools fall back to the calling agent's own model.

Usage in tools:
    provider_name, model_name = resolve_specialized_model(
        setting_key="summarization",
        params=params,  # contains _agent_provider, _agent_model from router
    )
"""
from __future__ import annotations

import logging

from ..paths import get_config_dir

_log = logging.getLogger("synpin.tools")


def resolve_specialized_model(
    setting_key: str,
    params: dict,
) -> tuple[str, str] | None:
    """Resolve a specialized model with fallback to agent's own model.

    Args:
        setting_key: Key in settings.models (e.g. "vision", "summarization")
        params: Tool params dict (contains _agent_provider, _agent_model)

    Returns:
        (provider_name, model_name) or None if nothing available.
    """
    # 1. Try settings.yaml first
    model_str = _read_settings_model(setting_key)
    if model_str:
        parts = model_str.split("/", 1)
        if len(parts) == 2:
            _log.info("[model-resolve] %s: using settings model %s/%s", setting_key, parts[0], parts[1])
            return (parts[0], parts[1])

    # 2. Fallback to agent's own model
    agent_provider = params.get("_agent_provider", "")
    agent_model = params.get("_agent_model", "")
    if agent_provider and agent_model:
        _log.info("[model-resolve] %s: no settings, falling back to agent model %s/%s", setting_key, agent_provider, agent_model)
        return (agent_provider, agent_model)

    # 3. Nothing available
    return None


def _read_settings_model(setting_key: str) -> str | None:
    """Read a model string from settings.yaml → models.{key}."""
    try:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        settings_path = config_dir / "settings.yaml"
        if not settings_path.exists():
            return None
        import yaml
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
        model_str = settings.get("models", {}).get(setting_key, "")
        return model_str if model_str else None
    except Exception as e:
        _log.warning("[model-resolve] Failed to read settings: %s", e)
        return None
