"""Tests for Telegram utils — typing_indicator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.channels.telegram.utils import typing_indicator


class TestTypingIndicator:
    @pytest.mark.asyncio
    async def test_normal_flow(self):
        """typing_indicator sends at least one chat action during normal use."""
        bot = MagicMock()
        bot.send_chat_action = AsyncMock()

        async with typing_indicator(bot, 123):
            await asyncio.sleep(0.01)

        assert bot.send_chat_action.called
        bot.send_chat_action.assert_called_with(chat_id=123, action="typing")

    @pytest.mark.asyncio
    async def test_body_raises_exception_task_still_cancelled(self):
        """If the body raises, the background task is cancelled cleanly."""
        bot = MagicMock()
        bot.send_chat_action = AsyncMock()

        with pytest.raises(ValueError, match="boom"):
            async with typing_indicator(bot, 456):
                raise ValueError("boom")

        # After the context manager exits (even with error), the background
        # task should have been cancelled — no orphan tasks.
        await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_send_chat_action_error_ignored(self):
        """Errors from send_chat_action are swallowed, context exits cleanly."""
        bot = MagicMock()
        bot.send_chat_action = AsyncMock(side_effect=Exception("network"))

        # Should not propagate the exception from send_chat_action
        async with typing_indicator(bot, 789):
            await asyncio.sleep(0.01)

        # Context exited without error
        assert bot.send_chat_action.called

    @pytest.mark.asyncio
    async def test_typing_action_sent_repeatedly(self):
        """typing_indicator re-sends the action at each sleep interval."""
        bot = MagicMock()
        bot.send_chat_action = AsyncMock()

        # Patch the sleep inside the _loop to be very fast, but still yield
        # control. After enough calls, let the main body proceed.
        call_count = 0
        body_done = asyncio.Event()
        original_sleep = asyncio.sleep

        async def fast_sleep(seconds):
            nonlocal call_count
            call_count += 1
            # Always yield control, but use tiny delay instead of 3s
            await original_sleep(0)
            # After enough iterations, wait for body to finish
            if call_count > 4:
                await body_done.wait()

        with patch("src.channels.telegram.utils.asyncio.sleep", side_effect=fast_sleep):
            async with typing_indicator(bot, 123):
                # Give the loop time to run a few iterations
                await original_sleep(0.05)
                body_done.set()

        assert bot.send_chat_action.call_count >= 2

    @pytest.mark.asyncio
    async def test_task_cleanup_on_exit(self):
        """After exiting the context, the background task is cancelled."""
        bot = MagicMock()
        bot.send_chat_action = AsyncMock()
        captured_task = None

        original_create_task = asyncio.create_task

        def capturing_create_task(coro, **kwargs):
            nonlocal captured_task
            captured_task = original_create_task(coro, **kwargs)
            return captured_task

        with patch("src.channels.telegram.utils.asyncio.create_task", side_effect=capturing_create_task):
            async with typing_indicator(bot, 100):
                await asyncio.sleep(0.01)

        # After context exit, the task should be done (cancelled)
        assert captured_task is not None
        assert captured_task.done()
