"""Tests for Claude Code cc: commands — UserSession extensions, _build_command flags, persistence."""

import json

import pytest

from src.bridges.claude_code.bridge import ClaudeCodeBridge, UserSession
from src.config import AppConfig, ClaudeCodeConfig


@pytest.fixture
def bridge(tmp_path) -> ClaudeCodeBridge:
    config = AppConfig(
        claude_code=ClaudeCodeConfig(
            state_file=str(tmp_path / "cc_states.json"),
            projects_dir=str(tmp_path / "projects"),
        ),
    )
    return ClaudeCodeBridge(config)


# --- UserSession fields ---

class TestUserSessionFields:
    def test_defaults(self):
        s = UserSession()
        assert s.active_model is None
        assert s.active_effort is None

    def test_set_fields(self):
        s = UserSession(active_model="sonnet", active_effort="high")
        assert s.active_model == "sonnet"
        assert s.active_effort == "high"


# --- set_model / set_effort ---

class TestBridgeSetters:
    def test_set_model(self, bridge):
        bridge.activate_session("u1", "proj", "/path", session_id="s1")
        bridge.set_model("u1", "opus")
        assert bridge.get_user_state("u1").active_model == "opus"

    def test_set_model_none(self, bridge):
        bridge.activate_session("u1", "proj", "/path", session_id="s1")
        bridge.set_model("u1", "opus")
        bridge.set_model("u1", None)
        assert bridge.get_user_state("u1").active_model is None

    def test_set_effort(self, bridge):
        bridge.activate_session("u1", "proj", "/path", session_id="s1")
        bridge.set_effort("u1", "low")
        assert bridge.get_user_state("u1").active_effort == "low"

    def test_set_effort_none(self, bridge):
        bridge.activate_session("u1", "proj", "/path", session_id="s1")
        bridge.set_effort("u1", "high")
        bridge.set_effort("u1", None)
        assert bridge.get_user_state("u1").active_effort is None


# --- _build_command with model/effort ---

class TestBuildCommandFlags:
    def test_no_model_no_effort(self, bridge):
        state = UserSession(active_session_id="abc123")
        cmd = bridge._build_command("hello", state)
        assert "--model" not in cmd
        assert "--effort" not in cmd

    def test_with_model(self, bridge):
        state = UserSession(active_session_id="abc123", active_model="sonnet")
        cmd = bridge._build_command("hello", state)
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "sonnet"

    def test_with_effort(self, bridge):
        state = UserSession(active_session_id="abc123", active_effort="high")
        cmd = bridge._build_command("hello", state)
        idx = cmd.index("--effort")
        assert cmd[idx + 1] == "high"

    def test_with_both(self, bridge):
        state = UserSession(
            active_session_id="abc123",
            active_model="opus",
            active_effort="low",
        )
        cmd = bridge._build_command("hello", state)
        assert "--model" in cmd
        assert "--effort" in cmd
        assert cmd[cmd.index("--model") + 1] == "opus"
        assert cmd[cmd.index("--effort") + 1] == "low"

    def test_model_effort_before_text(self, bridge):
        state = UserSession(
            active_session_id="abc123",
            active_model="sonnet",
            active_effort="medium",
        )
        cmd = bridge._build_command("my prompt", state)
        # Text should be the last argument
        assert cmd[-1] == "my prompt"
        assert cmd.index("--model") < len(cmd) - 1
        assert cmd.index("--effort") < len(cmd) - 1

    def test_fork_flag(self, bridge):
        state = UserSession(active_session_id="abc123")
        cmd = bridge._build_command("hello", state, fork=True)
        assert "--fork-session" in cmd
        assert "--resume" in cmd

    def test_fork_without_session(self, bridge):
        state = UserSession()
        cmd = bridge._build_command("hello", state, fork=True)
        assert "--fork-session" not in cmd
        assert "--resume" not in cmd


# --- Persistence roundtrip ---

class TestPersistenceRoundtrip:
    def test_model_effort_persisted(self, tmp_path):
        state_file = str(tmp_path / "cc_states.json")
        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                state_file=state_file,
                projects_dir=str(tmp_path / "projects"),
            ),
        )

        # First bridge: set state
        bridge1 = ClaudeCodeBridge(config)
        bridge1.activate_session("u1", "proj", "/path", session_id="s1")
        bridge1.set_model("u1", "opus")
        bridge1.set_effort("u1", "high")

        # Second bridge: restore state
        bridge2 = ClaudeCodeBridge(config)
        state = bridge2.get_user_state("u1")
        assert state.active_model == "opus"
        assert state.active_effort == "high"
        assert state.active_session_id == "s1"

    def test_none_values_persisted(self, tmp_path):
        state_file = str(tmp_path / "cc_states.json")
        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                state_file=state_file,
                projects_dir=str(tmp_path / "projects"),
            ),
        )

        bridge1 = ClaudeCodeBridge(config)
        bridge1.activate_session("u1", "proj", "/path", session_id="s1")
        # Don't set model/effort — should persist as None

        bridge2 = ClaudeCodeBridge(config)
        state = bridge2.get_user_state("u1")
        assert state.active_model is None
        assert state.active_effort is None

    def test_exit_clears_state(self, bridge):
        bridge.activate_session("u1", "proj", "/path", session_id="s1")
        bridge.set_model("u1", "opus")
        bridge.exit_mode("u1")
        state = bridge.get_user_state("u1")
        assert state.active_model is None
        assert state.mode == "ciana"
