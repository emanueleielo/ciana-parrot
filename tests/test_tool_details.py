"""Tests for ToolDetailsManager — store, expand/collapse, callback handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import BadRequest

from src.channels.telegram.tool_details import ToolDetailsManager


class TestStore:
    def test_returns_incremental_keys(self):
        mgr = ToolDetailsManager("td")
        k1 = mgr.store(["item1"])
        k2 = mgr.store(["item2"])
        assert k1 == "1"
        assert k2 == "2"

    def test_eviction_beyond_max_stored(self):
        mgr = ToolDetailsManager("td", max_stored=3)
        keys = [mgr.store([f"item{i}"]) for i in range(5)]
        # Only the last 3 should remain
        assert mgr._details.get(keys[0]) is None
        assert mgr._details.get(keys[1]) is None
        assert mgr._details.get(keys[2]) is not None
        assert mgr._details.get(keys[3]) is not None
        assert mgr._details.get(keys[4]) is not None

    def test_stored_items_are_accessible(self):
        mgr = ToolDetailsManager("td")
        key = mgr.store(["<b>detail</b>", "plain text"])
        entry = mgr._details[key]
        assert entry["items"] == ["<b>detail</b>", "plain text"]
        assert entry["msg_ids"] == []


class TestButtons:
    def test_expand_button_callback_data(self):
        mgr = ToolDetailsManager("td")
        markup = mgr.expand_button("42")
        btn = markup.inline_keyboard[0][0]
        assert btn.callback_data == "td:tools:42"
        assert "Tool details" in btn.text

    def test_collapse_button_callback_data(self):
        mgr = ToolDetailsManager("cc")
        markup = mgr.collapse_button("7")
        btn = markup.inline_keyboard[0][0]
        assert btn.callback_data == "cc:tclose:7"
        assert "Hide" in btn.text

    def test_prefix_isolation(self):
        mgr_td = ToolDetailsManager("td")
        mgr_cc = ToolDetailsManager("cc")
        btn_td = mgr_td.expand_button("1").inline_keyboard[0][0]
        btn_cc = mgr_cc.expand_button("1").inline_keyboard[0][0]
        assert btn_td.callback_data.startswith("td:")
        assert btn_cc.callback_data.startswith("cc:")


class TestHandleCallback:
    def _make_query(self, data: str, chat_id: int = 123):
        query = AsyncMock()
        query.data = data
        query.message = MagicMock()
        query.message.chat_id = chat_id
        query.message.edit_reply_markup = AsyncMock()
        return query

    @pytest.mark.asyncio
    async def test_non_matching_prefix_returns_false(self):
        mgr = ToolDetailsManager("td")
        query = self._make_query("cc:tools:1")
        bot = AsyncMock()
        result = await mgr.handle_callback(query, bot)
        assert result is False
        query.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_expand_sends_messages_and_edits_button(self):
        mgr = ToolDetailsManager("td")
        key = mgr.store(["<b>Result</b>", "Plain text"])

        sent_msg = MagicMock()
        sent_msg.message_id = 999

        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value=sent_msg)

        query = self._make_query(f"td:tools:{key}")

        result = await mgr.handle_callback(query, bot)
        assert result is True
        query.answer.assert_called_once()
        assert bot.send_message.call_count == 2

        # Verify send_message calls used HTML parse mode
        for call in bot.send_message.call_args_list:
            assert call.kwargs.get("chat_id") == 123
            assert call.kwargs.get("disable_notification") is True

        # Verify button was changed to collapse
        query.message.edit_reply_markup.assert_called_once()
        markup = query.message.edit_reply_markup.call_args.kwargs["reply_markup"]
        btn = markup.inline_keyboard[0][0]
        assert "tclose" in btn.callback_data
        assert "Hide" in btn.text

        # msg_ids should be stored for collapse
        assert mgr._details[key]["msg_ids"] == [999, 999]

    @pytest.mark.asyncio
    async def test_expand_expired_key(self):
        mgr = ToolDetailsManager("td")
        query = self._make_query("td:tools:999")
        bot = AsyncMock()

        result = await mgr.handle_callback(query, bot)
        assert result is True
        query.answer.assert_called_once_with("Details no longer available")
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_collapse_deletes_messages_and_restores_button(self):
        mgr = ToolDetailsManager("cc")
        key = mgr.store(["item"])
        mgr._details[key]["msg_ids"] = [100, 101]

        bot = AsyncMock()
        query = self._make_query(f"cc:tclose:{key}")

        result = await mgr.handle_callback(query, bot)
        assert result is True
        query.answer.assert_called_once()

        # Verify delete_message was called for each stored msg_id
        assert bot.delete_message.call_count == 2
        deleted_ids = [
            call.kwargs["message_id"]
            for call in bot.delete_message.call_args_list
        ]
        assert sorted(deleted_ids) == [100, 101]

        # msg_ids should be cleared
        assert mgr._details[key]["msg_ids"] == []

        # Button should be restored to expand
        query.message.edit_reply_markup.assert_called_once()
        markup = query.message.edit_reply_markup.call_args.kwargs["reply_markup"]
        btn = markup.inline_keyboard[0][0]
        assert "tools" in btn.callback_data
        assert "Tool details" in btn.text

    @pytest.mark.asyncio
    async def test_collapse_with_no_msg_ids(self):
        mgr = ToolDetailsManager("td")
        key = mgr.store(["item"])
        # msg_ids is empty (never expanded)
        query = self._make_query(f"td:tclose:{key}")
        bot = AsyncMock()

        result = await mgr.handle_callback(query, bot)
        assert result is True
        query.answer.assert_called_once()
        bot.delete_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_expand_fallback_plaintext_on_bad_request(self):
        mgr = ToolDetailsManager("td")
        key = mgr.store(["<b>bad html</b>"])

        sent_msg = MagicMock()
        sent_msg.message_id = 500

        bot = AsyncMock()
        # First call with HTML raises BadRequest, second without HTML succeeds
        bot.send_message = AsyncMock(
            side_effect=[BadRequest("parse error"), sent_msg]
        )

        query = self._make_query(f"td:tools:{key}")
        result = await mgr.handle_callback(query, bot)
        assert result is True

        # Should have been called twice: once with HTML, once plaintext fallback
        assert bot.send_message.call_count == 2
        first_call = bot.send_message.call_args_list[0]
        assert first_call.kwargs.get("parse_mode") == "HTML"
        second_call = bot.send_message.call_args_list[1]
        assert "parse_mode" not in second_call.kwargs

        assert mgr._details[key]["msg_ids"] == [500]

    @pytest.mark.asyncio
    async def test_expand_total_failure_logs_warning(self):
        mgr = ToolDetailsManager("td")
        key = mgr.store(["<b>bad</b>"])

        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=BadRequest("fail"))

        query = self._make_query(f"td:tools:{key}")
        result = await mgr.handle_callback(query, bot)
        assert result is True
        # Both HTML and plaintext attempts fail
        assert bot.send_message.call_count == 2
        assert mgr._details[key]["msg_ids"] == []
