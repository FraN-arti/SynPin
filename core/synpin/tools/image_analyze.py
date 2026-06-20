"""Image analyze tool — analyze images using the configured vision model.

Reads settings.models.vision to find the vision model, then sends the image
via the appropriate provider for analysis.

This is a "fallback" tool — agents use it when their own model can't see images.
"""
from __future__ import annotations

import json
import logging
import os
from urllib.parse import unquote

from .base import ToolResult, make_success, make_error

_log = logging.getLogger("synpin.chat")


async def image_analyze(params: dict) -> ToolResult:
    """Analyze an image using the configured vision model.

    Params:
        image_url (str): Base64 data URL or HTTP URL of the image.
        prompt (str, optional): What to analyze. Default: "Опиши что изображено на картинке."

    Returns:
        ToolResult with the vision model's description.
    """
    image_url = params.get("image_url", "")
    prompt = params.get("prompt", "Опиши что изображено на картинке. Будь подробным.")

    if not image_url:
        return make_error("Missing required parameter: image_url")

    # Resolve model: settings → agent fallback
    from .model_resolve import resolve_specialized_model
    vision_config = resolve_specialized_model("vision", params)
    if not vision_config:
        return make_error(
            "Vision model not configured. "
            "Set it in Settings → General → Настройка моделей → Визион, "
            "or assign a model to the agent."
        )

    provider_name, model_name = vision_config
    _log.info("[image_analyze] provider=%s model=%s", provider_name, model_name)

    # Get provider config
    provider_config = _load_provider_config(provider_name)
    if not provider_config:
        return make_error(f"Provider '{provider_name}' not found in config.")

    # Call the vision provider
    try:
        result = await _call_vision_provider(
            provider_config=provider_config,
            model=model_name,
            image_url=image_url,
            prompt=prompt,
        )
        return make_success(result)
    except Exception as e:
        _log.error("[image_analyze] Error: %s", e)
        return make_error(f"Vision analysis failed: {e}")


def _get_config_dir() -> str:
    """Find config directory — same logic as config_router.py."""
    from pathlib import Path
    candidates = [
        Path.home() / ".synpin" / "config",
        Path(__file__).resolve().parent.parent / "config",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    candidates[0].mkdir(parents=True, exist_ok=True)
    return str(candidates[0])


def _load_vision_config() -> tuple[str, str] | None:
    """Load vision model from settings.yaml. Returns (provider, model) or None."""
    try:
        config_dir = _get_config_dir()
        settings_path = os.path.join(config_dir, "settings.yaml")
        if not os.path.exists(settings_path):
            return None

        import yaml
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

        vision = settings.get("models", {}).get("vision", "")
        if not vision:
            return None

        # Parse "provider/model" format
        parts = vision.split("/", 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
        return None
    except Exception as e:
        _log.warning("[image_analyze] Failed to load vision config: %s", e)
        return None


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

        # providers.yaml format: {providers: {name: {config}, ...}}
        providers_dict = providers.get("providers", providers)
        if isinstance(providers_dict, dict):
            return providers_dict.get(provider_name)
        elif isinstance(providers_dict, list):
            for p in providers_dict:
                if isinstance(p, dict) and p.get("name") == provider_name:
                    return p

        return None
    except Exception as e:
        _log.warning("[image_analyze] Failed to load provider config: %s", e)
        return None


async def _call_vision_provider(
    provider_config: dict,
    model: str,
    image_url: str,
    prompt: str,
) -> str:
    """Call the vision provider with the image and prompt. Returns text response."""
    import httpx

    base_url = provider_config.get("base_url", "")
    api_key = provider_config.get("api_key", "")

    if not base_url:
        raise ValueError(f"Provider has no base_url configured")

    # Build multimodal messages (OpenAI format)
    content_parts = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]

    messages = [
        {"role": "user", "content": content_parts},
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

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
        )
        resp_text = resp.text

        if resp.status_code == 400:
            _log.warning("[image_analyze] 400 from %s/%s: %s", provider_config.get("name", "?"), model, resp_text[:500])
            raise ValueError(
                f"Модель '{model}' не поддерживает изображения (400 Bad Request). "
                f"Настройте другую vision-модель в Settings → General → Настройка моделей → Визион."
            )

        if resp.status_code != 200:
            _log.warning("[image_analyze] HTTP %d from %s/%s: %s", resp.status_code, provider_config.get("name", "?"), model, resp_text[:500])
            raise ValueError(
                f"Vision-провайдер вернул ошибку HTTP {resp.status_code}: {resp_text[:200]}"
            )

        if not resp_text.strip():
            raise ValueError(
                f"Vision-модель '{model}' вернула пустой ответ. "
                f"Модель не поддерживает изображения или сервер не работает."
            )

        # Strip SSE "data: " prefix if present (some providers return SSE even for non-streaming)
        clean_text = resp_text.strip()
        if clean_text.startswith("data: "):
            clean_text = clean_text[6:].strip()
        # Take only the first line if multiple SSE lines
        if "\n" in clean_text:
            first_line = clean_text.split("\n", 1)[0].strip()
            if first_line.startswith("data: "):
                first_line = first_line[6:].strip()
            clean_text = first_line

        try:
            data = json.loads(clean_text)
        except Exception as e:
            _log.warning("[image_analyze] JSON parse error: %s, body=%s", e, resp_text[:300])
            raise ValueError(
                f"Vision-модель вернула некорректный ответ: {resp_text[:200]}"
            )

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content", "")

    if not content:
        raise ValueError("Vision model returned empty response")

    return content


__all__ = ["image_analyze"]
