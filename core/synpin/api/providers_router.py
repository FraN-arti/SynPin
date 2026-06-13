"""REST API for managing LLM providers configuration."""
from fastapi import APIRouter, HTTPException
from ._base import BaseRequest
from ..config import manager

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderCreate(BaseRequest):
    name: str
    type: str  # openai | openai-compatible | anthropic
    base_url: str = ""
    api_key: str = ""
    models: list[str] = []
    default: bool = False


class ProviderUpdate(BaseRequest):
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    default: bool | None = None


@router.get("")
async def get_all_providers():
    """Get all configured providers."""
    data = manager.get_providers()
    providers = data.get("providers", {})
    result = []
    for name, cfg in providers.items():
        result.append({
            "name": name,
            "type": cfg.get("type", "openai-compatible"),
            "base_url": cfg.get("base_url", ""),
            "api_key": cfg.get("api_key", ""),
            "models": cfg.get("models", []),
            "default": cfg.get("default", False),
        })
    return {"providers": result}


@router.post("")
async def create_provider(req: ProviderCreate):
    """Add a new provider."""
    if not req.name:
        raise HTTPException(400, "Provider name is required")
    if req.type not in ("openai", "openai-compatible", "anthropic"):
        raise HTTPException(400, "Type must be 'openai', 'openai-compatible', or 'anthropic'")
    config = {"type": req.type}
    if req.base_url:
        config["base_url"] = req.base_url
    if req.api_key:
        config["api_key"] = req.api_key
    if req.models:
        config["models"] = req.models
    if req.default:
        config["default"] = True
    manager.add_provider(req.name, config)
    return {"status": "ok", "name": req.name}


@router.put("/{name}")
async def update_provider(name: str, req: ProviderUpdate):
    """Update an existing provider."""
    existing = manager.get_provider(name)
    if not existing:
        raise HTTPException(404, f"Provider not found: {name}")
    if req.type is not None:
        if req.type not in ("openai", "openai-compatible", "anthropic"):
            raise HTTPException(400, "Invalid type")
        existing["type"] = req.type
    if req.base_url is not None:
        existing["base_url"] = req.base_url
    if req.api_key is not None and req.api_key != "":
        existing["api_key"] = req.api_key
    if req.models is not None:
        existing["models"] = req.models
    if req.default is not None:
        existing["default"] = req.default
    data = manager.get_providers()
    data["providers"][name] = existing
    manager.save_providers(data)
    return {"status": "ok"}


@router.delete("/{name}")
async def delete_provider(name: str):
    """Remove a provider."""
    if not manager.remove_provider(name):
        raise HTTPException(404, f"Provider not found: {name}")
    return {"status": "ok"}


@router.post("/{name}/models/{model_name}")
async def add_model_to_provider(name: str, model_name: str):
    """Add a model to a provider's model list."""
    provider = manager.get_provider(name)
    if not provider:
        raise HTTPException(404, f"Provider not found: {name}")
    models = provider.get("models", [])
    if model_name not in models:
        models.append(model_name)
        provider["models"] = models
        data = manager.get_providers()
        data["providers"][name] = provider
        manager.save_providers(data)
    return {"status": "ok", "models": models}


@router.delete("/{name}/models/{model_name}")
async def remove_model_from_provider(name: str, model_name: str):
    """Remove a model from a provider's model list."""
    provider = manager.get_provider(name)
    if not provider:
        raise HTTPException(404, f"Provider not found: {name}")
    models = [m for m in provider.get("models", []) if m != model_name]
    provider["models"] = models
    data = manager.get_providers()
    data["providers"][name] = provider
    manager.save_providers(data)
    return {"status": "ok", "models": models}


