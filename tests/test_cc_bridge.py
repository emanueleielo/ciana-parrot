"""Tests for ClaudeCodeBridge — state, projects, execution, parsing."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.gateway.bridges.claude_code.bridge import (
    CCResponse,
    ClaudeCodeBridge,
    ConversationInfo,
    ProjectInfo,
    UserSession,
    _clean_preview,
)
from src.config import AppConfig, ClaudeCodeConfig
from src.events import TextEvent, ThinkingEvent, ToolCallEvent


@pytest.fixture
def bridge(tmp_path):
    config = AppConfig(
        claude_code=ClaudeCodeConfig(
            state_file=str(tmp_path / "cc_states.json"),
            projects_dir=str(tmp_path / "projects"),
        ),
    )
    return ClaudeCodeBridge(config)


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

class TestStateManagement:
    def test_get_user_state_creates_new(self, bridge):
        state = bridge.get_user_state("u1")
        assert isinstance(state, UserSession)
        assert state.mode == "ciana"

    def test_get_user_state_returns_existing(self, bridge):
        state1 = bridge.get_user_state("u1")
        state2 = bridge.get_user_state("u1")
        assert state1 is state2

    def test_is_claude_code_mode_false_by_default(self, bridge):
        bridge.get_user_state("u1")
        assert bridge.is_claude_code_mode("u1") is False

    def test_is_claude_code_mode_true_after_activate(self, bridge):
        bridge.activate_session("u1", "proj", "/path/to/proj")
        assert bridge.is_claude_code_mode("u1") is True

    def test_restore_states_from_store(self, tmp_path):
        state_file = tmp_path / "cc_states.json"
        state_file.write_text(json.dumps({
            "u1": {
                "mode": "claude_code",
                "active_project": "proj-enc",
                "active_project_path": "/some/path",
                "active_session_id": "sess-123",
                "active_model": "opus",
                "active_effort": "high",
            }
        }))
        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                state_file=str(state_file),
                projects_dir=str(tmp_path / "projects"),
            ),
        )
        bridge = ClaudeCodeBridge(config)
        state = bridge.get_user_state("u1")
        assert state.mode == "claude_code"
        assert state.active_project == "proj-enc"
        assert state.active_project_path == "/some/path"
        assert state.active_session_id == "sess-123"
        assert state.active_model == "opus"
        assert state.active_effort == "high"


# ---------------------------------------------------------------------------
# List projects
# ---------------------------------------------------------------------------

class TestListProjects:
    def test_no_dir(self, bridge):
        assert bridge.list_projects() == []

    def test_empty_dir(self, bridge, tmp_path):
        (tmp_path / "projects").mkdir(parents=True)
        assert bridge.list_projects() == []

    def test_multiple_projects_sorted_by_mtime(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects"
        proj_dir.mkdir(parents=True)

        # Older project
        p1 = proj_dir / "proj1"
        p1.mkdir()
        j1 = p1 / "session1.jsonl"
        j1.write_text('{"cwd": "/path/to/proj1"}\n')
        # Set mtime to 1000 seconds ago
        old_time = time.time() - 1000
        os.utime(j1, (old_time, old_time))

        # Newer project
        p2 = proj_dir / "proj2"
        p2.mkdir()
        j2 = p2 / "session2.jsonl"
        j2.write_text('{"cwd": "/path/to/proj2"}\n')

        projects = bridge.list_projects()
        assert len(projects) == 2
        # Newest first
        assert projects[0].encoded_name == "proj2"
        assert projects[1].encoded_name == "proj1"

    def test_skips_non_dirs_and_empty_projects(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects"
        proj_dir.mkdir(parents=True)

        # Regular file (not a directory)
        (proj_dir / "not_a_dir.txt").write_text("hello")

        # Empty project dir (no .jsonl files)
        empty = proj_dir / "empty_proj"
        empty.mkdir()

        # Valid project with a .jsonl
        valid = proj_dir / "valid_proj"
        valid.mkdir()
        (valid / "sess.jsonl").write_text('{"cwd": "/valid"}\n')

        projects = bridge.list_projects()
        assert len(projects) == 1
        assert projects[0].encoded_name == "valid_proj"


# ---------------------------------------------------------------------------
# List conversations
# ---------------------------------------------------------------------------

class TestListConversations:
    def test_no_dir(self, bridge):
        assert bridge.list_conversations("nonexistent") == []

    def test_parses_jsonl(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects" / "myproj"
        proj_dir.mkdir(parents=True)

        # Conversation 1
        c1 = proj_dir / "conv1.jsonl"
        c1.write_text(
            '{"timestamp": "2024-01-01T00:00:00Z"}\n'
            '{"type": "user", "message": {"role": "user", "content": "hello world"}}\n'
        )

        # Conversation 2
        c2 = proj_dir / "conv2.jsonl"
        c2.write_text(
            '{"timestamp": "2024-02-01T00:00:00Z"}\n'
            '{"type": "user", "message": {"role": "user", "content": "second conv"}}\n'
        )

        convos = bridge.list_conversations("myproj")
        assert len(convos) == 2
        assert all(isinstance(c, ConversationInfo) for c in convos)

    def test_sorted_by_timestamp(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects" / "myproj"
        proj_dir.mkdir(parents=True)

        # Older conversation
        c1 = proj_dir / "older.jsonl"
        c1.write_text('{"timestamp": "2024-01-01T00:00:00Z"}\n'
                       '{"type": "user", "message": {"role": "user", "content": "old"}}\n')

        # Newer conversation
        c2 = proj_dir / "newer.jsonl"
        c2.write_text('{"timestamp": "2025-06-01T00:00:00Z"}\n'
                       '{"type": "user", "message": {"role": "user", "content": "new"}}\n')

        convos = bridge.list_conversations("myproj")
        assert convos[0].session_id == "newer"
        assert convos[1].session_id == "older"


# ---------------------------------------------------------------------------
# _peek_cwd
# ---------------------------------------------------------------------------

class TestPeekCwd:
    def test_finds_cwd(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects" / "proj1"
        proj_dir.mkdir(parents=True)
        jsonl = proj_dir / "sess.jsonl"
        jsonl.write_text('{"cwd": "/path/project"}\n{"type": "user"}\n')
        assert bridge._peek_cwd(jsonl) == "/path/project"

    def test_empty_file(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects" / "proj1"
        proj_dir.mkdir(parents=True)
        jsonl = proj_dir / "empty.jsonl"
        jsonl.write_text("")
        assert bridge._peek_cwd(jsonl) == ""

    def test_invalid_json(self, bridge, tmp_path):
        proj_dir = tmp_path / "projects" / "proj1"
        proj_dir.mkdir(parents=True)
        jsonl = proj_dir / "bad.jsonl"
        jsonl.write_text("this is not json\n")
        assert bridge._peek_cwd(jsonl) == ""


# ---------------------------------------------------------------------------
# _clean_preview
# ---------------------------------------------------------------------------

class TestCleanPreview:
    def test_command_message(self):
        text = "<command-message>commit</command-message>"
        assert _clean_preview(text) == "/commit"

    def test_command_with_args(self):
        text = (
            "<command-message>review</command-message>"
            "<command-args>PR #42</command-args>"
        )
        assert _clean_preview(text) == "/review PR #42"

    def test_plain_text_truncation(self):
        long_text = "x" * 200
        result = _clean_preview(long_text)
        assert len(result) == 120


# ---------------------------------------------------------------------------
# Execution routing
# ---------------------------------------------------------------------------

class TestExecutionRouting:
    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_routes_to_bridge_when_set(self, MockClient, tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "stdout": '{"type":"result","result":"ok"}',
            "stderr": "",
            "returncode": 0,
        }
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                bridge_url="http://localhost:9842",
                state_file=str(tmp_path / "cc_states.json"),
                projects_dir=str(tmp_path / "projects"),
            ),
        )
        bridge = ClaudeCodeBridge(config)
        result = await bridge._execute_command(["claude", "-p", "hi"], "/path")
        mock_client_instance.post.assert_called_once()
        assert result.error == ""

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.asyncio.create_subprocess_exec")
    async def test_routes_to_local_when_no_gateway(self, mock_exec, bridge):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b'{"type":"result","result":"ok"}', b"")
        )
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        result = await bridge._execute_command(["claude", "-p", "hi"], None)
        mock_exec.assert_called_once()
        assert result.error == ""


# ---------------------------------------------------------------------------
# _execute_via_gateway
# ---------------------------------------------------------------------------

class TestExecuteViaBridge:
    @pytest.fixture
    def bridge_with_url(self, tmp_path):
        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                bridge_url="http://localhost:9842",
                state_file=str(tmp_path / "cc_states.json"),
                projects_dir=str(tmp_path / "projects"),
            ),
        )
        return ClaudeCodeBridge(config)

    def _mock_httpx(self, MockClient, response):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        return mock_client

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_success(self, MockClient, bridge_with_url):
        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.json.return_value = {
            "stdout": '{"type":"result","result":"ok"}',
            "stderr": "",
            "returncode": 0,
        }
        self._mock_httpx(MockClient, resp)
        result = await bridge_with_url._execute_via_bridge(["cmd"], "/path")
        assert result.error == ""
        assert len(result.events) >= 1

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_bridge_connect_error(self, MockClient, bridge_with_url):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        result = await bridge_with_url._execute_via_bridge(["cmd"], "/path")
        assert "Cannot connect" in result.error

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_nonzero_returncode(self, MockClient, bridge_with_url):
        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.json.return_value = {
            "stdout": "",
            "stderr": "error msg",
            "returncode": 1,
        }
        self._mock_httpx(MockClient, resp)
        result = await bridge_with_url._execute_via_bridge(["cmd"], "/path")
        assert "error msg" in result.error

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_empty_stdout(self, MockClient, bridge_with_url):
        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.json.return_value = {
            "stdout": "",
            "stderr": "",
            "returncode": 0,
        }
        self._mock_httpx(MockClient, resp)
        result = await bridge_with_url._execute_via_bridge(["cmd"], "/path")
        assert result.error == ""
        assert any(
            isinstance(e, TextEvent) and "(empty response)" in e.text
            for e in result.events
        )


# ---------------------------------------------------------------------------
# _execute_local
# ---------------------------------------------------------------------------

class TestExecuteLocal:
    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.asyncio.create_subprocess_exec")
    async def test_success(self, mock_exec, bridge):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b'{"type":"result","result":"ok"}', b"")
        )
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        result = await bridge._execute_local(["claude", "-p", "test"])
        assert result.error == ""
        assert len(result.events) >= 1
        assert any(isinstance(e, TextEvent) for e in result.events)

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.asyncio.create_subprocess_exec")
    async def test_timeout(self, mock_exec, tmp_path):
        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                state_file=str(tmp_path / "cc_states.json"),
                projects_dir=str(tmp_path / "projects"),
                timeout=5,  # non-zero to trigger wait_for path
            ),
        )
        bridge = ClaudeCodeBridge(config)
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_exec.return_value = mock_proc
        result = await bridge._execute_local(["claude", "-p", "test"])
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.asyncio.create_subprocess_exec")
    async def test_nonzero_exit(self, mock_exec, bridge):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"some error output")
        )
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc
        result = await bridge._execute_local(["claude", "-p", "test"])
        assert "some error output" in result.error


# ---------------------------------------------------------------------------
# _check_gateway
# ---------------------------------------------------------------------------

class TestCheckBridge:
    def _mock_httpx_get(self, MockClient, response):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        return mock_client

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_ok_with_cc_bridge(self, MockClient, tmp_path):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "status": "ok",
            "bridges": ["claude-code", "other"],
        }
        self._mock_httpx_get(MockClient, resp)

        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                bridge_url="http://localhost:9842",
                state_file=str(tmp_path / "cc_states.json"),
                projects_dir=str(tmp_path / "projects"),
            ),
        )
        bridge = ClaudeCodeBridge(config)
        ok, msg = await bridge._check_bridge()
        assert ok is True
        assert "Gateway OK" in msg

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.httpx.AsyncClient")
    async def test_no_cc_bridge(self, MockClient, tmp_path):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "status": "ok",
            "bridges": ["other"],
        }
        self._mock_httpx_get(MockClient, resp)

        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                bridge_url="http://localhost:9842",
                state_file=str(tmp_path / "cc_states.json"),
                projects_dir=str(tmp_path / "projects"),
            ),
        )
        bridge = ClaudeCodeBridge(config)
        ok, msg = await bridge._check_bridge()
        assert ok is False
        assert "not registered" in msg


# ---------------------------------------------------------------------------
# _check_local
# ---------------------------------------------------------------------------

class TestCheckLocal:
    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.asyncio.create_subprocess_exec")
    async def test_found(self, mock_exec, bridge):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"1.0.0\n", b""))
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        ok, msg = await bridge._check_local()
        assert ok is True
        assert "1.0.0" in msg

    @pytest.mark.asyncio
    @patch("src.gateway.bridges.claude_code.bridge.asyncio.create_subprocess_exec")
    async def test_not_found(self, mock_exec, bridge):
        mock_exec.side_effect = FileNotFoundError("No such file")
        ok, msg = await bridge._check_local()
        assert ok is False
        assert "not found" in msg.lower()
