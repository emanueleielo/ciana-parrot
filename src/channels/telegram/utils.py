"""Telegram channel utilities."""

import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def typing_indicator(bot, chat_id: int):
    """Async context manager that sends 'typing' action every 3 seconds.

    Usage::

        async with typing_indicator(bot, chat_id):
            response = await slow_operation()
    """
    async def _loop():
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(3)

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
