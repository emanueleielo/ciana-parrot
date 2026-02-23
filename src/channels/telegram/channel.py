"""Telegram channel adapter using python-telegram-bot v22+."""

import asyncio
import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

import telegram.error
from telegram import (
    BotCommand,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from ...config import TelegramChannelConfig
from ...transcription import is_configured as transcription_configured, transcribe
from ..base import AbstractChannel, IncomingMessage, SendResult
from .formatting import md_to_telegram_html, split_text, strip_html_tags, TELEGRAM_MAX_MESSAGE_LEN
from .rendering import render_events
from .tool_details import ToolDetailsManager
from .utils import typing_indicator

logger = logging.getLogger(__name__)
MAX_SEEN_UPDATES = 1000


@runtime_checkable
class ModeHandler(Protocol):
    """Protocol for mode handlers (Claude Code, etc.)."""
    name: str

    def register(self) -> None: ...
    def is_active(self, user_id: str) -> bool: ...
    def match_button(self, text: str) -> str | None: ...
    async def process_message(self, user_id: str, text: str, chat_id: int) -> None: ...
    async def exit_with_keyboard_remove(self, user_id: str, chat_id: str) -> None: ...
    async def show_menu(self, user_id: str, chat_id: str) -> None: ...
    def get_commands(self) -> list[tuple[str, str]]: ...
    def get_help_lines(self) -> list[str]: ...


# Factory type: receives (app, send_fn) and returns a ModeHandler
ModeHandlerFactory = Callable[[Application, Callable], "ModeHandler"]


class TelegramChannel(AbstractChannel):
    """Telegram channel adapter."""

    name = "telegram"

    def __init__(self, config: TelegramChannelConfig):
        self._token = config.token
        self._app: Application | None = None
        self._callback = None
        self._seen_updates: set[int] = set()
        self._mode_handlers: list[ModeHandler] = []
        self._mode_handler_factories: list[ModeHandlerFactory] = []
        self._active_tasks: set[asyncio.Task] = set()
        self._tool_details_mgr = ToolDetailsManager("td")

    def register_mode_handler(self, factory: ModeHandlerFactory) -> None:
        """Register a mode handler factory. Called before start().

        The factory will be invoked during start() with (app, send_fn)
        and must return a ModeHandler instance.
        """
        self._mode_handler_factories.append(factory)

    def _tracked_task(self, coro) -> asyncio.Task:
        """Create a task that is tracked for clean shutdown."""
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._active_tasks.discard(t)
            if not t.cancelled() and t.exception():
                logger.error("Unhandled error in background task: %s",
                             t.exception(), exc_info=t.exception())

        task.add_done_callback(_done)
        return task

    async def start(self) -> None:
        """Start Telegram polling in the current event loop."""
        self._app = Application.builder().token(self._token).build()

        # Instantiate mode handlers from registered factories
        for factory in self._mode_handler_factories:
            handler = factory(self._app, self.send)
            self._mode_handlers.append(handler)

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("new", self._cmd_new))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        for handler in self._mode_handlers:
            handler.register()
        self._app.add_handler(CallbackQueryHandler(
            self._handle_tool_details_callback_wrapper, pattern=r"^td:"))
        self._app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.VOICE | filters.AUDIO | filters.PHOTO)
                & ~filters.COMMAND,
                self._handle_message,
            )
        )

        # Manual startup for shared event loop (no run_polling)
        await self._app.initialize()
        await self._app.start()

        # Register bot commands menu before polling starts
        commands = [
            ("start", "Welcome"),
            ("help", "Show commands"),
            ("new", "New session"),
            ("status", "System status"),
        ]
        for handler in self._mode_handlers:
            commands.extend(handler.get_commands())
        await self._app.bot.set_my_commands(
            [BotCommand(c, d) for c, d in commands])

        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram channel started")

    async def stop(self) -> None:
        """Stop Telegram polling and drain active tasks."""
        if self._app:
            await self._app.updater.stop()
            if self._active_tasks:
                logger.info("Draining %d active task(s)…", len(self._active_tasks))
                await asyncio.gather(*self._active_tasks, return_exceptions=True)
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram channel stopped")

    async def send(self, chat_id: str, text: str, *,
                   reply_to_message_id: Optional[str] = None,
                   reply_markup: Optional[object] = None,
                   disable_notification: bool = False) -> Optional[SendResult]:
        """Send message via Telegram. Converts Markdown to Telegram HTML."""
        if not self._app or not text:
            return None
        converted = md_to_telegram_html(text)
        chunks = split_text(converted, TELEGRAM_MAX_MESSAGE_LEN)
        last_msg = None
        for i, chunk in enumerate(chunks):
            kwargs: dict = {
                "chat_id": int(chat_id),
                "text": chunk,
                "parse_mode": "HTML",
                "disable_notification": disable_notification,
            }
            # reply_to only on first chunk (threading)
            if i == 0 and reply_to_message_id:
                kwargs["reply_to_message_id"] = int(reply_to_message_id)
            # reply_markup only on last chunk (keyboard state)
            if i == len(chunks) - 1 and reply_markup is not None:
                kwargs["reply_markup"] = reply_markup
            try:
                last_msg = await self._app.bot.send_message(**kwargs)
            except telegram.error.BadRequest as e:
                logger.warning("send_message BadRequest: %s", e)
                kwargs["text"] = strip_html_tags(kwargs["text"])
                kwargs.pop("parse_mode", None)
                kwargs.pop("reply_to_message_id", None)
                try:
                    last_msg = await self._app.bot.send_message(**kwargs)
                except telegram.error.BadRequest:
                    logger.exception("send_message retry failed")
        if last_msg:
            return SendResult(message_id=str(last_msg.message_id))
        return None

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
        if not update.message:
            return
        await update.message.reply_text(
            "Hi! I'm Ciana, your AI assistant.\n"
            "Send me a message or use /help for commands."
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        lines = [
            "<b>Commands:</b>",
            "/start - Welcome message",
            "/help - This message",
            "/new - New session",
            "/status - System status",
        ]
        for handler in self._mode_handlers:
            lines.extend(handler.get_help_lines())
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    async def _cmd_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reset session by sending a reset signal through the callback."""
        if not update.message or not self._callback:
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
        if not update.message:
            return
        await update.message.reply_text("System is up and running.")

    # --- Message handler ---

    async def _transcribe_voice(self, message, chat_id: str) -> Optional[str]:
        """Download voice/audio and transcribe via configured provider."""
        if not transcription_configured():
            logger.info("Transcription not configured, rejecting voice from chat %s", chat_id)
            await self.send(chat_id, "Voice messages are not supported (transcription not configured).")
            return None

        try:
            # Determine filename and MIME type based on message type
            if message.voice:
                voice_obj = message.voice
                filename, mime_type = "voice.ogg", "audio/ogg"
            else:
                voice_obj = message.audio
                filename = message.audio.file_name or "audio.mp3"
                mime_type = message.audio.mime_type or "audio/mpeg"

            file = await voice_obj.get_file()
            buf = BytesIO()
            await file.download_to_memory(buf)
            audio_bytes = buf.getvalue()

            if not audio_bytes:
                await self.send(chat_id, "Could not download the voice message (empty file).")
                return None

            text = await transcribe(audio_bytes, filename=filename, mime_type=mime_type)
            if not text or not text.strip():
                await self.send(chat_id, "Could not transcribe the voice message (empty result).")
                return None
            return text.strip()
        except Exception as e:
            logger.exception("Voice transcription failed for chat %s", chat_id)
            await self.send(chat_id, f"Voice transcription failed: {e}")
            return None

    async def _download_photo_base64(self, message, chat_id: str) -> Optional[str]:
        """Download highest-resolution photo and return base64-encoded string."""
        try:
            photo = message.photo[-1]  # highest resolution
            file = await photo.get_file()
            buf = BytesIO()
            await file.download_to_memory(buf)
            data = buf.getvalue()
            if not data:
                await self.send(chat_id, "Failed to download the photo (empty file).")
                return None
            return base64.b64encode(data).decode("ascii")
        except Exception:
            logger.exception("Photo download failed for chat %s", chat_id)
            await self.send(chat_id, "Failed to download the photo.")
            return None

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text, voice, and photo messages."""
        if not update.message:
            return
        if not self._callback:
            return

        message = update.message
        has_voice = bool(message.voice or message.audio)
        has_photo = bool(message.photo)
        has_text = bool(message.text)

        # Must have at least one supported content type
        if not has_voice and not has_photo and not has_text:
            return

        # Dedup: skip already-seen updates
        uid = update.update_id
        if uid in self._seen_updates:
            logger.debug("Skipping duplicate update %d", uid)
            return
        self._seen_updates.add(uid)
        if len(self._seen_updates) > MAX_SEEN_UPDATES:
            cutoff = max(self._seen_updates) - MAX_SEEN_UPDATES // 2
            self._seen_updates = {u for u in self._seen_updates if u >= cutoff}

        chat = update.effective_chat
        user = update.effective_user
        chat_id = str(chat.id)
        user_id = str(user.id) if user else "unknown"
        is_private = chat.type == "private"

        # Intercept ReplyKeyboard buttons for mode handlers (text only)
        if is_private and has_text:
            for handler in self._mode_handlers:
                btn = handler.match_button(message.text)
                if btn == "exit":
                    await handler.exit_with_keyboard_remove(user_id, chat_id)
                    return
                if btn == "conversations":
                    await handler.show_menu(user_id, chat_id)
                    return

        # Mode intercept (private chats only) — checked before media
        # download/transcription to avoid wasted API calls
        if is_private:
            for handler in self._mode_handlers:
                if handler.is_active(user_id):
                    if has_photo:
                        await self.send(chat_id, "Photos are not supported in Claude Code mode.")
                        return
                    if has_voice:
                        # Transcribe voice then forward as text to CC mode
                        transcribed = await self._transcribe_voice(message, chat_id)
                        if transcribed is None:
                            return
                        self._tracked_task(handler.process_message(user_id, transcribed, chat.id))
                        return
                    self._tracked_task(handler.process_message(user_id, message.text, chat.id))
                    return

        # Determine text and image content based on message type
        text = ""
        image_base64 = None

        if has_voice:
            transcribed = await self._transcribe_voice(message, chat_id)
            if transcribed is None:
                return
            text = transcribed
        elif has_photo:
            image_base64 = await self._download_photo_base64(message, chat_id)
            if image_base64 is None:
                return
            text = message.caption or ""
        else:
            text = message.text

        msg = IncomingMessage(
            channel=self.name,
            chat_id=chat_id,
            user_id=user_id,
            user_name=user.first_name if user else "unknown",
            text=text,
            is_private=is_private,
            message_id=str(message.message_id),
            image_base64=image_base64,
        )

        # Process in background so the handler returns immediately
        self._tracked_task(self._process_message(msg, chat.id))

    async def _process_message(self, msg: IncomingMessage, chat_id: int) -> None:
        """Process a message in the background."""
        str_chat_id = str(chat_id)

        try:
            async with typing_indicator(self._app.bot, chat_id):
                agent_resp = await self._callback(msg)
            if not agent_resp:
                return

            compact, tool_detail_items = render_events(agent_resp.events)

            # If no events were produced, fall back to plain text
            if not agent_resp.events and agent_resp.text:
                compact = agent_resp.text
                tool_detail_items = []

            # Build inline button for tool details if available
            inline_markup = None
            if tool_detail_items:
                key = self._tool_details_mgr.store(tool_detail_items)
                inline_markup = self._tool_details_mgr.expand_button(key)

            await self.send(str_chat_id, compact,
                            reply_to_message_id=msg.message_id,
                            reply_markup=inline_markup)

        except Exception as e:
            logger.exception("Error processing message from %s", msg.user_id)
            await self.send(str_chat_id, f"Error: {e}")

    async def _handle_tool_details_callback_wrapper(
            self, update: Update,
            context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle tool-details expand/collapse callbacks (td: prefix)."""
        query = update.callback_query
        try:
            await self._tool_details_mgr.handle_callback(query, self._app.bot)
        except (IndexError, ValueError) as e:
            logger.warning("Bad tool-details callback data %r: %s",
                           query.data, e)
            await query.answer("Something went wrong")
