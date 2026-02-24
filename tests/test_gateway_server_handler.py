"""Tests for GatewayHandler — HTTP request handling."""

import json
import io
from unittest.mock import patch, MagicMock
import subprocess

from src.gateway.server import GatewayHandler, validate_cwd


def _make_handler(method, path, body=None, headers=None, token="test-token"):
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
            handler.headers = {
                "Content-Length": str(len(body_bytes)),
                "Authorization": f"Bearer {token}",
            }
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
    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server._CWD_ALLOWLISTS", {})
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

    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server._CWD_ALLOWLISTS", {})
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

    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server._CWD_ALLOWLISTS", {})
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

    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    def test_execute_invalid_command(self):
        body = {"bridge": "claude-code", "cmd": ["bash", "-c", "echo hi"]}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(403)
        resp = _get_response_body(wfile)
        assert "not allowed" in resp["error"]

    @patch("src.gateway.server.TOKEN", "test-token")
    def test_execute_not_found_path(self):
        body = {"bridge": "claude-code", "cmd": ["claude"]}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.path = "/other"
        handler.do_POST()

        handler.send_response.assert_called_once_with(404)


class TestCheckAuth:
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

    @patch("src.gateway.server.TOKEN", "secret123")
    def test_missing_token_rejected(self):
        headers = {}
        handler, wfile = _make_handler("POST", "/execute", headers=headers)
        result = handler._check_auth()
        assert result is False
        handler.send_response.assert_called_once_with(401)


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

    def test_body_too_large(self):
        handler, wfile = _make_handler("POST", "/execute")
        handler.headers = {"Content-Length": "2000000"}
        handler.rfile = io.BytesIO(b"x" * 100)
        result = handler._read_json()
        assert result is None
        handler.send_response.assert_called_once_with(413)
        body = _get_response_body(wfile)
        assert "too large" in body["error"]

    def test_negative_content_length(self):
        handler, wfile = _make_handler("POST", "/execute")
        handler.headers = {"Content-Length": "-1"}
        handler.rfile = io.BytesIO(b"")
        result = handler._read_json()
        assert result is None
        handler.send_response.assert_called_once_with(413)


class TestCwdValidation:
    def test_no_cwd_always_allowed(self):
        ok, _ = validate_cwd(None, "claude-code", {})
        assert ok is True

    def test_cwd_rejected_when_no_allowlist(self):
        ok, error = validate_cwd("/etc", "spotify", {})
        assert ok is False
        assert "not allowed" in error

    def test_cwd_allowed_under_configured_dir(self, tmp_path):
        allowed = str(tmp_path)
        sub = tmp_path / "subdir"
        sub.mkdir()
        ok, _ = validate_cwd(str(sub), "claude-code", {"claude-code": [allowed]})
        assert ok is True

    def test_cwd_exact_match(self, tmp_path):
        allowed = str(tmp_path)
        ok, _ = validate_cwd(allowed, "claude-code", {"claude-code": [allowed]})
        assert ok is True

    def test_cwd_rejected_outside_allowed(self, tmp_path):
        allowed = str(tmp_path / "safe")
        (tmp_path / "safe").mkdir()
        ok, error = validate_cwd(str(tmp_path / "unsafe"), "claude-code",
                                  {"claude-code": [allowed]})
        assert ok is False
        assert "not under any allowed" in error

    def test_cwd_symlink_resolved(self, tmp_path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        symlink = tmp_path / "link"
        symlink.symlink_to(real_dir)
        ok, _ = validate_cwd(str(symlink), "claude-code",
                              {"claude-code": [str(real_dir)]})
        assert ok is True

    def test_cwd_symlink_escape_rejected(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        unsafe = tmp_path / "unsafe"
        unsafe.mkdir()
        symlink = safe / "escape"
        symlink.symlink_to(unsafe)
        ok, _ = validate_cwd(str(symlink), "claude-code",
                              {"claude-code": [str(safe)]})
        assert ok is False


class TestTimeoutValidation:
    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server._CWD_ALLOWLISTS", {})
    @patch("src.gateway.server.DEFAULT_TIMEOUT", 30)
    @patch("src.gateway.server.subprocess")
    def test_negative_timeout_clamped(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        body = {"bridge": "claude-code", "cmd": ["claude"], "timeout": -5}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(200)
        # timeout=0 after clamping → uses DEFAULT_TIMEOUT (30)
        _, kwargs = mock_subprocess.run.call_args
        assert kwargs["timeout"] == 30

    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server._CWD_ALLOWLISTS", {})
    @patch("src.gateway.server.DEFAULT_TIMEOUT", 30)
    @patch("src.gateway.server.subprocess")
    def test_huge_timeout_clamped(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        body = {"bridge": "claude-code", "cmd": ["claude"], "timeout": 99999}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(200)
        _, kwargs = mock_subprocess.run.call_args
        assert kwargs["timeout"] == 600  # MAX_TIMEOUT

    @patch("src.gateway.server.TOKEN", "test-token")
    @patch("src.gateway.server._ALLOWLISTS", {"claude-code": {"claude"}})
    @patch("src.gateway.server._CWD_ALLOWLISTS", {})
    @patch("src.gateway.server.DEFAULT_TIMEOUT", 30)
    @patch("src.gateway.server.subprocess")
    def test_zero_timeout_uses_default(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        body = {"bridge": "claude-code", "cmd": ["claude"], "timeout": 0}
        handler, wfile = _make_handler("POST", "/execute", body=body)
        handler.do_POST()

        handler.send_response.assert_called_once_with(200)
        _, kwargs = mock_subprocess.run.call_args
        assert kwargs["timeout"] == 30  # DEFAULT_TIMEOUT
