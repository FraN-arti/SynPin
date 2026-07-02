"""Web search providers — unified interface for multiple search engines.

Each provider implements the same interface:
    async def search(query: str, limit: int) -> list[dict]

Returns list of {title, url, snippet} dicts.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx
import yaml

logger = logging.getLogger("synpin.web_search")

# Load config
_config_cache: dict | None = None


def _load_config() -> dict:
    """Load web_search.yaml config."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    candidates = [
        Path.home() / ".synpin" / "config" / "web_search.yaml",
        Path(__file__).resolve().parent.parent / "config" / "web_search.yaml",
    ]
    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _config_cache = yaml.safe_load(f) or {}
                return _config_cache

    _config_cache = {"providers": {}}
    return _config_cache


def reload_config() -> None:
    """Force reload config (call after settings change)."""
    global _config_cache
    _config_cache = None


def get_enabled_providers() -> list[str]:
    """Return list of enabled provider names."""
    config = _load_config()
    providers = config.get("providers", {})
    return [name for name, cfg in providers.items() if cfg.get("enabled", False)]


def get_provider_config(name: str) -> dict | None:
    """Get config for a specific provider."""
    config = _load_config()
    return config.get("providers", {}).get(name)


# ── Provider implementations ──────────────────────────────────────────────


async def search_ddg(query: str, limit: int = 10) -> list[dict]:
    """DuckDuckGo search — free, no API key."""
    try:
        from .web_search import web_search
        result = await web_search({"query": query, "limit": limit})
        if result.get("success"):
            # Parse the text output into structured results
            return _parse_ddg_text(result.get("output", ""))
        return []
    except Exception as e:
        logger.warning("[search] DDG error: %s", e)
        return []


def _parse_ddg_text(text: str) -> list[dict]:
    """Parse DuckDuckGo text output into structured results."""
    results = []
    lines = text.strip().split("\n")
    current: dict = {}
    for line in lines:
        line = line.strip()
        if line.startswith("Title:"):
            if current:
                results.append(current)
            current = {"title": line[6:].strip()}
        elif line.startswith("URL:"):
            current["url"] = line[4:].strip()
        elif line.startswith("Snippet:"):
            current["snippet"] = line[8:].strip()
    if current and current.get("url"):
        results.append(current)
    return results


async def search_tavily(query: str, limit: int = 10) -> list[dict]:
    """Tavily search — best for AI agents, includes answer."""
    cfg = get_provider_config("tavily")
    if not cfg or not cfg.get("api_key"):
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "query": query,
                "max_results": limit,
                "include_answer": True,
                "search_depth": "basic",
            },
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.warning("[search] Tavily error: %s", resp.status_code)
            return []

        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:200],
            })
        return results


async def search_bing(query: str, limit: int = 10) -> list[dict]:
    """Bing Search — via Azure Cognitive Services."""
    cfg = get_provider_config("bing")
    if not cfg or not cfg.get("api_key"):
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.bing.microsoft.com/v7.0/search",
            params={"q": query, "count": limit, "mkt": "en-us"},
            headers={"Ocp-Apim-Subscription-Key": cfg["api_key"]},
        )
        if resp.status_code != 200:
            logger.warning("[search] Bing error: %s", resp.status_code)
            return []

        data = resp.json()
        results = []
        for item in data.get("webPages", {}).get("value", []):
            results.append({
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
            })
        return results


async def search_serpapi(query: str, limit: int = 10) -> list[dict]:
    """SerpAPI — Google search results."""
    cfg = get_provider_config("serpapi")
    if not cfg or not cfg.get("api_key"):
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={
                "engine": "google",
                "q": query,
                "api_key": cfg["api_key"],
                "num": limit,
            },
        )
        if resp.status_code != 200:
            logger.warning("[search] SerpAPI error: %s", resp.status_code)
            return []

        data = resp.json()
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results


async def search_google(query: str, limit: int = 10) -> list[dict]:
    """Google Custom Search JSON API."""
    cfg = get_provider_config("google")
    if not cfg or not cfg.get("api_key") or not cfg.get("search_engine_id"):
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://customsearch.googleapis.com/customsearch/v1",
            params={
                "key": cfg["api_key"],
                "cx": cfg["search_engine_id"],
                "q": query,
                "num": min(limit, 10),
            },
        )
        if resp.status_code != 200:
            logger.warning("[search] Google CSE error: %s", resp.status_code)
            return []

        data = resp.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results


async def search_perplexity(query: str, limit: int = 10) -> list[dict]:
    """Perplexity — AI-powered search with citations."""
    cfg = get_provider_config("perplexity")
    if not cfg or not cfg.get("api_key"):
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.perplexity.ai/search",
            json={"query": query, "max_results": limit},
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.warning("[search] Perplexity error: %s", resp.status_code)
            return []

        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
            })
        return results


async def search_exa(query: str, limit: int = 10) -> list[dict]:
    """EXA — AI-optimized search with highlights and summaries."""
    cfg = get_provider_config("exa")
    if not cfg or not cfg.get("api_key"):
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.exa.ai/search",
            json={
                "query": query,
                "numResults": limit,
                "contents": {"highlights": True},
            },
            headers={
                "x-api-key": cfg["api_key"],
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.warning("[search] EXA error: %s", resp.status_code)
            return []

        data = resp.json()
        results = []
        for item in data.get("results", []):
            highlights = item.get("highlights", [])
            snippet = highlights[0] if highlights else item.get("text", "")[:200]
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": snippet,
            })
        return results


# ── Provider registry ─────────────────────────────────────────────────────

PROVIDERS = {
    "duckduckgo": search_ddg,
    "tavily": search_tavily,
    "perplexity": search_perplexity,
    "exa": search_exa,
    "bing": search_bing,
    "serpapi": search_serpapi,
    "google": search_google,
}


async def web_search_unified(query: str, provider: str = "", limit: int = 10) -> tuple[list[dict], str]:
    """Unified web search — tries configured provider, falls back to DDG.
    
    Args:
        query: Search query
        provider: Provider name (empty = auto-detect from settings)
        limit: Max results
    
    Returns:
        Tuple of (results_list, provider_name_used)
    """
    used_provider = "duckduckgo"  # default

    # Get preferred provider from settings
    if not provider:
        try:
            from ..config.manager import load_yaml
            settings = load_yaml("settings.yaml")
            provider = settings.get("models", {}).get("web_search", "")
            # Extract provider name from "provider/model" format
            if "/" in provider:
                provider = provider.split("/")[0]
        except Exception:
            provider = ""

    # Try configured provider
    if provider and provider in PROVIDERS:
        cfg = get_provider_config(provider)
        if cfg and cfg.get("enabled") and (provider == "duckduckgo" or cfg.get("api_key")):
            try:
                results = await PROVIDERS[provider](query, limit)
                if results:
                    return results, provider
            except Exception as e:
                logger.warning("[search] Provider %s failed: %s", provider, e)

    # Fallback to DuckDuckGo
    try:
        results = await search_ddg(query, limit)
        return results, "duckduckgo"
    except Exception as e:
        logger.error("[search] All providers failed: %s", e)
        return [], "none"
