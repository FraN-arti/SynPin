"""Web search tool — unified search via multiple providers.

Supports: DuckDuckGo (default), Tavily, Bing, SerpAPI, Google CSE.
Provider is selected from settings.yaml → models.web_search.
"""
from __future__ import annotations

import re
from html import unescape as html_unescape
from urllib.parse import unquote

from .base import ToolResult, make_success, make_error
from ._registry import register_tool

# Default number of results
_DEFAULT_LIMIT = 10


@register_tool(
    name='web_search',
    description='Поиск информации в интернете. Поддерживает несколько поисковых систем (DuckDuckGo, Tavily, EXA, Perplexity, Bing, SerpAPI, Google). Провайдер выбирается автоматически из настроек.',
    category='web',
    scope='all',
    dangerous=False,
)
async def web_search(params: dict) -> ToolResult:
    """Search the web for information.
    
    Params:
        query (str): The search query.
        limit (int, optional): Maximum number of results. Defaults to 10.
        provider (str, optional): Override provider (duckduckgo, tavily, bing, etc.)
    
    Returns:
        ToolResult with search results as formatted text.
    """
    query = params.get("query")
    if not query:
        return make_error("Missing required parameter: query")
    limit = params.get("limit", _DEFAULT_LIMIT)
    provider_override = params.get("provider", "")

    # Use unified provider system
    try:
        from .web_search_providers import web_search_unified
        results, used_provider = await web_search_unified(query, provider=provider_override, limit=limit)
        if results:
            # Format results as text
            output_lines = [f"[Провайдер: {used_provider}]"]
            for i, r in enumerate(results, 1):
                output_lines.append(f"**{i}. {r.get('title', 'No title')}**")
                output_lines.append(f"URL: {r.get('url', '')}")
                output_lines.append(f"Snippet: {r.get('snippet', '')}")
                output_lines.append("")
            return make_success("\n".join(output_lines))
    except Exception:
        pass  # Fall through to legacy DDG

    # Fallback: legacy DuckDuckGo methods
    results = await _ddg_instant(query, limit)
    if results:
        return make_success(results)

    results = await _ddg_lite(query, limit)
    if results:
        return make_success(results)

    results = await _ddg_html(query, limit)
    if results:
        return make_success(results)

    return make_error(
        "Web search returned no results. "
        "The search APIs may be temporarily unavailable."
    )


async def _ddg_instant(query: str, limit: int) -> str | None:
    """Try DuckDuckGo Instant Answer API."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
            # DDG API returns 202 for successful instant answers
            if resp.status_code not in (200, 202):
                return None

            data = resp.json()

            # Check for a direct answer
            abstract = data.get("AbstractText", "")
            heading = data.get("Heading", "")
            url = data.get("AbstractURL", "")
            source = data.get("AbstractSource", "")

            parts: list[str] = []

            if heading:
                parts.append(f"# {heading}")
            if abstract:
                parts.append(abstract)
            if url:
                parts.append(f"Source: {url}")
            if source and source not in (url or ""):
                parts.append(f"({source})")

            # Collect related topics
            related = data.get("RelatedTopics", [])
            count = 0
            for topic in related:
                if count >= limit:
                    break
                # Skip empty result groups
                if isinstance(topic, dict) and "Text" in topic:
                    text = topic["Text"]
                    topic_url = topic.get("FirstURL", "")
                    if text:
                        entry = f"\n- {text}"
                        if topic_url:
                            entry += f" ({topic_url})"
                        parts.append(entry)
                        count += 1
                elif isinstance(topic, dict) and "Topics" in topic:
                    # Sub-topics
                    for sub in topic["Topics"]:
                        if count >= limit:
                            break
                        if isinstance(sub, dict) and "Text" in sub:
                            text = sub["Text"]
                            topic_url = sub.get("FirstURL", "")
                            if text:
                                entry = f"\n- {text}"
                                if topic_url:
                                    entry += f" ({topic_url})"
                                parts.append(entry)
                                count += 1

            if parts:
                return "\n".join(parts)
            return None

    except Exception:
        return None


async def _ddg_lite(query: str, limit: int) -> str | None:
    """Search via DuckDuckGo lite HTML page and parse results."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
            )
            if resp.status_code != 200:
                return None

            html = resp.text
            return _parse_ddg_html(html, limit)

    except Exception:
        return None


async def _ddg_html(query: str, limit: int) -> str | None:
    """Search via DuckDuckGo HTML and parse results."""
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SynPin/1.0)"},
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            if resp.status_code != 200:
                return None

            html = resp.text
            return _parse_ddg_html(html, limit)

    except Exception:
        return None


def _parse_ddg_html(html: str, limit: int) -> str | None:
    """Parse DuckDuckGo HTML search results.

    Supports multiple DDG HTML formats:
    - html.duckduckgo.com/html/ uses result__a and result__snippet classes
    - lite.duckduckgo.com/lite/ uses different markup
    """
    parts: list[str] = []

    # Strategy 1: Try html.duckduckgo.com format (result__a / result__snippet)
    link_pattern = re.compile(
        r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'class="result__snippet"[^>]*>(.*?)</[at]',
        re.DOTALL,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    if not links:
        # Strategy 2: Try lite.duckduckgo.com format (generic anchors + td content)
        link_pattern = re.compile(
            r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        links = link_pattern.findall(html)
        # Filter to only non-DuckDuckGo links with meaningful text
        filtered = []
        for href, text in links:
            text_clean = re.sub(r"<[^>]+>", "", text).strip()
            # Skip DDG internal links, navigation, and empty text
            if (
                text_clean
                and "duckduckgo.com" not in href
                and not href.startswith("/")
                and len(text_clean) > 3
            ):
                filtered.append((href, text_clean))
        links = filtered

    count = min(len(links), limit)

    for i in range(count):
        if isinstance(links[i], tuple) and len(links[i]) == 2:
            url, title = links[i]
            title = re.sub(r"<[^>]+>", "", title).strip()
            title = html_unescape(title)
        else:
            continue

        # Find matching snippet
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            snippet = html_unescape(snippet)

        if title:
            entry = f"{i + 1}. {title}"
            if snippet:
                entry += f"\n   {snippet}"
            if url:
                # Clean up DDG redirect URLs
                if "uddg=" in url:
                    uddg_match = re.search(r"uddg=([^&]+)", url)
                    if uddg_match:
                        url = unquote(uddg_match.group(1))
                entry += f"\n   URL: {url}"
            parts.append(entry)

    return "\n\n".join(parts) if parts else None
