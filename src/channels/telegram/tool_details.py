"""Shared tool-details expand/collapse manager for Telegram handlers."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from .formatting import strip_html_tags

logger = logging.getLogger(__name__)

_DEFAULT_MAX_STORED = 50


class ToolDetailsManager:
    """Manage tool-detail storage and expand/collapse callbacks.

    Each instance uses a unique *prefix* (e.g. ``"td"`` for the main agent,
    ``"cc"`` for Claude Code) so callback data never collides between handlers.
    """

    def __init__(self, prefix: str, max_stored: int = _DEFAULT_MAX_STORED):
        self._prefix = prefix
        self._max_stored = max_stored
        self._details: dict[str, dict] = {}
        self._counter = 0

    # --- Public API ---

    def store(self, items: list[str]) -> str:
        """Store tool detail items and return a lookup key."""
        self._counter += 1
        key = str(self._counter)
        self._details[key] = {"items": items, "msg_ids": []}
        if len(self._details) > self._max_stored:
            oldest = sorted(self._details, key=int)[
                :len(self._details) - self._max_stored]
            for k in oldest:
                del self._details[k]
        return key

    def expand_button(self, key: str) -> InlineKeyboardMarkup:
        """Return an inline keyboard with a single 'Tool details' button."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "\U0001f4cb Tool details",
                callback_data=f"{self._prefix}:tools:{key}",
            ),
        ]])

    def collapse_button(self, key: str) -> InlineKeyboardMarkup:
        """Return an inline keyboard with a single 'Hide details' button."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "\u2715 Hide details",
                callback_data=f"{self._prefix}:tclose:{key}",
            ),
        ]])

    async def handle_callback(self, query, bot) -> bool:
        """Handle a callback query if it matches this manager's prefix.

        Returns ``True`` if the callback was handled, ``False`` otherwise.
        """
        data = query.data or ""
        expand_prefix = f"{self._prefix}:tools:"
        collapse_prefix = f"{self._prefix}:tclose:"

        if data.startswith(expand_prefix):
            key = data[len(expand_prefix):]
            await self._handle_expand(query, bot, key)
            return True

        if data.startswith(collapse_prefix):
            key = data[len(collapse_prefix):]
            await self._handle_collapse(query, bot, key)
            return True

        return False

    # --- Internal handlers ---

    async def _handle_expand(self, query, bot, key: str) -> None:
        entry = self._details.get(key)
        if not entry or not entry.get("items"):
            await query.answer("Details no longer available")
            return

        await query.answer()
        msg_ids: list[int] = []
        for item_html in entry["items"]:
            try:
                sent = await bot.send_message(
                    chat_id=query.message.chat_id,
                    text=item_html,
                    parse_mode="HTML",
                    disable_notification=True,
                )
                msg_ids.append(sent.message_id)
            except BadRequest:
                try:
                    sent = await bot.send_message(
                        chat_id=query.message.chat_id,
                        text=strip_html_tags(item_html),
                        disable_notification=True,
                    )
                    msg_ids.append(sent.message_id)
                except Exception:
                    logger.warning("Failed to send tool detail")
        entry["msg_ids"] = msg_ids
        try:
            await query.message.edit_reply_markup(
                reply_markup=self.collapse_button(key))
        except Exception:
            pass

    async def _handle_collapse(self, query, bot, key: str) -> None:
        entry = self._details.get(key)
        if not entry or not entry.get("msg_ids"):
            await query.answer()
            return

        await query.answer()
        for mid in entry["msg_ids"]:
            try:
                await bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=mid,
                )
            except Exception:
                pass
        entry["msg_ids"] = []
        try:
            await query.message.edit_reply_markup(
                reply_markup=self.expand_button(key))
        except Exception:
            pass
