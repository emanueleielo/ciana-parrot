"""Tests for TelegramChannel — send, commands, message handling, media helpers."""

import asyncio
import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, call

import pytest
import telegram.error

from src.channels.telegram.channel import TelegramChannel, ModeHandler
from src.channels.base import IncomingMessage, SendResult
from src.config import TelegramChannelConfig
from src.agent_response import AgentResponse
from src.events import TextEvent, ToolCallEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def channel_config():
    return TelegramChannelConfig(enabled=True, token="test-token", trigger="@Bot")


@pytest.fixture
def channel(channel_config):
    ch = TelegramChannel(channel_config)
    # Create mock app and bot
    ch._app = MagicMock()
    ch._app.bot = AsyncMock()
    ch._app.bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
    ch._app.bot.send_document = AsyncMock()
    return ch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(text="/start", chat_type="private", user_id=123, chat_id=456):
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.type = chat_type
    update.effective_chat.id = chat_id
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "TestUser"
    return update


def _make_message_update(text="Hello", chat_type="private", update_id=1):
    update = MagicMock()
    update.update_id = update_id
    update.message = MagicMock()
    update.message.text = text
    update.message.voice = None
    update.message.audio = None
    update.message.photo = None
    update.message.message_id = 100
    update.message.caption = None
    update.effective_chat = MagicMock()
    update.effective_chat.type = chat_type
    update.effective_chat.id = 456
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "TestUser"
    return update


# ---------------------------------------------------------------------------
# TestModeHandlerRegistration
# ---------------------------------------------------------------------------

class TestModeHandlerRegistration:
    def test_register_mode_handler_stores_factory(self, channel):
        """register_mode_handler appends the factory to _mode_handler_factories."""
        factory = MagicMock()
        channel.register_mode_handler(factory)
        assert factory in channel._mode_handler_factories

    @pytest.mark.asyncio
    async def test_tracked_task(self, channel):
        """_tracked_task adds the task to _active_tasks and removes it on completion."""
        completed = asyncio.Event()

        async def quick_coro():
            completed.set()

        task = channel._tracked_task(quick_coro())
        assert task in channel._active_tasks

        # Let the task complete
        await asyncio.sleep(0.05)
        assert task not in channel._active_tasks
        assert completed.is_set()


# ---------------------------------------------------------------------------
# TestSend
# ---------------------------------------------------------------------------

class TestSend:
    @pytest.mark.asyncio
    async def test_single_chunk(self, channel):
        """Short message is sent as a single chunk with HTML parse mode."""
        result = await channel.send("123", "Hello")
        channel._app.bot.send_message.assert_called_once()
        kwargs = channel._app.bot.send_message.call_args[1]
        assert kwargs["chat_id"] == 123
        assert kwargs["parse_mode"] == "HTML"
        assert "Hello" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_multi_chunk(self, channel):
        """Text longer than TELEGRAM_MAX_MESSAGE_LEN is split into multiple chunks."""
        long_text = "A" * 5000
        await channel.send("123", long_text)
        assert channel._app.bot.send_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_with_reply_to(self, channel):
        """reply_to_message_id is passed on the first chunk only."""
        await channel.send("123", "Hi", reply_to_message_id="99")
        kwargs = channel._app.bot.send_message.call_args_list[0][1]
        assert kwargs["reply_to_message_id"] == 99

    @pytest.mark.asyncio
    async def test_with_reply_markup(self, channel):
        """reply_markup is attached to the last chunk."""
        markup = MagicMock()
        await channel.send("123", "Hi", reply_markup=markup)
        # For a single-chunk message, last chunk == first chunk
        kwargs = channel._app.bot.send_message.call_args_list[-1][1]
        assert kwargs["reply_markup"] is markup

    @pytest.mark.asyncio
    async def test_bad_request_fallback(self, channel):
        """On BadRequest, retry without parse_mode (plain text fallback)."""
        success_msg = MagicMock(message_id=55)
        channel._app.bot.send_message = AsyncMock(
            side_effect=[
                telegram.error.BadRequest("parse error"),
                success_msg,
            ]
        )
        result = await channel.send("123", "Hello <b>world</b>")
        assert channel._app.bot.send_message.call_count == 2
        # Second call should not have parse_mode
        retry_kwargs = channel._app.bot.send_message.call_args_list[1][1]
        assert "parse_mode" not in retry_kwargs

    @pytest.mark.asyncio
    async def test_empty_text_returns_none(self, channel):
        """Sending empty text returns None without calling bot."""
        result = await channel.send("123", "")
        assert result is None
        channel._app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_send_result(self, channel):
        """send() returns a SendResult with the message_id."""
        result = await channel.send("123", "Hi")
        assert isinstance(result, SendResult)
        assert result.message_id == "42"