@router.get("/{name}/fetch-models")
async def fetch_models(name: str, base_url: str = "", ptype: str = "openai-compatible", api_key: str = ""):
    """Fetch available models from a provider's API."""
    import httpx
    provider = manager.get_provider(name)
    if provider:
        ptype = provider.get("type", ptype)
        base_url = provider.get("base_url", base_url).rstrip("/")
        api_key = provider.get("api_key", api_key)
    elif not base_url:
        raise HTTPException(400, "base_url is required for non-existing providers.")

    def human_error(status_code: int, text: str) -> str:
        if status_code in (401, 403):
            return "Неверный API ключ или нет доступа"
        if status_code == 404:
            return "Эндпоинт не найден"
        if status_code == 429:
            return "Превышен лимит запросов"
        if text.strip().startswith("<!DOCTYPE") or text.strip().startswith("<html"):
            return "Получена HTML-страница вместо API-ответа"
        return f"HTTP {status_code}"

    is_ollama = "ollama.com" in base_url or "ollama.ai" in base_url
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            if is_ollama:
                resp = await client.get(f"{base_url}/tags", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    all_models = data.get("models", [])
                    model_ids = [m.get("name", "") if isinstance(m, dict) else str(m) for m in all_models]
                    cloud_models = [m for m in model_ids if "cloud" in m.lower()]
                    known_cloud = [m for m in model_ids if any(kw in m.lower() for kw in [
                        "gpt-oss", "kimi", "deepseek-v3", "deepseek-v4", "glm-",
                        "qwen3", "minimax-m", "mistral-large", "gemma", "gemini",
                        "nemotron", "cogito", "devstral", "ministral"
                    ])]
                    result_models = sorted(set(cloud_models + known_cloud))
                    return {"models": result_models[:50], "total": len(result_models)}
                else:
                    return {"status": "error", "message": human_error(resp.status_code, resp.text[:200])}
            else:
                resp = await client.get(f"{base_url}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    model_list = data.get("data", [])
                    model_ids = [m.get("id", m) if isinstance(m, dict) else str(m) for m in model_list]
                    return {"models": model_ids[:100], "total": len(model_ids)}
                else:
                    return {"status": "error", "message": human_error(resp.status_code, resp.text[:200])}
    except httpx.ConnectError:
        return {"status": "error", "message": f"Не удаётся подключиться к {base_url}"}
    except httpx.TimeoutException:
        return {"status": "error", "message": "Превышено время ожидания (15 сек)"}
    except Exception as e:
        return {"status": "error", "message": f"Ошибка: {str(e)}"}


@router.post("/{name}/test")
async def test_provider(name: str):
    """Test provider connectivity by calling their API."""
    import httpx
    provider = manager.get_provider(name)
    if not provider:
        raise HTTPException(404, f"Provider not found: {name}")
    ptype = provider.get("type", "openai-compatible")
    base_url = provider.get("base_url", "").rstrip("/")
    api_key = provider.get("api_key", "")

    def human_error(status_code: int, text: str, url: str) -> str:
        if status_code in (401, 403):
            return "Неверный API ключ или нет доступа"
        if status_code == 404:
            return f"Эндпоинт не найден: {url}/models"
        if status_code == 429:
            return "Превышен лимит запросов (rate limit)"
        if status_code == 500:
            return "Ошибка на стороне провайдера"
        if status_code == 502:
            return "Провайдер недоступен (bad gateway)"
        if status_code == 503:
            return "Провайдер временно недоступен (maintenance)"
        if text.strip().startswith("<!DOCTYPE") or text.strip().startswith("<html"):
            return f"Получена HTML-страница вместо API-ответа (проверьте URL: {url})"
        if status_code == 200 and not text.strip():
            return "Пустой ответ от провайдера"
        return f"HTTP {status_code}: {text[:120]}"

    if ptype in ("openai", "openai-compatible"):
        if not base_url:
            return {"status": "error", "message": "base_url не указан"}
        is_ollama = "ollama.com" in base_url or "ollama.ai" in base_url
        if is_ollama and not api_key:
            return {"status": "error", "message": "Ollama Cloud требует API ключ"}
        test_url = f"{base_url}/tags" if is_ollama else f"{base_url}/models"
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "json" not in content_type and not resp.text.strip().startswith("{"):
                        return {"status": "error", "message": human_error(resp.status_code, resp.text[:200], test_url)}
                    try:
                        data = resp.json()
                    except Exception:
                        return {"status": "error", "message": human_error(resp.status_code, resp.text[:200], test_url)}
                    if is_ollama:
                        model_list = data.get("models", [])
                        model_ids = [m.get("name", m) if isinstance(m, dict) else m for m in model_list[:10]]
                    else:
                        model_list = data.get("data", [])
                        model_ids = [m.get("id", m) if isinstance(m, dict) else m for m in model_list[:10]]
                    return {"status": "ok", "message": f"Connected — {len(model_list)} models available", "models": model_ids}
                else:
                    return {"status": "error", "message": human_error(resp.status_code, resp.text[:200], test_url)}
        except httpx.ConnectError:
            return {"status": "error", "message": f"Не удаётся подключиться к {base_url}"}
        except httpx.TimeoutException:
            return {"status": "error", "message": "Превышено время ожидания (10 сек)"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка: {str(e)}"}
    elif ptype == "anthropic":
        try:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            body = {"model": provider.get("models", ["claude-sonnet-4-20250514"])[0], "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
                if resp.status_code in (200, 400):
                    return {"status": "ok", "message": "Anthropic API reachable"}
                else:
                    return {"status": "error", "message": human_error(resp.status_code, resp.text[:200], "https://api.anthropic.com")}
        except httpx.ConnectError:
            return {"status": "error", "message": "Не удаётся подключиться к Anthropic API"}
        except httpx.TimeoutException:
            return {"status": "error", "message": "Превышено время ожидания (10 сек)"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка: {str(e)}"}
    return {"status": "error", "message": f"Unknown provider type: {ptype}"}
