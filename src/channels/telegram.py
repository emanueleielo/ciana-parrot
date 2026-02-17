"""Telegram channel adapter using python-telegram-bot v22+."""

import asyncio
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from .base import AbstractChannel, IncomingMessage

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LEN = 4096


class TelegramChannel(AbstractChannel):
    """Telegram channel adapter."""

    name = "telegram"

    def __init__(self, config: dict):
        self._token = config["token"]
        self._trigger = config.get("trigger", "@Ciana")
        self._app: Application | None = None
        self._callback = None

    async def start(self) -> None:
        """Start Telegram polling in the current event loop."""
        self._app = Application.builder().token(self._token).build()

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("new", self._cmd_new))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Manual startup for shared event loop (no run_polling)
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram channel started")

    async def stop(self) -> None:
        """Stop Telegram polling."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram channel stopped")

    async def send(self, chat_id: str, text: str) -> None:
        """Send message via Telegram. Uses HTML parse mode."""
        if not self._app:
            return
        for chunk in _split_text(text, TELEGRAM_MAX_MESSAGE_LEN):
            await self._app.bot.send_message(
                chat_id=int(chat_id),
                text=chunk,
                parse_mode="HTML",
            )

    async def send_file(self, chat_id: str, path: str, caption: str = "") -> None:
        """Send a file via Telegram."""
        if not self._app:
            return
        file_path = Path(path)
        if not file_path.exists():
            await self.send(chat_id, f"File not found: {path}")
            return
        with open(file_path, "rb") as f:
            await self._app.bot.send_document(
                chat_id=int(chat_id),
                document=f,
                caption=caption,
            )

    # --- Command handlers ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Hi! I'm Ciana, your AI assistant.\n"
            "Send me a message or use /help for commands."
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "<b>Commands:</b>\n"
            "/start - Welcome message\n"
            "/help - This message\n"
            "/new - New session\n"
            "/status - System status",
            parse_mode="HTML",
        )

    async def _cmd_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reset session by signaling the router."""
        chat_id = str(update.effective_chat.id)
        # Store reset flag in context for router to pick up
        context.chat_data["reset_session"] = True
        await update.message.reply_text("Session reset. Let's start fresh!")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("System is up and running.")

    # --- Message handler ---

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return
        if not self._callback:
            return

        chat = update.effective_chat
        user = update.effective_user
        text = update.message.text
        is_private = chat.type == "private"

        msg = IncomingMessage(
            channel=self.name,
            chat_id=str(chat.id),
            user_id=str(user.id) if user else "unknown",
            user_name=user.first_name if user else "unknown",
            text=text,
            is_private=is_private,
        )

        # Typing indicator while processing
        await self._app.bot.send_chat_action(chat_id=chat.id, action="typing")

        try:
            response = await self._callback(msg)
            if response:
                await self.send(str(chat.id), response)
        except Exception as e:
            logger.exception("Error processing message from %s", msg.user_id)
            await self.send(str(chat.id), f"Error: {e}")


def _split_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks respecting max length."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at newline
        idx = text.rfind("\n", 0, max_len)
        if idx == -1:
            idx = max_len
        chunks.append(text[:idx])
        text = text[idx:].lstrip("\n")
    return chunks
