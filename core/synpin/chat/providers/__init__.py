"""Provider registry and factory."""
import yaml
from pathlib import Path
from typing import Optional

from .base import BaseProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider


class ProviderRegistry:
    """Registry of configured LLM providers."""
    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}
        self._models: dict[str, list[str]] = {}  # provider_name → [model_names]
        self._default: str | None = None
        self._config_path: Path | None = None  # Stored for hot-reload

    def register(self, name: str, provider: BaseProvider, default: bool = False):
        self._providers[name] = provider
        if default or self._default is None:
            self._default = name

    def get(self, name: str | None = None) -> Optional[BaseProvider]:
        name = name or self._default
        return self._providers.get(name)

    def get_default_model(self, provider_name: str | None = None) -> str | None:
        """Return the first model for a provider, or None."""
        name = provider_name or self._default
        models = self._models.get(name, [])
        return models[0] if models else None

    def list_names(self) -> list[str]:
        return list(self._providers.keys())

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ProviderRegistry":
        """Load providers from YAML config."""
        registry = cls()
        config_path = Path(config_path)

        if not config_path.exists():
            return registry

        registry._config_path = config_path
        registry._load(config_path)
        return registry

    def reload(self) -> None:
        """Hot-reload providers from stored config path.

        Re-reads the YAML and replaces all providers in-place.
        Callers holding a reference to this registry automatically get new providers.
        """
        if not self._config_path or not self._config_path.exists():
            return
        self._load(self._config_path)

    def _load(self, config_path: Path) -> None:
        """Parse YAML and populate providers."""
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        new_providers: dict[str, BaseProvider] = {}
        new_models: dict[str, list[str]] = {}
        new_default: str | None = None

        for name, cfg in config.get("providers", {}).items():
            provider_type = cfg.get("type", "").lower()
            api_key = cfg.get("api_key", "")
            base_url = cfg.get("base_url", "")

            if provider_type in ("openai", "openai-compatible"):
                provider = OpenAIProvider(
                    api_key=api_key,
                    base_url=base_url or "https://api.openai.com/v1",
                )
                # Some providers (Mistral, local LLMs) don't support stream_options
                if cfg.get("supports_stream_options") is False:
                    provider.supports_stream_options = False
            elif provider_type == "anthropic":
                provider = AnthropicProvider(api_key=api_key)
            else:
                continue

            new_providers[name] = provider
            new_models[name] = cfg.get("models", [])
            if cfg.get("default", False) or new_default is None:
                new_default = name

        self._providers = new_providers
        self._models = new_models
        self._default = new_default
