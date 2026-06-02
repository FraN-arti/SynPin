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
        self._default: str | None = None

    def register(self, name: str, provider: BaseProvider, default: bool = False):
        self._providers[name] = provider
        if default or self._default is None:
            self._default = name

    def get(self, name: str | None = None) -> Optional[BaseProvider]:
        name = name or self._default
        return self._providers.get(name)

    def list_names(self) -> list[str]:
        return list(self._providers.keys())

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ProviderRegistry":
        """Load providers from YAML config."""
        registry = cls()

        config_path = Path(config_path)
        if not config_path.exists():
            return registry

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        for name, cfg in config.get("providers", {}).items():
            provider_type = cfg.get("type", "").lower()
            api_key = cfg.get("api_key", "")
            base_url = cfg.get("base_url", "")

            if provider_type == "openai" or provider_type == "openai-compatible":
                provider = OpenAIProvider(
                    api_key=api_key,
                    base_url=base_url or "https://api.openai.com/v1",
                )
            elif provider_type == "anthropic":
                provider = AnthropicProvider(api_key=api_key)
            else:
                continue

            is_default = cfg.get("default", False)
            registry.register(name, provider, default=is_default)

        return registry
