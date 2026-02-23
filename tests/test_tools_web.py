"""Tests for src.tools.web — init_web_tools, web_search, _brave_search, _ddg_search, web_fetch."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import WebConfig
from src.tools.web import init_web_tools, web_search, web_fetch, _brave_search, _ddg_search
from src.tools import web as web_module


class TestInitWebTools:
    def test_sets_brave_api_key(self):
        config = WebConfig(brave_api_key="test-key", fetch_timeout=15)
        init_web_tools(config)
        assert web_module._brave_api_key == "test-key"
        assert web_module._fetch_timeout == 15

    def test_none_api_key(self):
        config = WebConfig(brave_api_key=None, fetch_timeout=30)
        init_web_tools(config)
        assert web_module._brave_api_key is None
        assert web_module._fetch_timeout == 30

    def test_empty_api_key_becomes_none(self):
        config = WebConfig(brave_api_key="")
        init_web_tools(config)
        assert web_module._brave_api_key is None

    def test_custom_timeout(self):
        config = WebConfig(fetch_timeout=60)
        init_web_tools(config)
        assert web_module._fetch_timeout == 60

    def test_default_config(self):
        config = WebConfig()
        init_web_tools(config)
        assert web_module._brave_api_key is None
        assert web_module._fetch_timeout == 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_httpx_client_mock(mock_response):
    """Build a patched httpx.AsyncClient that yields *mock_response* from `async with`."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_client


# ---------------------------------------------------------------------------
# TestWebSearch — dispatcher logic
# ---------------------------------------------------------------------------

class TestWebSearch:
    @pytest.mark.asyncio
    @patch("src.tools.web._brave_search", new_callable=AsyncMock)
    async def test_dispatches_to_brave_when_key_set(self, mock_brave):
        web_module._brave_api_key = "test"
        mock_brave.return_value = "brave result"
        result = await web_search.ainvoke({"query": "test"})
        mock_brave.assert_called_once()
        assert result == "brave result"

    @pytest.mark.asyncio
    @patch("src.tools.web._ddg_search", new_callable=AsyncMock)
    async def test_dispatches_to_ddg_when_no_key(self, mock_ddg):
        web_module._brave_api_key = None
        mock_ddg.return_value = "ddg result"
        result = await web_search.ainvoke({"query": "test"})
        mock_ddg.assert_called_once()
        assert result == "ddg result"

    @pytest.mark.asyncio
    @patch("src.tools.web._ddg_search", new_callable=AsyncMock)
    async def test_passes_query_to_backend(self, mock_ddg):
        web_module._brave_api_key = None
        mock_ddg.return_value = "ok"
        await web_search.ainvoke({"query": "my question"})
        args, _kwargs = mock_ddg.call_args
        assert args[0] == "my question"


# ---------------------------------------------------------------------------
# TestBraveSearch
# ---------------------------------------------------------------------------

class TestBraveSearch:
    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_success_formatted_results(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "T1", "url": "http://u1", "description": "D1"},
                    {"title": "T2", "url": "http://u2", "description": "D2"},
                ]
            }
        }

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        web_module._brave_api_key = "key123"
        result = await _brave_search("test query", 5)
        assert "T1" in result
        assert "http://u1" in result
        assert "T2" in result

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_empty_results(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        web_module._brave_api_key = "key123"
        result = await _brave_search("nothing", 5)
        assert result == "No results found."

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_http_error(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden",
            request=MagicMock(),
            response=MagicMock(status_code=403),
        )

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        web_module._brave_api_key = "key123"
        with pytest.raises(httpx.HTTPStatusError):
            await _brave_search("test", 5)

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_respects_max_results(self, MockClient):
        items = [
            {"title": f"T{i}", "url": f"http://u{i}", "description": f"D{i}"}
            for i in range(10)
        ]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"web": {"results": items}}

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        web_module._brave_api_key = "key123"
        result = await _brave_search("test", 3)
        # Should contain at most 3 separator blocks
        assert result.count("---") <= 2  # 3 items => 2 separators


# ---------------------------------------------------------------------------
# TestDdgSearch
# ---------------------------------------------------------------------------

class TestDdgSearch:
    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_parse_results(self, MockClient):
        html = (
            '<html><body>'
            '<div class="result">'
            '<a class="result__a" href="http://example.com">Example Title</a>'
            '<a class="result__snippet">Snippet text here</a>'
            '</div>'
            '</body></html>'
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = html

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        result = await _ddg_search("test", 5)
        assert "Example Title" in result
        assert "http://example.com" in result
        assert "Snippet text here" in result

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_empty_results(self, MockClient):
        html = "<html><body><div>No results here</div></body></html>"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = html

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        result = await _ddg_search("nothing", 5)
        assert result == "No results found."

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_http_error(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        with pytest.raises(httpx.HTTPStatusError):
            await _ddg_search("test", 5)


# ---------------------------------------------------------------------------
# TestWebFetch
# ---------------------------------------------------------------------------

class TestWebFetch:
    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_html_content_to_markdown(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = "<h1>Hello</h1><p>World</p>"

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        init_web_tools(WebConfig(fetch_timeout=10))
        result = await web_fetch.ainvoke({"url": "http://example.com"})
        # markdownify should convert <h1> to something with "Hello"
        assert "Hello" in result
        assert "World" in result

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_plain_text(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "plain text content"

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        init_web_tools(WebConfig(fetch_timeout=10))
        result = await web_fetch.ainvoke({"url": "http://example.com/data.txt"})
        assert result == "plain text content"

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_truncation(self, MockClient):
        long_body = "<html><body>" + "A" * 20_000 + "</body></html>"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = long_body

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        init_web_tools(WebConfig(fetch_timeout=10))
        result = await web_fetch.ainvoke({"url": "http://example.com"})
        assert result.endswith("... (truncated)")

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_http_error(self, MockClient):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        mock_cm, _ = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        init_web_tools(WebConfig(fetch_timeout=10))
        result = await web_fetch.ainvoke({"url": "http://example.com/missing"})
        assert "Error fetching" in result

    @pytest.mark.asyncio
    @patch("src.tools.web.httpx.AsyncClient")
    async def test_redirect_followed(self, MockClient):
        """Verify that follow_redirects=True is passed to client.get()."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "redirected content"

        mock_cm, mock_client = _make_httpx_client_mock(mock_response)
        MockClient.return_value = mock_cm

        init_web_tools(WebConfig(fetch_timeout=10))
        result = await web_fetch.ainvoke({"url": "http://example.com/redirect"})
        # Verify follow_redirects was passed
        mock_client.get.assert_called_once()
        _, kwargs = mock_client.get.call_args
        assert kwargs.get("follow_redirects") is True
        assert result == "redirected content"
