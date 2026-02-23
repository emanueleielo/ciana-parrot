"""Tests for src.router — should_respond, is_user_allowed, get_thread_id, handle_message."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.channels.base import IncomingMessage
from src.config import AppConfig, AgentConfig, ChannelsConfig, TelegramChannelConfig
from src.router import MessageRouter


@pytest.fixture
def router_config(tmp_path) -> AppConfig:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "sessions").mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return AppConfig(
        agent=AgentConfig(workspace=str(ws), data_dir=str(data)),
        channels=ChannelsConfig(
            telegram=TelegramChannelConfig(
                enabled=True,
                token="tok",
                trigger="@Bot",
                allowed_users=["user1", "user2"],
            )
        ),
    )


@pytest.fixture
def router(mock_agent, router_config) -> MessageRouter:
    return MessageRouter(mock_agent, router_config)


class TestShouldRespond:
    def test_private_always(self, router):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="hello", is_private=True,
        )
        should, text = router.should_respond(msg, "@Bot")
        assert should is True
        assert text == "hello"

    def test_group_with_trigger(self, router):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="@Bot what is the weather?", is_private=False,
        )
        should, text = router.should_respond(msg, "@Bot")
        assert should is True
        assert text == "what is the weather?"

    def test_group_without_trigger(self, router):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="hello everyone", is_private=False,
        )
        should, text = router.should_respond(msg, "@Bot")
        assert should is False

    def test_trigger_case_insensitive(self, router):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="@bot hello", is_private=False,
        )
        should, text = router.should_respond(msg, "@Bot")
        assert should is True
        assert text == "hello"

    def test_whitespace_stripped(self, router):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="u",
            user_name="Test", text="  @Bot  hi  ", is_private=False,
        )
        should, text = router.should_respond(msg, "@Bot")
        assert should is True
        assert text == "hi"


class TestIsUserAllowed:
    def test_allowed_user(self, router):
        assert router.is_user_allowed("telegram", "user1") is True

    def test_disallowed_user(self, router):
        assert router.is_user_allowed("telegram", "stranger") is False

    def test_unknown_channel_allows_all(self, router):
        assert router.is_user_allowed("slack", "anyone") is True

    def test_empty_allowlist(self, mock_agent, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        config = AppConfig(
            agent=AgentConfig(workspace=str(ws)),
            channels=ChannelsConfig(
                telegram=TelegramChannelConfig(allowed_users=[])
            ),
        )
        r = MessageRouter(mock_agent, config)
        assert r.is_user_allowed("telegram", "anyone") is True


class TestGetThreadId:
    def test_basic(self, router):
        tid = router.get_thread_id("telegram", "123")
        assert tid == "telegram_123"

    def test_after_reset(self, router):
        router.reset_session("telegram", "123")
        tid = router.get_thread_id("telegram", "123")
        assert tid == "telegram_123_s1"

    def test_multiple_resets(self, router):
        router.reset_session("telegram", "456")
        router.reset_session("telegram", "456")
        tid = router.get_thread_id("telegram", "456")
        assert tid == "telegram_456_s2"


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_unauthorized_user(self, router, router_config):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="stranger",
            user_name="Bad", text="hello", is_private=True,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is None

    @pytest.mark.asyncio
    async def test_reset_session(self, router, router_config):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="", is_private=True, reset_session=True,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is None
        # Session should be incremented
        assert router.get_thread_id("telegram", "1") == "telegram_1_s1"

    @pytest.mark.asyncio
    async def test_no_trigger_in_group(self, router, router_config):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="hello", is_private=False,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_text_after_trigger(self, router, router_config):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="@Bot", is_private=False,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_message(self, router, mock_agent, router_config):
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="hello", is_private=True,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is not None
        assert result.text == "Test response"
        mock_agent.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_agent_error(self, router, mock_agent, router_config):
        mock_agent.ainvoke.side_effect = RuntimeError("boom")
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="hello", is_private=True,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is not None
        assert "error" in result.text.lower()

    @pytest.mark.asyncio
    async def test_image_with_caption(self, router, mock_agent, router_config):
        """Photo with caption should send multimodal content to agent."""
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="What is this?", is_private=True,
            image_base64="dGVzdA==",
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is not None
        # Verify multimodal content was sent
        call_args = mock_agent.ainvoke.call_args
        content = call_args[0][0]["messages"][0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert "data:image/jpeg;base64,dGVzdA==" in content[1]["image_url"]["url"]

    @pytest.mark.asyncio
    async def test_image_without_caption(self, router, mock_agent, router_config):
        """Photo without caption in private chat should still be processed."""
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="", is_private=True,
            image_base64="dGVzdA==",
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is not None
        call_args = mock_agent.ainvoke.call_args
        content = call_args[0][0]["messages"][0]["content"]
        assert isinstance(content, list)
        assert content[1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_group_trigger_with_image(self, router, mock_agent, router_config):
        """Image with trigger in group chat should respond."""
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="@Bot describe this", is_private=False,
            image_base64="dGVzdA==",
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is not None
        call_args = mock_agent.ainvoke.call_args
        content = call_args[0][0]["messages"][0]["content"]
        assert isinstance(content, list)

    @pytest.mark.asyncio
    async def test_text_message_stays_string(self, router, mock_agent, router_config):
        """Regular text message content should remain a plain string, not a list."""
        msg = IncomingMessage(
            channel="telegram", chat_id="1", user_id="user1",
            user_name="Test", text="hello", is_private=True,
        )
        result = await router.handle_message(msg, router_config.channels.telegram)
        assert result is not None
        call_args = mock_agent.ainvoke.call_args
        content = call_args[0][0]["messages"][0]["content"]
        assert isinstance(content, str)
