"""Web search and fetch tools."""

import logging
from typing import Optional

import httpx
from langchain_core.tools import tool
from markdownify import markdownify

from ..config import WebConfig

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 15_000

# Module-level config, set by init_web_tools()
_brave_api_key: Optional[str] = None
_fetch_timeout: int = 30


def init_web_tools(config: WebConfig) -> None:
    """Initialize web tools with config values."""
    global _brave_api_key, _fetch_timeout
    _brave_api_key = config.brave_api_key
    _fetch_timeout = config.fetch_timeout


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information. Returns a summary of search results."""
    if _brave_api_key:
        return await _brave_search(query, max_results)
    return await _ddg_search(query, max_results)


async def _brave_search(query: str, max_results: int) -> str:
    """Search via Brave Search API."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": _brave_api_key},
        )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        results.append(f"**{item['title']}**\n{item['url']}\n{item.get('description', '')}")
    return "\n\n---\n\n".join(results) if results else "No results found."


async def _ddg_search(query: str, max_results: int) -> str:
    """Search via DuckDuckGo HTML (no API key needed)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "CianaParrot/0.1"},
        )
    resp.raise_for_status()
    # Parse simple results from DDG HTML
    from html.parser import HTMLParser

    class DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results: list[dict] = []
            self._in_title = False
            self._in_snippet = False
            self._current: dict = {}

        def handle_starttag(self, tag, attrs):
            attrs_d = dict(attrs)
            cls = attrs_d.get("class", "")
            if tag == "a" and "result__a" in cls:
                self._in_title = True
                self._current = {"title": "", "url": attrs_d.get("href", ""), "snippet": ""}
            elif tag == "a" and "result__snippet" in cls:
                self._in_snippet = True

        def handle_endtag(self, tag):
            if tag == "a" and self._in_title:
                self._in_title = False
            elif tag == "a" and self._in_snippet:
                self._in_snippet = False
                if self._current:
                    self.results.append(self._current)
                    self._current = {}

        def handle_data(self, data):
            if self._in_title and self._current:
                self._current["title"] += data
            elif self._in_snippet and self._current:
                self._current["snippet"] += data

    parser = DDGParser()
    parser.feed(resp.text)
    results = parser.results[:max_results]
    if not results:
        return "No results found."
    return "\n\n---\n\n".join(
        f"**{r['title']}**\n{r['url']}\n{r['snippet']}" for r in results
    )


@tool
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its content as clean markdown."""
    try:
        async with httpx.AsyncClient(timeout=_fetch_timeout) as client:
            resp = await client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": "CianaParrot/0.1"},
            )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            md = markdownify(resp.text, strip=["script", "style", "nav", "footer"])
            # Trim to reasonable length
            if len(md) > MAX_CONTENT_LENGTH:
                md = md[:MAX_CONTENT_LENGTH] + "\n\n... (truncated)"
            return md
        # Plain text or other
        text = resp.text[:MAX_CONTENT_LENGTH]
        return text
    except Exception as e:
        return f"Error fetching {url}: {e}"
