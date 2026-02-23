"""Tests for src.gateway.client — GatewayClient async HTTP client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.gateway.client import GatewayClient, GatewayResult


@pytest.fixture
def client():
    return GatewayClient("http://localhost:9842", token="test-token")


@pytest.fixture
def client_no_auth():
    return GatewayClient("http://localhost:9842")


class TestGatewayResult:
    def test_defaults(self):
        r = GatewayResult()
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.returncode == 0
        assert r.error == ""

    def test_custom_values(self):
        r = GatewayResult(stdout="out", stderr="err", returncode=1, error="oops")
        assert r.stdout == "out"
        assert r.returncode == 1
        assert r.error == "oops"


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    return resp


class TestGatewayClientExecute:
    @pytest.mark.asyncio
    async def test_success(self, client):
        mock_resp = _mock_response(200, {"stdout": "hello\n", "stderr": "", "returncode": 0})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.execute("claude-code", ["claude", "--version"])

        assert result.stdout == "hello\n"
        assert result.returncode == 0
        assert result.error == ""

        # Verify request
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "claude-code" in str(call_args)

    @pytest.mark.asyncio
    async def test_auth_header_sent(self, client):
        mock_resp = _mock_response(200, {"stdout": "", "stderr": "", "returncode": 0})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            await client.execute("test", ["cmd"])

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_no_auth_header_when_no_token(self, client_no_auth):
        mock_resp = _mock_response(200, {"stdout": "", "stderr": "", "returncode": 0})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            await client_no_auth.execute("test", ["cmd"])

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_auth_failure(self, client):
        mock_resp = _mock_response(401, {"error": "unauthorized"})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.execute("claude-code", ["claude"])

        assert "auth failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_forbidden(self, client):
        mock_resp = _mock_response(403, {"error": "command 'evil' not allowed for bridge 'claude-code'"})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.execute("claude-code", ["evil"])

        assert "not allowed" in result.error

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.execute("claude-code", ["claude"])

        assert "Cannot connect" in result.error

    @pytest.mark.asyncio
    async def test_timeout(self, client):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.execute("claude-code", ["claude"], timeout=5)

        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_payload_includes_cwd_and_timeout(self, client):
        mock_resp = _mock_response(200, {"stdout": "", "stderr": "", "returncode": 0})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            await client.execute("test", ["cmd"], cwd="/some/dir", timeout=10)

        call_kwargs = mock_client.post.call_args
        json_payload = call_kwargs.kwargs.get("json", {})
        assert json_payload["cwd"] == "/some/dir"
        assert json_payload["timeout"] == 10
        assert json_payload["bridge"] == "test"

    @pytest.mark.asyncio
    async def test_server_error(self, client):
        mock_resp = _mock_response(500, {"error": "internal"})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.execute("test", ["cmd"])

        assert "500" in result.error


class TestGatewayClientHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, client):
        mock_resp = _mock_response(200, {"status": "ok", "bridges": ["claude-code", "apple-notes"]})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            ok, data = await client.health()

        assert ok
        assert data["bridges"] == ["claude-code", "apple-notes"]

    @pytest.mark.asyncio
    async def test_health_error(self, client):
        mock_resp = _mock_response(500, {"error": "internal"})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            ok, data = await client.health()

        assert not ok
        assert "500" in data["error"]

    @pytest.mark.asyncio
    async def test_health_connection_error(self, client):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.gateway.client.httpx.AsyncClient", return_value=mock_client):
            ok, data = await client.health()

        assert not ok
        assert "Cannot connect" in data["error"]
