"""Tests for ClaudeCodeHandler — commands, callbacks, message processing."""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.channels.telegram.handlers.claude_code import (
    ClaudeCodeHandler,
    _cc_reply_keyboard,
    _cc_mode_buttons,
    _cc_status_buttons,
    _pagination_row,
    _relative_time,
    _render_cc_response,
    _MODEL_SHORTCUTS,
    CC_BTN_EXIT,
    CC_BTN_CONVERSATIONS,
    CC_PAGE_SIZE,
)
from src.gateway.bridges.claude_code.bridge import (
    CCResponse, UserSession, ConversationInfo, ProjectInfo,
)
from src.events import TextEvent, ToolCallEvent, ThinkingEvent


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.is_claude_code_mode = MagicMock(return_value=False)
    bridge.get_user_state = MagicMock(return_value=UserSession())
    bridge.list_projects = MagicMock(return_value=[])
    bridge.list_conversations = MagicMock(return_value=[])
    bridge.activate_session = MagicMock()
    bridge.exit_mode = MagicMock()
    bridge.set_model = MagicMock()
    bridge.set_effort = MagicMock()
    bridge.send_message = AsyncMock(
        return_value=CCResponse(events=[TextEvent(text="response")])
    )
    bridge.fork_session = AsyncMock(
        return_value=CCResponse(events=[TextEvent(text="forked")])
    )
    return bridge


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    app.bot.send_chat_action = AsyncMock()
    app.add_handler = MagicMock()
    return app


@pytest.fixture
def mock_send():
    return AsyncMock()


@pytest.fixture
def handler(mock_bridge, mock_app, mock_send):
    return ClaudeCodeHandler(mock_bridge, mock_app, mock_send)


# ---------------------------------------------------------------------------
# Helper to create Telegram Update / CallbackQuery mocks
# ---------------------------------------------------------------------------

def _make_update(text="/cc", chat_type="private", user_id=123, chat_id=456):
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.type = chat_type
    update.effective_chat.id = chat_id
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    return update


def _make_query(data, chat_id=456, user_id=123, message_id=1):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = chat_id
    query.message.message_id = message_id
    query.message.edit_text = AsyncMock()
    query.message.edit_reply_markup = AsyncMock()
    query.message.reply_text = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    return update, query


# ---------------------------------------------------------------------------
# TestHelperFunctions
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_cc_reply_keyboard(self):
        kb = _cc_reply_keyboard("my-project")
        # Returns a ReplyKeyboardMarkup; check the button layout
        from telegram import ReplyKeyboardMarkup
        assert isinstance(kb, ReplyKeyboardMarkup)
        # The keyboard should mention the project name in input_field_placeholder
        # and contain conversations + exit buttons
        # Access the internal keyboard data — telegram lib stores it in .keyboard
        rows = kb.keyboard
        labels = [btn.text for row in rows for btn in row]
        assert CC_BTN_CONVERSATIONS in labels
        assert CC_BTN_EXIT in labels

    def test_relative_time_just_now(self):
        assert _relative_time(datetime.now(tz=timezone.utc)) == "just now"

    def test_relative_time_minutes(self):
        result = _relative_time(datetime.now(tz=timezone.utc) - timedelta(minutes=5))
        assert "5m ago" in result

    def test_relative_time_hours(self):
        result = _relative_time(datetime.now(tz=timezone.utc) - timedelta(hours=3))
        assert "3h ago" in result

    def test_relative_time_days(self):
        result = _relative_time(datetime.now(tz=timezone.utc) - timedelta(days=2))
        assert "2d ago" in result

    def test_relative_time_none(self):
        assert _relative_time(None) == ""

    def test_relative_time_weeks(self):
        dt = datetime.now(tz=timezone.utc) - timedelta(weeks=2)
        result = _relative_time(dt)
        # Should fall back to YYYY-MM-DD format
        assert dt.strftime("%Y-%m-%d") == result


