"""Web search and fetch tools."""

import logging
from typing import Optional

import httpx
from langchain_core.tools import tool
from markdownify import markdownify

logger = logging.getLogger(__name__)

# Module-level config, set by init_web_tools()
_brave_api_key: Optional[str] = None
_fetch_timeout: int = 30


def init_web_tools(config: dict) -> None:
    """Initialize web tools with config values."""
    global _brave_api_key, _fetch_timeout
    web_cfg = config.get("web", {})
    _brave_api_key = web_cfg.get("brave_api_key") or None
    _fetch_timeout = web_cfg.get("fetch_timeout", 30)


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information. Returns a summary of search results."""
    if _brave_api_key:
        return _brave_search(query, max_results)
    return _ddg_search(query, max_results)


def _brave_search(query: str, max_results: int) -> str:
    """Search via Brave Search API."""
    resp = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": max_results},
        headers={"X-Subscription-Token": _brave_api_key},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        results.append(f"**{item['title']}**\n{item['url']}\n{item.get('description', '')}")
    return "\n\n---\n\n".join(results) if results else "No results found."


def _ddg_search(query: str, max_results: int) -> str:
    """Search via DuckDuckGo HTML (no API key needed)."""
    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "CianaParrot/0.1"},
        timeout=15,
    )
    resp.raise_for_status()
    # Parse simple results from DDG HTML
    from html.parser import HTMLParser

    class DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results: list[dict] = []
            self._in_result = False
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
def web_fetch(url: str) -> str:
    """Fetch a URL and return its content as clean markdown."""
    try:
        resp = httpx.get(
            url,
            timeout=_fetch_timeout,
            follow_redirects=True,
            headers={"User-Agent": "CianaParrot/0.1"},
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            md = markdownify(resp.text, strip=["script", "style", "nav", "footer"])
            # Trim to reasonable length
            if len(md) > 15000:
                md = md[:15000] + "\n\n... (truncated)"
            return md
        # Plain text or other
        text = resp.text[:15000]
        return text
    except Exception as e:
        return f"Error fetching {url}: {e}"
