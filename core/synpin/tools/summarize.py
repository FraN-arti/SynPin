"""Summarize tool — summarize text using the configured summarization model.

Reads settings.models.summarization to find the model, then sends the text
for summarization via the appropriate provider.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .base import ToolResult, make_success, make_error

_log = logging.getLogger("synpin.chat")


async def summarize(params: dict) -> ToolResult:
    """Summarize text using the configured summarization model.

    Params:
        text (str): Text to summarize.
        max_length (str, optional): Max summary length. Default: 'short'.
            Options: 'short' (1-2 sentences), 'medium' (paragraph), 'detailed' (full summary).

    Returns:
        ToolResult with the summary.
    """
    text = params.get("text", "")
    max_length = params.get("max_length", "medium")

    if not text:
        return make_error("Missing required parameter: text")

    # Load summarization model config
    model_config = _load_summarization_config()
    if not model_config:
        return make_error(
            "Summarization model not configured. "
            "Set it in Settings → General → Настройка моделей → Суммаризация."
        )

    provider_name, model_name = model_config
    provider_config = _load_provider_config(provider_name)
    if not provider_config:
        return make_error(f"Provider '{provider_name}' not found in config.")

    # Build prompt based on max_length
    length_prompts = {
        "short": "Кратко (1-2 предложения) опиши суть следующего текста.",
        "medium": "Суммаризируй следующий текст в 1-2 абзацах, сохраняя ключевые факты.",
        "detailed": "Подробно.summarизируй следующий текст, сохраняя все важные детали и факты.",
    }
    prompt = length_prompts.get(max_length, length_prompts["medium"])

    try:
        result = await _call_provider(
            provider_config=provider_config,
            model=model_name,
            text=text,
            prompt=prompt,
        )
        return make_success(result)
    except Exception as e:
        _log.error("[summarize] Error: %s", e)
        return make_error(f"Summarization failed: {e}")


def _load_summarization_config() -> tuple[str, str] | None:
    """Load summarization model from settings.yaml. Returns (provider, model) or None."""
    try:
        config_dir = _get_config_dir()
        settings_path = os.path.join(config_dir, "settings.yaml")
        if not os.path.exists(settings_path):
            return None

        import yaml
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

        model_str = settings.get("models", {}).get("summarization", "")
        if not model_str:
            return None

        parts = model_str.split("/", 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
        return None
    except Exception as e:
        _log.warning("[summarize] Failed to load config: %s", e)
        return None


def _get_config_dir() -> str:
    """Find config directory — same logic as config_router.py."""
    candidates = [
        Path.home() / ".synpin" / "config",
        Path(__file__).resolve().parent.parent / "config",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    candidates[0].mkdir(parents=True, exist_ok=True)
    return str(candidates[0])


def _load_provider_config(provider_name: str) -> dict | None:
    """Load provider config from providers.yaml."""
    try:
        config_dir = _get_config_dir()
        providers_path = os.path.join(config_dir, "providers.yaml")
        if not os.path.exists(providers_path):
            return None

        import yaml
        with open(providers_path, "r", encoding="utf-8") as f:
            providers = yaml.safe_load(f) or {}

        providers_dict = providers.get("providers", providers)
        if isinstance(providers_dict, dict):
            return providers_dict.get(provider_name)
        return None
    except Exception as e:
        _log.warning("[summarize] Failed to load provider: %s", e)
        return None


async def _call_provider(provider_config: dict, model: str, text: str, prompt: str) -> str:
    """Call the provider for summarization. Returns text response."""
    import httpx

    base_url = provider_config.get("base_url", "")
    api_key = provider_config.get("api_key", "")

    if not base_url:
        raise ValueError("Provider has no base_url configured")

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
        )
        resp_text = resp.text

        if resp.status_code != 200:
            raise ValueError(f"Provider returned HTTP {resp.status_code}: {resp_text[:200]}")

        if not resp_text.strip():
            raise ValueError("Model returned empty response")

        # Handle SSE prefix
        clean_text = resp_text.strip()
        if clean_text.startswith("data: "):
            clean_text = clean_text[6:].strip()
        if "\n" in clean_text:
            first_line = clean_text.split("\n", 1)[0].strip()
            if first_line.startswith("data: "):
                first_line = first_line[6:].strip()
            clean_text = first_line

        data = json.loads(clean_text)

    choice = data.get("choices", [{}])[0]
    content = choice.get("message", {}).get("content", "")

    if not content:
        raise ValueError("Model returned empty content")

    return content


async def summarize_for_compaction(messages: list[dict]) -> str:
    """Summarize a list of messages into a compact summary for compaction.

    Used by compact_messages when summarization model is configured.
    Returns a summary string.
    """
    # Format messages as conversation
    parts = []
    for m in messages:
        role = m.get("role", "unknown")
        sender = m.get("sender", "")
        content = m.get("content", "")
        if content:
            label = f"[{sender or role}]"
            parts.append(f"{label}: {content}")

    conversation = "\n".join(parts)

    if not conversation.strip():
        return ""

    prompt = (
        "Ты — ассистент для суммаризации истории чата. "
        "Суммаризируй следующий диалог, сохраняя:\n"
        "- Ключевые решения и договорённости\n"
        "- Задачи и их статусы\n"
        "- Важные факты и детали\n"
        "- Имена и роли участников\n\n"
        "Формат: краткий абзац на русском языке."
    )

    # Try to use configured summarization model
    model_config = _load_summarization_config()
    if model_config:
        provider_name, model_name = model_config
        provider_config = _load_provider_config(provider_name)
        if provider_config:
            try:
                return await _call_provider(provider_config, model_name, conversation, prompt)
            except Exception as e:
                _log.warning("[summarize] Failed to use configured model: %s", e)

    # Fallback: simple truncation summary
    return f"[Суммаризация недоступна — настройте модель в Settings → General → Настройка моделей → Суммаризация. Удалено {len(messages)} сообщений]"


__all__ = ["summarize", "summarize_for_compaction"]