# ---------------------------------------------------------------------------
# TestPaginationRow
# ---------------------------------------------------------------------------

class TestPaginationRow:
    def test_first_page(self):
        row = _pagination_row("cc:projects", 0, 3)
        assert len(row) == 1
        assert "Next" in row[0].text

    def test_middle_page(self):
        row = _pagination_row("cc:projects", 1, 3)
        assert len(row) == 2
        texts = [btn.text for btn in row]
        assert any("Prev" in t for t in texts)
        assert any("Next" in t for t in texts)

    def test_last_page(self):
        row = _pagination_row("cc:projects", 2, 3)
        assert len(row) == 1
        assert "Prev" in row[0].text

    def test_single_page(self):
        row = _pagination_row("cc:projects", 0, 1)
        assert row == []


# ---------------------------------------------------------------------------
# TestMatchButton
# ---------------------------------------------------------------------------

class TestMatchButton:
    def test_exit_button(self, handler):
        assert handler.match_button(CC_BTN_EXIT) == "exit"

    def test_conversations_button(self, handler):
        assert handler.match_button(CC_BTN_CONVERSATIONS) == "conversations"

    def test_other_text(self, handler):
        assert handler.match_button("hello") is None


# ---------------------------------------------------------------------------
# TestCcCommands  (cc:help, cc:model, cc:effort, cc:compact, cc:clear, etc.)
# ---------------------------------------------------------------------------

