"""Telegram channel adapter using python-telegram-bot v22+."""

import asyncio
import html
import logging
import re
from pathlib import Path

import telegram.error
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
MAX_SEEN_UPDATES = 1000


class TelegramChannel(AbstractChannel):
    """Telegram channel adapter."""

    name = "telegram"

    def __init__(self, config: dict):
        self._token = config["token"]
        self._trigger = config.get("trigger", "@Ciana")
        self._app: Application | None = None
        self._callback = None
        self._seen_updates: set[int] = set()

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
        """Send message via Telegram. Converts Markdown to Telegram HTML."""
        if not self._app:
            return
        converted = _md_to_telegram_html(text)
        for chunk in _split_text(converted, TELEGRAM_MAX_MESSAGE_LEN):
            try:
                await self._app.bot.send_message(
                    chat_id=int(chat_id),
                    text=chunk,
                    parse_mode="HTML",
                )
            except telegram.error.BadRequest:
                await self._app.bot.send_message(
                    chat_id=int(chat_id),
                    text=chunk,
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
        """Reset session by sending a reset signal through the callback."""
        if not self._callback:
            return
        chat = update.effective_chat
        user = update.effective_user
        msg = IncomingMessage(
            channel=self.name,
            chat_id=str(chat.id),
            user_id=str(user.id) if user else "unknown",
            user_name=user.first_name if user else "unknown",
            text="",
            is_private=chat.type == "private",
            reset_session=True,
        )
        await self._callback(msg)
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

        # Dedup: skip already-seen updates
        uid = update.update_id
        if uid in self._seen_updates:
            logger.debug("Skipping duplicate update %d", uid)
            return
        self._seen_updates.add(uid)
        if len(self._seen_updates) > MAX_SEEN_UPDATES:
            # Discard oldest half
            to_keep = sorted(self._seen_updates)[MAX_SEEN_UPDATES // 2:]
            self._seen_updates = set(to_keep)

        chat = update.effective_chat
        user = update.effective_user
        text = update.message.text
        chat_id = str(chat.id)
        is_private = chat.type == "private"

        msg = IncomingMessage(
            channel=self.name,
            chat_id=chat_id,
            user_id=str(user.id) if user else "unknown",
            user_name=user.first_name if user else "unknown",
            text=text,
            is_private=is_private,
        )

        # Process in background so the handler returns immediately
        asyncio.create_task(self._process_message(msg, chat.id))

    async def _process_message(self, msg: IncomingMessage, chat_id: int) -> None:
        """Process a message in the background."""
        str_chat_id = str(chat_id)

        # Typing indicator while processing
        await self._app.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            response = await self._callback(msg)
            if response:
                await self.send(str_chat_id, response)
        except Exception as e:
            logger.exception("Error processing message from %s", msg.user_id)
            await self.send(str_chat_id, f"Error: {e}")


def _md_to_telegram_html(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML."""
    # Split out fenced code blocks to protect them from further processing
    parts = re.split(r"(```[\s\S]*?```)", text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Fenced code block
            m = re.match(r"```(\w*)\n?([\s\S]*?)```", part)
            if m:
                lang, code = m.group(1), m.group(2).rstrip()
                escaped = html.escape(code)
                if lang:
                    result.append(f'<pre><code class="language-{lang}">{escaped}</code></pre>')
                else:
                    result.append(f"<pre>{escaped}</pre>")
            else:
                result.append(html.escape(part))
        else:
            result.append(_md_inline_to_html(part))
    return "".join(result)


def _md_inline_to_html(text: str) -> str:
    """Convert inline Markdown to Telegram HTML."""
    # Protect inline code spans first
    codes: list[str] = []

    def _save_code(m: re.Match) -> str:
        codes.append(html.escape(m.group(1)))
        return f"\x00CODE{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _save_code, text)

    # Escape HTML in the rest
    text = html.escape(text)

    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    # Italic: *text* or _text_  (but not inside words like file_name)
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<i>\1</i>", text)
    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Headers: # text → bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # Blockquotes: > text
    text = re.sub(
        r"^(?:&gt;|>) (.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE
    )
    # Merge adjacent blockquotes
    text = re.sub(r"</blockquote>\n<blockquote>", "\n", text)
    # Horizontal rules: --- or *** → line
    text = re.sub(r"^[-*]{3,}$", "—" * 20, text, flags=re.MULTILINE)

    # Restore inline code
    for idx, code in enumerate(codes):
        text = text.replace(f"\x00CODE{idx}\x00", f"<code>{code}</code>")

    return text


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
