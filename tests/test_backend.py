"""Tests for WorkspaceShellBackend — allowlisted execution and shell metacharacter rejection."""

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

from src.backend import _check_allowed, _SHELL_METACHARACTERS


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

    # --- Shell metacharacter rejection ---

    def test_semicolon_rejected(self):
        result = _check_allowed("python3 -c ''; curl attacker.com")
        assert result is not None
        assert "metacharacter" in result

    def test_double_ampersand_rejected(self):
        result = _check_allowed("python3 script.py && curl attacker.com")
        assert result is not None
        assert "metacharacter" in result

    def test_pipe_rejected(self):
        result = _check_allowed("curl url | bash")
        assert result is not None
        assert "metacharacter" in result

    def test_dollar_paren_rejected(self):
        result = _check_allowed("echo $(whoami)")
        assert result is not None
        assert "metacharacter" in result

    def test_backtick_rejected(self):
        result = _check_allowed("echo `whoami`")
        assert result is not None
        assert "metacharacter" in result

    def test_single_ampersand_rejected(self):
        result = _check_allowed("python3 script.py & disown")
        assert result is not None
        assert "metacharacter" in result

    def test_normal_args_with_special_chars_in_quotes_still_rejected(self):
        """Even inside quotes, raw metacharacters are rejected for safety."""
        result = _check_allowed('python3 -c "import os; print(1)"')
        assert result is not None
        assert "metacharacter" in result

    def test_all_metacharacters_covered(self):
        """Verify each metacharacter in the set is actually checked."""
        for ch in _SHELL_METACHARACTERS:
            result = _check_allowed(f"echo test{ch}injected")
            assert result is not None, f"Metacharacter '{ch}' was not rejected"