class TestCcCommands:
    @pytest.mark.asyncio
    async def test_cc_help(self, handler, mock_send):
        await handler.process_message("u1", "cc:help", 123)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][1]
        assert "Claude Code Commands" in text

    @pytest.mark.asyncio
    async def test_cc_model_show(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            active_model="sonnet"
        )
        await handler.process_message("u1", "cc:model", 123)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][1]
        assert "sonnet" in text

    @pytest.mark.asyncio
    async def test_cc_model_set(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:model some-custom-model", 123)
        mock_bridge.set_model.assert_called_once_with("u1", "some-custom-model")
        text = mock_send.call_args[0][1]
        assert "some-custom-model" in text

    @pytest.mark.asyncio
    async def test_cc_effort_show(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            active_effort="high"
        )
        await handler.process_message("u1", "cc:effort", 123)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][1]
        assert "high" in text

    @pytest.mark.asyncio
    async def test_cc_effort_set_valid(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:effort low", 123)
        mock_bridge.set_effort.assert_called_once_with("u1", "low")
        text = mock_send.call_args[0][1]
        assert "low" in text

    @pytest.mark.asyncio
    async def test_cc_effort_set_invalid(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:effort invalid", 123)
        mock_bridge.set_effort.assert_not_called()
        text = mock_send.call_args[0][1]
        assert "Invalid effort" in text

    @pytest.mark.asyncio
    async def test_cc_compact_no_session(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession()
        await handler.process_message("u1", "cc:compact", 123)
        text = mock_send.call_args[0][1]
        assert "No active session" in text

    @pytest.mark.asyncio
    async def test_cc_compact_success(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            active_session_id="abc12345-session",
            active_project="proj",
            active_project_path="/tmp/proj",
        )
        mock_bridge.fork_session = AsyncMock(
            return_value=CCResponse(events=[TextEvent(text="forked")])
        )
        await handler.process_message("u1", "cc:compact", 123)
        mock_bridge.fork_session.assert_awaited_once_with("u1")

    @pytest.mark.asyncio
    async def test_cc_clear(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            active_project="proj",
            active_project_path="/tmp/proj",
            active_session_id="sess1",
        )
        await handler.process_message("u1", "cc:clear", 123)
        mock_bridge.activate_session.assert_called_once_with(
            "u1", "proj", "/tmp/proj", session_id=None
        )
        text = mock_send.call_args[0][1]
        assert "cleared" in text.lower()

    @pytest.mark.asyncio
    async def test_cc_unknown_command(self, handler, mock_send):
        await handler.process_message("u1", "cc:blah", 123)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][1]
        assert "Unknown command" in text

    @pytest.mark.asyncio
    async def test_cc_model_opus_shortcut(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:model opus", 123)
        mock_bridge.set_model.assert_called_once_with("u1", "claude-opus-4-6")
        text = mock_send.call_args[0][1]
        assert "claude-opus-4-6" in text

    @pytest.mark.asyncio
    async def test_cc_model_sonnet_shortcut(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:model sonnet", 123)
        mock_bridge.set_model.assert_called_once_with("u1", "claude-sonnet-4-6")

    @pytest.mark.asyncio
    async def test_cc_model_haiku_shortcut(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:model haiku", 123)
        mock_bridge.set_model.assert_called_once_with("u1", "claude-haiku-4-5-20251001")

    @pytest.mark.asyncio
    async def test_cc_model_full_id_passthrough(self, handler, mock_bridge, mock_send):
        await handler.process_message("u1", "cc:model claude-opus-4-6", 123)
        mock_bridge.set_model.assert_called_once_with("u1", "claude-opus-4-6")

    @pytest.mark.asyncio
    async def test_cc_cost_shows_config(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            active_model="opus",
            active_effort="high",
            active_session_id="abc12345",
            active_project_path="/tmp/my-proj",
        )
        await handler.process_message("u1", "cc:cost", 123)
        text = mock_send.call_args[0][1]
        assert "opus" in text
        assert "high" in text
        assert "Session Info" in text

    @pytest.mark.asyncio
    async def test_cc_resume_no_project(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession()
        await handler.process_message("u1", "cc:resume", 123)
        text = mock_send.call_args[0][1]
        assert "No active project" in text

    @pytest.mark.asyncio
    async def test_cc_resume_with_id(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            mode="claude_code",
            active_project="proj",
            active_project_path="/tmp/proj",
        )
        mock_bridge.list_conversations.return_value = [
            ConversationInfo(
                session_id="abc12345-full-id",
                first_message="hello world",
                timestamp=datetime.now(tz=timezone.utc),
                message_count=3,
            ),
        ]
        await handler.process_message("u1", "cc:resume abc1", 123)
        mock_bridge.activate_session.assert_called_once_with(
            "u1", "proj", "/tmp/proj", "abc12345-full-id",
        )
        text = mock_send.call_args[0][1]
        assert "Resumed" in text

    @pytest.mark.asyncio
    async def test_cc_resume_no_match(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            mode="claude_code",
            active_project="proj",
            active_project_path="/tmp/proj",
        )
        mock_bridge.list_conversations.return_value = []
        await handler.process_message("u1", "cc:resume xyz", 123)
        text = mock_send.call_args[0][1]
        assert "No session" in text

    @pytest.mark.asyncio
    async def test_cc_memory_no_session(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession()
        await handler.process_message("u1", "cc:memory", 123)
        text = mock_send.call_args[0][1]
        assert "No active session" in text

    @pytest.mark.asyncio
    async def test_cc_memory_success(self, handler, mock_bridge, mock_send):
        mock_bridge.get_user_state.return_value = UserSession(
            active_session_id="abc12345",
            active_project="proj",
            active_project_path="/tmp/proj",
        )
        mock_bridge.send_message = AsyncMock(
            return_value=CCResponse(events=[TextEvent(text="# Memory\nHello")])
        )
        await handler.process_message("u1", "cc:memory", 123)
        mock_bridge.send_message.assert_awaited_once()
        # Verify the message was sent (response rendered)
        assert mock_send.call_count >= 1

    @pytest.mark.asyncio
    async def test_cc_doctor_ok(self, handler, mock_bridge, mock_send):
        mock_bridge.check_available = AsyncMock(return_value=(True, "Claude Code v1.0"))
        await handler.process_message("u1", "cc:doctor", 123)
        text = mock_send.call_args[0][1]
        assert "OK" in text

    @pytest.mark.asyncio
    async def test_cc_doctor_fail(self, handler, mock_bridge, mock_send):
        mock_bridge.check_available = AsyncMock(return_value=(False, "Gateway unreachable"))
        await handler.process_message("u1", "cc:doctor", 123)
        text = mock_send.call_args[0][1]
        assert "FAIL" in text

    @pytest.mark.asyncio
    async def test_cc_project_no_args(self, handler, mock_bridge, mock_app):
        mock_bridge.list_projects.return_value = []
        await handler.process_message("u1", "cc:project", 123)
        # Should show project list via bot.send_message
        mock_app.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cc_project_match(self, handler, mock_bridge, mock_send):
        mock_bridge.list_projects.return_value = [
            ProjectInfo(
                encoded_name="enc1", real_path="/tmp/my-proj",
                display_name="my-proj", conversation_count=2,
                last_activity=datetime.now(tz=timezone.utc),
            ),
        ]
        await handler.process_message("u1", "cc:project my-proj", 123)
        mock_bridge.activate_session.assert_called_once_with(
            "u1", "enc1", "/tmp/my-proj", session_id=None)
        text = mock_send.call_args[0][1]
        assert "my-proj" in text

    @pytest.mark.asyncio
    async def test_cc_project_no_match(self, handler, mock_bridge, mock_send):
        mock_bridge.list_projects.return_value = []
        await handler.process_message("u1", "cc:project nonexistent", 123)
        text = mock_send.call_args[0][1]
        assert "No project" in text

    @pytest.mark.asyncio
    async def test_cc_help_includes_new_commands(self, handler, mock_send):
        await handler.process_message("u1", "cc:help", 123)
        text = mock_send.call_args[0][1]
        assert "cc:model" in text
        assert "opus" in text
        assert "cc:resume" in text
        assert "cc:memory" in text
        assert "cc:doctor" in text
        assert "cc:project" in text


# ---------------------------------------------------------------------------
# TestCmdCc  (/cc command via Telegram)
# ---------------------------------------------------------------------------

class TestCmdCc:
    @pytest.mark.asyncio
    async def test_group_chat_rejected(self, handler):
        update = _make_update(text="/cc", chat_type="group")
        await handler._cmd_cc(update, MagicMock())
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "only available in private" in text.lower()

    @pytest.mark.asyncio
    async def test_cc_exit_in_mode(self, handler, mock_bridge):
        mock_bridge.is_claude_code_mode.return_value = True
        update = _make_update(text="/cc exit")
        await handler._cmd_cc(update, MagicMock())
        mock_bridge.exit_mode.assert_called_once_with("123")
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Exited" in text

    @pytest.mark.asyncio
    async def test_cc_exit_not_in_mode(self, handler, mock_bridge):
        mock_bridge.is_claude_code_mode.return_value = False
        update = _make_update(text="/cc exit")
        await handler._cmd_cc(update, MagicMock())
        mock_bridge.exit_mode.assert_not_called()
        text = update.message.reply_text.call_args[0][0]
        assert "not in claude code mode" in text.lower()

    @pytest.mark.asyncio
    async def test_already_active_shows_status(self, handler, mock_bridge):
        mock_bridge.is_claude_code_mode.return_value = True
        mock_bridge.get_user_state.return_value = UserSession(
            active_project="proj",
            active_project_path="/tmp/proj",
            active_session_id="sess123",
        )
        update = _make_update(text="/cc")
        await handler._cmd_cc(update, MagicMock())
        update.message.reply_text.assert_awaited_once()
        call_kwargs = update.message.reply_text.call_args
        text = call_kwargs[0][0]
        assert "active" in text.lower()
        # Should have inline buttons (status buttons)
        assert call_kwargs[1]["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_normal_shows_project_list(self, handler, mock_bridge):
        mock_bridge.is_claude_code_mode.return_value = False
        update = _make_update(text="/cc")
        await handler._cmd_cc(update, MagicMock())
        # Should have called list_projects (via _show_project_list)
        mock_bridge.list_projects.assert_called_once()


# ---------------------------------------------------------------------------
# TestProjectList
# ---------------------------------------------------------------------------

class TestProjectList:
    @pytest.mark.asyncio
    async def test_empty_projects(self, handler, mock_bridge, mock_send, mock_app):
        mock_bridge.list_projects.return_value = []
        update = _make_update(text="/cc")
        await handler._show_project_list("u1", message=update.message)
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "No Claude Code projects found" in text

    @pytest.mark.asyncio
    async def test_with_projects(self, handler, mock_bridge, mock_app):
        now = datetime.now(tz=timezone.utc)
        mock_bridge.list_projects.return_value = [
            ProjectInfo(
                encoded_name="proj-a",
                real_path="/home/user/proj-a",
                display_name="proj-a",
                conversation_count=3,
                last_activity=now,
            ),
            ProjectInfo(
                encoded_name="proj-b",
                real_path="/home/user/proj-b",
                display_name="proj-b",
                conversation_count=1,
                last_activity=now - timedelta(hours=1),
            ),
        ]
        update = _make_update(text="/cc")
        await handler._show_project_list("u1", message=update.message)
        update.message.reply_text.assert_awaited_once()
        call_kwargs = update.message.reply_text.call_args
        markup = call_kwargs[1]["reply_markup"]
        from telegram import InlineKeyboardMarkup
        assert isinstance(markup, InlineKeyboardMarkup)
        # Should have 2 project buttons (one per project)
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        assert len(all_buttons) == 2
        assert "proj-a" in all_buttons[0].text
        assert "proj-b" in all_buttons[1].text

    @pytest.mark.asyncio
    async def test_pagination(self, handler, mock_bridge, mock_app):
        now = datetime.now(tz=timezone.utc)
        # Create more projects than CC_PAGE_SIZE
        projects = [
            ProjectInfo(
                encoded_name=f"proj-{i}",
                real_path=f"/home/user/proj-{i}",
                display_name=f"proj-{i}",
                conversation_count=1,
                last_activity=now - timedelta(hours=i),
            )
            for i in range(CC_PAGE_SIZE + 2)
        ]
        mock_bridge.list_projects.return_value = projects
        update = _make_update(text="/cc")
        await handler._show_project_list("u1", page=0, message=update.message)
        update.message.reply_text.assert_awaited_once()
        call_kwargs = update.message.reply_text.call_args
        markup = call_kwargs[1]["reply_markup"]
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        # Should have pagination buttons — look for "Next" label
        button_texts = [btn.text for btn in all_buttons]
        assert any("Next" in t for t in button_texts)


# ---------------------------------------------------------------------------
# TestConversationList
# ---------------------------------------------------------------------------

class TestConversationList:
    @pytest.mark.asyncio
    async def test_with_conversations(self, handler, mock_bridge, mock_app):
        now = datetime.now(tz=timezone.utc)
        project = ProjectInfo(
            encoded_name="proj-a",
            real_path="/home/user/proj-a",
            display_name="proj-a",
            conversation_count=2,
            last_activity=now,
        )
        handler._projects_cache["u1"] = [project]
        mock_bridge.list_conversations.return_value = [
            ConversationInfo(
                session_id="sess-1",
                first_message="Hello world",
                timestamp=now,
                message_count=5,
                git_branch="main",
            ),
            ConversationInfo(
                session_id="sess-2",
                first_message="Fix the bug",
                timestamp=now - timedelta(hours=1),
                message_count=3,
            ),
        ]
        await handler._show_conversation_list(
            user_id="u1", proj_idx=0, chat_id=456
        )
        mock_app.bot.send_message.assert_awaited_once()
        call_kwargs = mock_app.bot.send_message.call_args
        markup = call_kwargs[1]["reply_markup"]
        from telegram import InlineKeyboardMarkup
        assert isinstance(markup, InlineKeyboardMarkup)
        # 2 conv buttons + 1 row (New session + Projects) = at least 4 buttons
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]
        assert any("Hello world" in t for t in button_texts)
        assert any("Fix the bug" in t for t in button_texts)
        assert any("New session" in t for t in button_texts)

    @pytest.mark.asyncio
    async def test_cache_expired(self, handler, mock_bridge, mock_app):
        # proj_idx beyond cached list
        handler._projects_cache["u1"] = []
        await handler._show_conversation_list(
            user_id="u1", proj_idx=5, chat_id=456
        )
        mock_app.bot.send_message.assert_awaited_once()
        text = mock_app.bot.send_message.call_args[1]["text"]
        assert "cache expired" in text.lower()

    @pytest.mark.asyncio
    async def test_pagination(self, handler, mock_bridge, mock_app):
        now = datetime.now(tz=timezone.utc)
        project = ProjectInfo(
            encoded_name="proj-a",
            real_path="/home/user/proj-a",
            display_name="proj-a",
            conversation_count=CC_PAGE_SIZE + 2,
            last_activity=now,
        )
        handler._projects_cache["u1"] = [project]
        conversations = [
            ConversationInfo(
                session_id=f"sess-{i}",
                first_message=f"Message {i}",
                timestamp=now - timedelta(minutes=i),
                message_count=1,
            )
            for i in range(CC_PAGE_SIZE + 2)
        ]
        mock_bridge.list_conversations.return_value = conversations
        await handler._show_conversation_list(
            user_id="u1", proj_idx=0, chat_id=456
        )
        mock_app.bot.send_message.assert_awaited_once()
        call_kwargs = mock_app.bot.send_message.call_args
        markup = call_kwargs[1]["reply_markup"]
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]
        assert any("Next" in t for t in button_texts)


# ---------------------------------------------------------------------------
# TestCallbackRouter
# ---------------------------------------------------------------------------

class TestCallbackRouter:
    @pytest.mark.asyncio
    async def test_projects_page(self, handler, mock_bridge):
        mock_bridge.list_projects.return_value = []
        update, query = _make_query("cc:projects:0")
        await handler._handle_callback(update, MagicMock())
        query.answer.assert_awaited_once()
        # Should have called list_projects (inside _show_project_list)
        mock_bridge.list_projects.assert_called_once()

    @pytest.mark.asyncio
    async def test_proj_conversations(self, handler, mock_bridge):
        now = datetime.now(tz=timezone.utc)
        handler._projects_cache["123"] = [
            ProjectInfo(
                encoded_name="proj-a",
                real_path="/tmp/proj-a",
                display_name="proj-a",
                conversation_count=1,
                last_activity=now,
            ),
        ]
        mock_bridge.list_conversations.return_value = []
        update, query = _make_query("cc:proj:0")
        await handler._handle_callback(update, MagicMock())
        query.answer.assert_awaited_once()
        mock_bridge.list_conversations.assert_called_once_with("proj-a")

    @pytest.mark.asyncio
    async def test_conv_activate(self, handler, mock_bridge, mock_send):
        now = datetime.now(tz=timezone.utc)
        project = ProjectInfo(
            encoded_name="proj-a",
            real_path="/tmp/proj-a",
            display_name="proj-a",
            conversation_count=1,
            last_activity=now,
        )
        conv = ConversationInfo(
            session_id="sess-abc123",
            first_message="Hello",
            timestamp=now,
            message_count=2,
        )
        handler._projects_cache["123"] = [project]
        handler._conversations_cache["123"] = [conv]
        update, query = _make_query("cc:conv:0:0")
        await handler._handle_callback(update, MagicMock())
        query.answer.assert_awaited_once()
        mock_bridge.activate_session.assert_called_once_with(
            "123", "proj-a", "/tmp/proj-a", "sess-abc123"
        )

    @pytest.mark.asyncio
    async def test_new_conversation(self, handler, mock_bridge, mock_send):
        now = datetime.now(tz=timezone.utc)
        project = ProjectInfo(
            encoded_name="proj-a",
            real_path="/tmp/proj-a",
            display_name="proj-a",
            conversation_count=1,
            last_activity=now,
        )
        handler._projects_cache["123"] = [project]
        update, query = _make_query("cc:new:0")
        await handler._handle_callback(update, MagicMock())
        query.answer.assert_awaited_once()
        mock_bridge.activate_session.assert_called_once_with(
            "123", "proj-a", "/tmp/proj-a", session_id=None
        )

    @pytest.mark.asyncio
    async def test_exit_callback(self, handler, mock_bridge, mock_send):
        update, query = _make_query("cc:exit")
        await handler._handle_callback(update, MagicMock())
        query.answer.assert_awaited_once()
        mock_bridge.exit_mode.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_bad_callback_data(self, handler, mock_bridge):
        update, query = _make_query("cc:conv:invalid")
        await handler._handle_callback(update, MagicMock())
        # Should answer with "Something went wrong"
        query.answer.assert_awaited()
        answer_calls = query.answer.call_args_list
        assert any(
            "Something went wrong" in str(c) for c in answer_calls
        )


# ---------------------------------------------------------------------------
# TestProcessMessageLocked
# ---------------------------------------------------------------------------

class TestProcessMessageLocked:
    def _setup_active_session(self, mock_bridge, mock_app):
        """Common setup: user is in CC mode with an active project."""
        mock_bridge.is_claude_code_mode.return_value = True
        mock_bridge.get_user_state.return_value = UserSession(
            mode="claude_code",
            active_project="proj-a",
            active_project_path="/tmp/proj-a",
            active_session_id="sess1",
        )
        placeholder = MagicMock()
        placeholder.edit_text = AsyncMock()
        placeholder.delete = AsyncMock()
        mock_app.bot.send_message = AsyncMock(return_value=placeholder)
        return placeholder

    @pytest.mark.asyncio
    async def test_success_single_chunk(self, handler, mock_bridge, mock_app, mock_send):
        placeholder = self._setup_active_session(mock_bridge, mock_app)
        mock_bridge.send_message = AsyncMock(
            return_value=CCResponse(events=[TextEvent(text="short response")])
        )
        await handler._process_message_locked("u1", "hello", 456)
        # Single chunk: placeholder should be edited (not deleted)
        placeholder.edit_text.assert_awaited_once()
        call_args = placeholder.edit_text.call_args
        assert "short response" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_success_multi_chunk(self, handler, mock_bridge, mock_app, mock_send):
        placeholder = self._setup_active_session(mock_bridge, mock_app)
        # Build a response longer than TELEGRAM_MAX_MESSAGE_LEN
        long_text = "x" * 5000
        mock_bridge.send_message = AsyncMock(
            return_value=CCResponse(events=[TextEvent(text=long_text)])
        )
        await handler._process_message_locked("u1", "hello", 456)
        # Multi-chunk: placeholder should be deleted and send_fn used
        placeholder.delete.assert_awaited_once()
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_timeout(self, handler, mock_bridge, mock_app, mock_send):
        placeholder = self._setup_active_session(mock_bridge, mock_app)
        mock_bridge.send_message = AsyncMock(side_effect=TimeoutError)
        await handler._process_message_locked("u1", "hello", 456)
        # Timeout: placeholder should be edited with timeout text
        placeholder.edit_text.assert_awaited_once()
        text = placeholder.edit_text.call_args[0][0]
        assert "taking longer" in text.lower()

    @pytest.mark.asyncio
    async def test_error(self, handler, mock_bridge, mock_app, mock_send):
        placeholder = self._setup_active_session(mock_bridge, mock_app)
        mock_bridge.send_message = AsyncMock(
            side_effect=Exception("boom")
        )
        await handler._process_message_locked("u1", "hello", 456)
        # Error: placeholder deleted, error sent via send_fn
        placeholder.delete.assert_awaited_once()
        mock_send.assert_called_once()
        text = mock_send.call_args[0][1]
        assert "error" in text.lower()
