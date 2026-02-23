"""Tests for GatewayHandler — HTTP request handling."""

import json
import io
from unittest.mock import patch, MagicMock
import subprocess

from src.gateway.server import GatewayHandler


def _make_handler(method, path, body=None, headers=None, token=""):
    """Create a GatewayHandler with mocked I/O for testing.

    Returns (handler, wfile) where wfile is a BytesIO capturing response body.
    """
    handler = GatewayHandler.__new__(GatewayHandler)
    handler.path = path
    handler.command = method
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)

    wfile = io.BytesIO()
    handler.wfile = wfile

    # Mock response-writing methods
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.log_message = MagicMock()

    if body is not None:
        body_bytes = json.dumps(body).encode() if isinstance(body, dict) else body.encode()
        handler.rfile = io.BytesIO(body_bytes)
        if headers is not None and isinstance(headers, dict):
            headers["Content-Length"] = str(len(body_bytes))
            handler.headers = headers
        else:
            handler.headers = {"Content-Length": str(len(body_bytes))}
    else:
        handler.rfile = io.BytesIO(b"")
        handler.headers = headers if headers is not None else {}

    return handler, wfile


def _get_response_body(wfile):
    """Extract the JSON body written to wfile."""
    return json.loads(wfile.getvalue())


class TestDoGet:
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    def test_health_endpoint(self):
        handler, wfile = _make_handler("GET", "/health")
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)
        body = _get_response_body(wfile)
        assert body["status"] == "ok"
        assert "bridges" in body
        assert "claude-code" in body["bridges"]

    def test_unknown_path_404(self):
        handler, wfile = _make_handler("GET", "/unknown")
        handler.do_GET()
        handler.send_response.assert_called_once_with(404)
        body = _get_response_body(wfile)
        assert "error" in body


class TestDoPost:
    @patch("src.gateway.server.TOKEN", "")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server.subprocess")
    def test_execute_success(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        body = {"bridge": "claude-code", "cmd": ["claude", "-p", "test"]}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(200)
        resp = _get_response_body(wfile)
        assert resp["stdout"] == "hello\n"
        assert resp["stderr"] == ""
        assert resp["returncode"] == 0

    @patch("src.gateway.server.TOKEN", "")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server.subprocess")
    def test_execute_subprocess_timeout(self, mock_subprocess):
        mock_subprocess.run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=30)
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        body = {"bridge": "claude-code", "cmd": ["claude", "-p", "test"], "timeout": 30}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(200)
        resp = _get_response_body(wfile)
        assert "timed out" in resp["stderr"].lower()
        assert resp["returncode"] == -1

    @patch("src.gateway.server.TOKEN", "")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server.subprocess")
    def test_execute_subprocess_error(self, mock_subprocess):
        mock_subprocess.run.side_effect = OSError("No such file")
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        body = {"bridge": "claude-code", "cmd": ["claude", "-p", "test"]}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(500)
        resp = _get_response_body(wfile)
        assert "error" in resp

    @patch("src.gateway.server.TOKEN", "")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    def test_execute_invalid_command(self):
        body = {"bridge": "claude-code", "cmd": ["bash", "-c", "echo hi"]}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(403)
        resp = _get_response_body(wfile)
        assert "not allowed" in resp["error"]

    @patch("src.gateway.server.TOKEN", "")
    def test_execute_not_found_path(self):
        body = {"bridge": "claude-code", "cmd": ["claude"]}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.path = "/other"
        handler.do_POST()

        handler.send_response.assert_called_once_with(404)


class TestCheckAuth:
    @patch("src.gateway.server.TOKEN", "")
    def test_no_token_configured(self):
        handler, _ = _make_handler("POST", "/execute", headers={})
        assert handler._check_auth() is True

    @patch("src.gateway.server.TOKEN", "secret123")
    def test_valid_token(self):
        headers = {"Authorization": "Bearer secret123"}
        handler, _ = _make_handler("POST", "/execute", headers=headers)
        assert handler._check_auth() is True

    @patch("src.gateway.server.TOKEN", "secret123")
    def test_invalid_token(self):
        headers = {"Authorization": "Bearer wrongtoken"}
        handler, wfile = _make_handler("POST", "/execute", headers=headers)
        result = handler._check_auth()
        assert result is False
        handler.send_response.assert_called_once_with(401)
        body = _get_response_body(wfile)
        assert "unauthorized" in body["error"]


class TestReadJson:
    def test_valid_json(self):
        body = {"key": "value"}
        handler, _ = _make_handler("POST", "/execute", body=body)
        result = handler._read_json()
        assert result == {"key": "value"}

    def test_invalid_json(self):
        handler, wfile = _make_handler("POST", "/execute")
        handler.headers = {"Content-Length": "11"}
        handler.rfile = io.BytesIO(b"not { json}")
        result = handler._read_json()
        assert result is None
        handler.send_response.assert_called_once_with(400)
        body = _get_response_body(wfile)
        assert "invalid JSON" in body["error"]
