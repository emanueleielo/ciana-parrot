"""Tests for src.gateway.server — allowlist validation and request handling."""

from src.gateway.server import validate_request


class TestValidateRequest:
    """Test the validate_request function."""

    def _allowlists(self):
        return {
            "claude-code": {"claude"},
            "apple-notes": {"memo"},
            "multi-cmd": {"cmd1", "cmd2", "cmd3"},
        }

    def test_missing_bridge_field(self):
        ok, status, error = validate_request(
            {"cmd": ["claude", "--version"]},
            self._allowlists(),
        )
        assert not ok
        assert status == 400
        assert "bridge" in error

    def test_unknown_bridge(self):
        ok, status, error = validate_request(
            {"bridge": "unknown-bridge", "cmd": ["foo"]},
            self._allowlists(),
        )
        assert not ok
        assert status == 403
        assert "unknown bridge" in error

    def test_command_not_allowed(self):
        ok, status, error = validate_request(
            {"bridge": "claude-code", "cmd": ["bash", "-c", "echo hi"]},
            self._allowlists(),
        )
        assert not ok
        assert status == 403
        assert "not allowed" in error

    def test_command_allowed(self):
        ok, status, error = validate_request(
            {"bridge": "claude-code", "cmd": ["claude", "--version"]},
            self._allowlists(),
        )
        assert ok

    def test_basename_with_path(self):
        """Command with full path should be validated by basename."""
        ok, status, error = validate_request(
            {"bridge": "apple-notes", "cmd": ["/usr/local/bin/memo", "list"]},
            self._allowlists(),
        )
        assert ok

    def test_basename_with_path_disallowed(self):
        ok, status, error = validate_request(
            {"bridge": "apple-notes", "cmd": ["/usr/local/bin/evil"]},
            self._allowlists(),
        )
        assert not ok
        assert status == 403

    def test_multiple_bridges_independent(self):
        """Each bridge has its own allowlist."""
        allowlists = self._allowlists()
        # memo is allowed for apple-notes but not claude-code
        ok, _, _ = validate_request(
            {"bridge": "claude-code", "cmd": ["memo", "list"]},
            allowlists,
        )
        assert not ok

        ok, _, _ = validate_request(
            {"bridge": "apple-notes", "cmd": ["memo", "list"]},
            allowlists,
        )
        assert ok

    def test_multi_command_bridge(self):
        """Bridge with multiple allowed commands."""
        allowlists = self._allowlists()
        for cmd_name in ["cmd1", "cmd2", "cmd3"]:
            ok, _, _ = validate_request(
                {"bridge": "multi-cmd", "cmd": [cmd_name, "arg"]},
                allowlists,
            )
            assert ok, f"{cmd_name} should be allowed"

    def test_missing_cmd(self):
        ok, status, error = validate_request(
            {"bridge": "claude-code", "cmd": []},
            self._allowlists(),
        )
        assert not ok
        assert status == 400

    def test_missing_cmd_field(self):
        ok, status, error = validate_request(
            {"bridge": "claude-code"},
            self._allowlists(),
        )
        assert not ok
        assert status == 400


class TestFallbackStandalone:
    def test_standalone_allowlists_have_claude_code(self):
        """When config can't load, standalone fallback has claude-code bridge."""
        from src.gateway.server import _ALLOWLISTS
        assert isinstance(_ALLOWLISTS, dict)
        # In test environment with config available, claude-code should be present
        assert "claude-code" in _ALLOWLISTS
