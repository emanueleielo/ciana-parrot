"""Tests for MessageRouter — sync_counters, log_message, multimodal, edge cases."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.channels.base import IncomingMessage
from src.config import AgentConfig, AppConfig, ChannelsConfig, TelegramChannelConfig
from src.router import MessageRouter


@pytest.fixture
def router_ext_config(tmp_path) -> AppConfig:
    """Config with separate workspace and data dirs under tmp_path."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return AppConfig(
        agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
        channels=ChannelsConfig(
            telegram=TelegramChannelConfig(
                enabled=True,
                token="tok",
                trigger="@Bot",
                allowed_users=["user1"],
            )
        ),
    )


class TestSyncCountersWithCheckpoints:
    def test_syncs_from_db(self, mock_agent, tmp_path):
        """Session counters should sync to the max checkpoint suffix (resume, not bump)."""
        data = tmp_path / "data"
        data.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        db_path = data / "checkpoints.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE checkpoints (thread_id TEXT)")
        conn.execute("INSERT INTO checkpoints VALUES (?)", ("telegram_123_s2",))
        conn.execute("INSERT INTO checkpoints VALUES (?)", ("telegram_123_s5",))
        conn.commit()
        conn.close()

        config = AppConfig(
            agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
            channels=ChannelsConfig(
                telegram=TelegramChannelConfig(token="t", trigger="@Bot")
            ),
        )
        router = MessageRouter(mock_agent, config, checkpointer=MagicMock())
        assert router._session_counters.get("telegram_123") == 5

    def test_no_db_file(self, mock_agent, tmp_path):
        """No checkpoints.db should not cause an error."""
        data = tmp_path / "data"
        data.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        config = AppConfig(
            agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
            channels=ChannelsConfig(
                telegram=TelegramChannelConfig(token="t", trigger="@Bot")
            ),
        )
        # Should not raise
        router = MessageRouter(mock_agent, config, checkpointer=MagicMock())
        assert router._session_counters == {}

    def test_empty_db(self, mock_agent, tmp_path):
        """Empty checkpoints table should leave counters unchanged."""
        data = tmp_path / "data"
        data.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        db_path = data / "checkpoints.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE checkpoints (thread_id TEXT)")
        conn.commit()
        conn.close()

        config = AppConfig(
            agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
            channels=ChannelsConfig(
                telegram=TelegramChannelConfig(token="t", trigger="@Bot")
            ),
        )
        router = MessageRouter(mock_agent, config, checkpointer=MagicMock())
        assert router._session_counters == {}

    def test_corrupt_db(self, mock_agent, tmp_path):
        """A corrupt file in place of checkpoints.db should not raise."""
        data = tmp_path / "data"
        data.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        db_path = data / "checkpoints.db"
        db_path.write_text("this is not a sqlite database")

        config = AppConfig(
            agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
            channels=ChannelsConfig(
                telegram=TelegramChannelConfig(token="t", trigger="@Bot")
            ),
        )
        # Should not raise — exception is caught internally
        router = MessageRouter(mock_agent, config, checkpointer=MagicMock())
        assert router._session_counters == {}


class TestLogMessage:
    def test_writes_jsonl(self, mock_agent, router_ext_config):
        router = MessageRouter(mock_agent, router_ext_config)
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="hello", is_private=True,
        )
        router._log_message("telegram_1", "user", "hello", msg)

        sessions_dir = Path(router_ext_config.agent.data_dir) / "sessions"
        log_path = sessions_dir / "telegram_1.jsonl"
        assert log_path.exists()

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["role"] == "user"
        assert entry["content"] == "hello"
        assert "ts" in entry
        assert entry["channel"] == "telegram"

    def test_creates_sessions_dir(self, mock_agent, tmp_path):
        """Sessions dir should be created if it doesn't exist."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        data = tmp_path / "data"
        data.mkdir()
        # Deliberately do NOT create data/sessions/

        config = AppConfig(
            agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
            channels=ChannelsConfig(
                telegram=TelegramChannelConfig(token="t", trigger="@Bot")
            ),
        )
        router = MessageRouter(mock_agent, config)
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="hi", is_private=True,
        )
        router._log_message("telegram_1", "user", "hi", msg)

        sessions_dir = data / "sessions"
        assert sessions_dir.exists()
        assert (sessions_dir / "telegram_1.jsonl").exists()

    def test_handles_write_error(self, mock_agent, router_ext_config):
        """IOError during write should be caught, not propagated."""
        router = MessageRouter(mock_agent, router_ext_config)
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="hi", is_private=True,
        )
        with patch("builtins.open", side_effect=IOError("disk full")):
            # Should not raise
            router._log_message("telegram_1", "user", "hi", msg)


class TestHandleMessageMultimodal:
    @pytest.mark.asyncio
    async def test_image_message(self, mock_agent, router_ext_config):
        """Image messages should send multimodal content with text and image_url blocks."""
        router = MessageRouter(mock_agent, router_ext_config)
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="What is this?", is_private=True,
            image_base64="abc123", image_mime_type="image/png",
        )
        result = await router.handle_message(msg, router_ext_config.channels.telegram)
        assert result is not None

        call_args = mock_agent.ainvoke.call_args
        content = call_args[0][0]["messages"][0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert "data:image/png;base64,abc123" in content[1]["image_url"]["url"]

    @pytest.mark.asyncio
    async def test_empty_text_with_image(self, mock_agent, router_ext_config):
        """Empty text with image should still be processed (not skipped)."""
        router = MessageRouter(mock_agent, router_ext_config)
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="", is_private=True,
            image_base64="abc123",
        )
        result = await router.handle_message(msg, router_ext_config.channels.telegram)
        assert result is not None
        mock_agent.ainvoke.assert_awaited_once()

        call_args = mock_agent.ainvoke.call_args
        content = call_args[0][0]["messages"][0]["content"]
        assert isinstance(content, list)
        assert content[1]["type"] == "image_url"


class TestShouldRespondEdge:
    def test_empty_after_trigger_strip(self, mock_agent, router_ext_config):
        """Trigger followed by only spaces should return True with empty cleaned text."""
        router = MessageRouter(mock_agent, router_ext_config)
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="@Bot  ", is_private=False,
        )
        should, cleaned = router.should_respond(msg, "@Bot")
        assert should is True
        assert cleaned == ""
