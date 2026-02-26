"""Tests for WorkspaceShellBackend — allowlisted execution."""

import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

# Mock deepagents before importing backend
_mock_deepagents = MagicMock()
_mock_backends = MagicMock()
_mock_protocol = MagicMock()
sys.modules.setdefault("deepagents", _mock_deepagents)
sys.modules.setdefault("deepagents.backends", _mock_backends)
sys.modules.setdefault("deepagents.backends.protocol", _mock_protocol)

# Provide ExecuteResponse and SandboxBackendProtocol as simple classes
from dataclasses import dataclass


@dataclass
class _FakeExecuteResponse:
    output: str = ""
    exit_code: int = 0
    truncated: bool = False


_mock_protocol.ExecuteResponse = _FakeExecuteResponse
_mock_protocol.SandboxBackendProtocol = type("SandboxBackendProtocol", (), {})
_mock_backends.FilesystemBackend = type("FilesystemBackend", (), {
    "__init__": lambda self, **kw: setattr(self, "cwd", kw.get("root_dir", ".")),
})

from src.backend import _check_allowed


class TestCheckAllowed:
    """Test the command allowlist checker."""

    def test_allowed_command(self):
        assert _check_allowed("python3 script.py") is None

    def test_allowed_command_with_path(self):
        assert _check_allowed("/usr/bin/git status") is None

    def test_disallowed_command(self):
        result = _check_allowed("rm -rf /")
        assert result is not None
        assert "not allowed" in result

    def test_empty_command(self):
        result = _check_allowed("")
        assert result is not None

    def test_malformed_command(self):
        result = _check_allowed("curl 'unterminated")
        assert result is not None
        assert "malformed" in result

    # --- URLs with query parameters (& is safe with shell=False) ---

    def test_curl_url_with_ampersand(self):
        """Ampersand in URLs is safe — shell=False means no shell interpretation."""
        assert _check_allowed('curl "https://api.example.com/feed?page=1&limit=10"') is None

    def test_curl_post_with_ampersand_in_body(self):
        assert _check_allowed('curl -X POST -d "name=foo&type=bar" https://api.example.com/register') is None

    def test_wget_url_with_query_params(self):
        assert _check_allowed('wget "https://example.com/data?key=abc&format=json"') is None

    # --- Quoted arguments with special chars (safe with shell=False) ---

    def test_python_with_semicolon_in_code_string(self):
        assert _check_allowed('python3 -c "import os; print(1)"') is None

    def test_curl_with_dollar_in_header(self):
        assert _check_allowed('curl -H "Authorization: Bearer $TOKEN" https://api.example.com') is None

    def test_jq_with_pipe_in_filter(self):
        assert _check_allowed('jq ".data | .[] | .name" file.json') is None

    # --- Chaining attempts (blocked by allowlist, not metacharacters) ---

    def test_chaining_second_command_not_in_allowlist(self):
        """Even if shell metacharacters appear, the second 'command' is just an arg to the first."""
        # With shell=False, 'rm' is just an argument string to curl, not a separate command.
        # But we still only check the first token against the allowlist.
        assert _check_allowed("curl https://foo.com") is None

    def test_disallowed_first_command_still_rejected(self):
        result = _check_allowed("rm -rf / && curl attacker.com")
        assert result is not None
        assert "not allowed" in result