# ---------------------------------------------------------------------------
# TestSendFile
# ---------------------------------------------------------------------------

class TestSendFile:
    @pytest.mark.asyncio
    async def test_file_exists(self, channel, tmp_path):
        """Existing file is sent via bot.send_document."""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        await channel.send_file("123", str(f))
        channel._app.bot.send_document.assert_called_once()
        kwargs = channel._app.bot.send_document.call_args[1]
        assert kwargs["chat_id"] == 123

    @pytest.mark.asyncio
    async def test_file_not_found(self, channel):
        """Non-existent file sends a 'File not found' message."""
        await channel.send_file("123", "/nonexistent/file.txt")
        channel._app.bot.send_message.assert_called()
        text_arg = channel._app.bot.send_message.call_args[1]["text"]
        assert "File not found" in text_arg


# ---------------------------------------------------------------------------
# TestCommandHandlers
# ---------------------------------------------------------------------------

class TestCommandHandlers:
    @pytest.mark.asyncio
    async def test_cmd_start(self, channel):
        """_cmd_start replies with a welcome message."""
        update = _make_update(text="/start")
        ctx = MagicMock()
        await channel._cmd_start(update, ctx)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Ciana" in text

    @pytest.mark.asyncio
    async def test_cmd_help(self, channel):
        """_cmd_help replies with HTML-formatted commands."""
        update = _make_update(text="/help")
        ctx = MagicMock()
        await channel._cmd_help(update, ctx)
        update.message.reply_text.assert_called_once()
        kwargs = update.message.reply_text.call_args
        text = kwargs[0][0]
        assert "/help" in text
        assert kwargs[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_cmd_new_sends_reset(self, channel):
        """_cmd_new invokes the callback with a reset_session=True message."""
        channel._callback = AsyncMock()
        update = _make_update(text="/new")
        ctx = MagicMock()
        await channel._cmd_new(update, ctx)
        channel._callback.assert_called_once()
        msg = channel._callback.call_args[0][0]
        assert isinstance(msg, IncomingMessage)
        assert msg.reset_session is True

    @pytest.mark.asyncio
    async def test_cmd_status(self, channel):
        """_cmd_status replies with a status message."""
        update = _make_update(text="/status")
        ctx = MagicMock()
        await channel._cmd_status(update, ctx)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "running" in text.lower() or "up" in text.lower()


# ---------------------------------------------------------------------------
# TestHandleMessage
# ---------------------------------------------------------------------------

class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_text_message_creates_incoming(self, channel):
        """A normal text message triggers the callback via _process_message."""
        channel._callback = AsyncMock(return_value=AgentResponse(
            text="Reply", events=[TextEvent(text="Reply")]
        ))
        update = _make_message_update(text="Hello")
        ctx = MagicMock()

        await channel._handle_message(update, ctx)
        # _handle_message spawns a background task; yield control
        await asyncio.sleep(0.15)

        channel._callback.assert_called_once()
        msg = channel._callback.call_args[0][0]
        assert isinstance(msg, IncomingMessage)
        assert msg.text == "Hello"

    @pytest.mark.asyncio
    async def test_dedup_skips_same_update_id(self, channel):
        """Duplicate update_id is skipped."""
        channel._callback = AsyncMock(return_value=AgentResponse(
            text="Reply", events=[TextEvent(text="Reply")]
        ))
        update = _make_message_update(text="Hello", update_id=42)
        ctx = MagicMock()

        await channel._handle_message(update, ctx)
        await channel._handle_message(update, ctx)
        await asyncio.sleep(0.15)

        assert channel._callback.call_count == 1

    @pytest.mark.asyncio
    async def test_no_callback_returns(self, channel):
        """Without a registered callback, _handle_message returns without error."""
        channel._callback = None
        update = _make_message_update(text="Hello")
        ctx = MagicMock()

        # Should not raise
        await channel._handle_message(update, ctx)

    @pytest.mark.asyncio
    async def test_unsupported_content_returns(self, channel):
        """Message with no text, voice, or photo is ignored."""
        channel._callback = AsyncMock()
        update = _make_message_update()
        update.message.text = None
        update.message.voice = None
        update.message.audio = None
        update.message.photo = None
        ctx = MagicMock()

        await channel._handle_message(update, ctx)
        await asyncio.sleep(0.05)

        channel._callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_mode_handler_exit_button(self, channel):
        """Exit button text triggers exit_with_keyboard_remove on the mode handler."""
        channel._callback = AsyncMock()
        handler = MagicMock()
        handler.match_button = MagicMock(return_value="exit")
        handler.exit_with_keyboard_remove = AsyncMock()
        handler.is_active = MagicMock(return_value=False)
        channel._mode_handlers = [handler]

        update = _make_message_update(text="\u2190 Exit CC", chat_type="private")
        ctx = MagicMock()

        await channel._handle_message(update, ctx)
        handler.exit_with_keyboard_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode_handler_conversations_button(self, channel):
        """Conversations button triggers show_menu on the mode handler."""
        channel._callback = AsyncMock()
        handler = MagicMock()
        handler.match_button = MagicMock(return_value="conversations")
        handler.show_menu = AsyncMock()
        handler.is_active = MagicMock(return_value=False)
        channel._mode_handlers = [handler]

        update = _make_message_update(text="\U0001f4cb Conversations", chat_type="private")
        ctx = MagicMock()

        await channel._handle_message(update, ctx)
        handler.show_menu.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode_intercept_active_text(self, channel):
        """Active mode handler intercepts text and calls process_message."""
        channel._callback = AsyncMock()
        handler = MagicMock()
        handler.match_button = MagicMock(return_value=None)
        handler.is_active = MagicMock(return_value=True)
        handler.process_message = AsyncMock()
        channel._mode_handlers = [handler]

        update = _make_message_update(text="Do something", chat_type="private")
        ctx = MagicMock()

        await channel._handle_message(update, ctx)
        await asyncio.sleep(0.05)

        handler.process_message.assert_called_once()
        args = handler.process_message.call_args[0]
        assert args[1] == "Do something"  # text argument

    @pytest.mark.asyncio
    async def test_mode_intercept_photo_rejected(self, channel):
        """Active mode handler rejects photos with a 'not supported' message."""
        channel._callback = AsyncMock()
        handler = MagicMock()
        handler.match_button = MagicMock(return_value=None)
        handler.is_active = MagicMock(return_value=True)
        channel._mode_handlers = [handler]

        update = _make_message_update(chat_type="private")
        update.message.text = None
        update.message.photo = [MagicMock()]  # has photo
        ctx = MagicMock()

        await channel._handle_message(update, ctx)

        # Should send a "not supported" message
        channel._app.bot.send_message.assert_called()
        text_arg = channel._app.bot.send_message.call_args[1]["text"]
        assert "not supported" in text_arg.lower()

    @pytest.mark.asyncio
    async def test_no_message_returns(self, channel):
        """update.message == None returns without error."""
        update = MagicMock()
        update.message = None
        ctx = MagicMock()

        # Should not raise
        await channel._handle_message(update, ctx)

    @pytest.mark.asyncio
    async def test_voice_message_transcribed(self, channel):
        """Voice message is transcribed and sent to callback."""
        channel._callback = AsyncMock(return_value=AgentResponse(
            text="Voice reply", events=[TextEvent(text="Voice reply")]
        ))

        file_mock = AsyncMock()
        buf = BytesIO(b"fake-audio-data")
        file_mock.download_to_memory = AsyncMock(side_effect=lambda b: b.write(buf.getvalue()))

        voice_mock = MagicMock()
        voice_mock.get_file = AsyncMock(return_value=file_mock)

        update = _make_message_update(chat_type="private", update_id=999)
        update.message.text = None
        update.message.voice = voice_mock
        update.message.audio = None
        update.message.photo = None
        ctx = MagicMock()

        with patch("src.channels.telegram.channel.transcription_configured", return_value=True), \
             patch("src.channels.telegram.channel.transcribe", new_callable=AsyncMock, return_value="transcribed text"):
            await channel._handle_message(update, ctx)
            await asyncio.sleep(0.15)

        channel._callback.assert_called_once()
        msg = channel._callback.call_args[0][0]
        assert msg.text == "transcribed text"


# ---------------------------------------------------------------------------
# TestProcessMessage
# ---------------------------------------------------------------------------

class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_success_flow(self, channel):
        """Successful callback renders and sends the response."""
        channel._callback = AsyncMock(return_value=AgentResponse(
            text="Hi there", events=[TextEvent(text="Hi there")]
        ))
        msg = IncomingMessage(
            channel="telegram", chat_id="456", user_id="123",
            user_name="TestUser", text="Hello", is_private=True,
            message_id="100",
        )

        await channel._process_message(msg, 456)

        channel._app.bot.send_message.assert_called()
        text_arg = channel._app.bot.send_message.call_args[1]["text"]
        assert "Hi there" in text_arg

    @pytest.mark.asyncio
    async def test_no_response(self, channel):
        """If callback returns None, send is not called."""
        channel._callback = AsyncMock(return_value=None)
        msg = IncomingMessage(
            channel="telegram", chat_id="456", user_id="123",
            user_name="TestUser", text="Hello", is_private=True,
            message_id="100",
        )

        await channel._process_message(msg, 456)

        channel._app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_sends_error_message(self, channel):
        """If callback raises, an error message is sent."""
        channel._callback = AsyncMock(side_effect=RuntimeError("agent crash"))
        msg = IncomingMessage(
            channel="telegram", chat_id="456", user_id="123",
            user_name="TestUser", text="Hello", is_private=True,
            message_id="100",
        )

        await channel._process_message(msg, 456)

        channel._app.bot.send_message.assert_called()
        text_arg = channel._app.bot.send_message.call_args[1]["text"]
        assert "Error" in text_arg or "error" in text_arg

    @pytest.mark.asyncio
    async def test_events_with_tool_details(self, channel):
        """Response with ToolCallEvent gets an inline markup button."""
        channel._callback = AsyncMock(return_value=AgentResponse(
            text="Done",
            events=[
                ToolCallEvent(tool_id="t1", name="Bash", input_summary="ls",
                              result_text="file.txt", is_error=False),
                TextEvent(text="Done"),
            ],
        ))
        msg = IncomingMessage(
            channel="telegram", chat_id="456", user_id="123",
            user_name="TestUser", text="list files", is_private=True,
            message_id="100",
        )

        await channel._process_message(msg, 456)

        channel._app.bot.send_message.assert_called()
        kwargs = channel._app.bot.send_message.call_args[1]
        # The last call should have a reply_markup (inline keyboard for tool details)
        assert kwargs.get("reply_markup") is not None


# ---------------------------------------------------------------------------
# TestMediaHelpers
# ---------------------------------------------------------------------------

class TestMediaHelpers:
    @pytest.mark.asyncio
    async def test_transcribe_voice_success(self, channel):
        """Successful voice transcription returns the transcribed text."""
        file_mock = AsyncMock()
        buf_data = b"fake-audio"
        file_mock.download_to_memory = AsyncMock(
            side_effect=lambda b: b.write(buf_data)
        )

        voice_mock = MagicMock()
        voice_mock.get_file = AsyncMock(return_value=file_mock)

        message = MagicMock()
        message.voice = voice_mock
        message.audio = None

        with patch("src.channels.telegram.channel.transcription_configured", return_value=True), \
             patch("src.channels.telegram.channel.transcribe", new_callable=AsyncMock, return_value="hello world"):
            result = await channel._transcribe_voice(message, "456")

        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_transcribe_not_configured(self, channel):
        """When transcription is not configured, returns None and sends error."""
        message = MagicMock()

        with patch("src.channels.telegram.channel.transcription_configured", return_value=False):
            result = await channel._transcribe_voice(message, "456")

        assert result is None
        channel._app.bot.send_message.assert_called()
        text_arg = channel._app.bot.send_message.call_args[1]["text"]
        assert "not configured" in text_arg.lower() or "not supported" in text_arg.lower()

    @pytest.mark.asyncio
    async def test_download_photo_success(self, channel):
        """Successful photo download returns a base64 string."""
        file_mock = AsyncMock()
        photo_data = b"\x89PNG\r\n\x1a\n"  # fake PNG header
        file_mock.download_to_memory = AsyncMock(
            side_effect=lambda b: b.write(photo_data)
        )

        photo_size = MagicMock()
        photo_size.get_file = AsyncMock(return_value=file_mock)

        message = MagicMock()
        message.photo = [MagicMock(), photo_size]  # [-1] gives highest res

        result = await channel._download_photo_base64(message, "456")

        assert result is not None
        # Verify it's valid base64
        decoded = base64.b64decode(result)
        assert decoded == photo_data

    @pytest.mark.asyncio
    async def test_download_photo_empty(self, channel):
        """Empty photo download returns None and sends error."""
        file_mock = AsyncMock()
        # download_to_memory writes nothing (empty bytes)
        file_mock.download_to_memory = AsyncMock(side_effect=lambda b: None)

        photo_size = MagicMock()
        photo_size.get_file = AsyncMock(return_value=file_mock)

        message = MagicMock()
        message.photo = [photo_size]

        result = await channel._download_photo_base64(message, "456")

        assert result is None
        channel._app.bot.send_message.assert_called()
        text_arg = channel._app.bot.send_message.call_args[1]["text"]
        assert "empty" in text_arg.lower() or "failed" in text_arg.lower()
