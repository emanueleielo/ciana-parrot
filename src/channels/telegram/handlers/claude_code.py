"""Claude Code mode handler for Telegram — inline keyboard UI."""

import asyncio
import html
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from ....bridges.claude_code.bridge import (
    CCResponse,
    TextEvent,
    ThinkingEvent,
    ToolCallEvent,
)
from ....utils import truncate_text
from ..formatting import md_to_telegram_html, split_text, strip_html_tags, TELEGRAM_MAX_MESSAGE_LEN
from ..utils import typing_indicator

logger = logging.getLogger(__name__)

CC_PAGE_SIZE = 6

# Button labels — imported by channel.py for intercept matching
CC_BTN_EXIT = "\u2190 Back to Ciana"
CC_BTN_STATUS_PREFIX = "\u26a1 "


def _cc_reply_keyboard(project_name: str) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard shown while in CC mode."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(f"{CC_BTN_STATUS_PREFIX}{project_name}"),
          KeyboardButton(CC_BTN_EXIT)]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Message to Claude Code...",
    )


_MAX_STORED_DETAILS = 50


def _tool_detail_html(ev: ToolCallEvent) -> str:
    """Render a single tool call as Telegram HTML for the details view."""
    icon = "\u274c" if ev.is_error else "\u2022"
    name_esc = html.escape(ev.name)
    summary_esc = f" {html.escape(ev.input_summary)}" if ev.input_summary else ""
    header = f"{icon} <b>{name_esc}</b>{summary_esc}"
    if ev.result_text:
        truncated = truncate_text(ev.result_text, max_chars=2500, max_lines=25)
        return f"{header}\n<pre>{html.escape(truncated)}</pre>"
    return f"{header} \u2714"


def _thinking_detail_html(ev: ThinkingEvent) -> str:
    """Render a thinking block as Telegram HTML for the details view."""
    lines = ev.text.splitlines()[:15]
    truncated = "\n".join(lines)
    if len(truncated) > 1500:
        truncated = truncated[:1500]
    return f"\U0001f4ad <b>Thinking</b>\n<blockquote>{html.escape(truncated)}</blockquote>"


def _render_cc_response(cc_resp: CCResponse) -> tuple[str, list[str]]:
    """Render a CCResponse into (compact_text, tool_detail_items).

    compact_text: main message with tool one-liners, thinking, and text.
    tool_detail_items: list of pre-formatted HTML strings, one per event.
    """
    if cc_resp.error:
        if "\n" in cc_resp.error:
            return f"Claude Code error:\n```\n{cc_resp.error}\n```", []
        return f"Claude Code error: {cc_resp.error}", []

    # Separate events by kind for rendering
    parts: list[str] = []
    tool_lines: list[str] = []

    def flush_tools():
        if tool_lines:
            parts.append("\n".join(tool_lines))
            tool_lines.clear()

    for ev in cc_resp.events:
        if isinstance(ev, ThinkingEvent):
            flush_tools()
            quoted = "\n".join(f"> {l}" for l in ev.text.splitlines()[:15])
            parts.append(f"**Thinking**\n{quoted}")

        elif isinstance(ev, ToolCallEvent):
            summary_str = f" {ev.input_summary}" if ev.input_summary else ""
            if ev.is_error and ev.result_text:
                icon = "\u274c"
                line = f"{icon} **{ev.name}**{summary_str}"
                truncated = truncate_text(ev.result_text, max_lines=8)
                flush_tools()
                parts.append(f"{line}\n```\n{truncated}\n```")
            else:
                icon = "\u274c" if ev.is_error else "\u2022"
                line = f"{icon} **{ev.name}**{summary_str}"
                tool_lines.append(line)

        elif isinstance(ev, TextEvent):
            flush_tools()
            parts.append(ev.text)

    flush_tools()

    # Build per-event HTML details (one message per tool/thinking)
    detail_items: list[str] = []
    for ev in cc_resp.events:
        if isinstance(ev, ToolCallEvent):
            detail_items.append(_tool_detail_html(ev))
        elif isinstance(ev, ThinkingEvent):
            detail_items.append(_thinking_detail_html(ev))

    compact = "\n\n".join(parts) if parts else "(empty response)"
    return compact, detail_items


class ClaudeCodeHandler:
    """Handles /cc command, inline keyboards, and mode-intercepted messages.

    Implements the ModeHandler protocol for TelegramChannel.
    """

    name = "cc"

    def __init__(self, bridge, app, send_fn):
        self._bridge = bridge
        self._app = app
        self._send = send_fn
        self._user_locks: dict[str, asyncio.Lock] = {}
        self._tool_details: dict[str, dict] = {}  # key -> {"items": list[str], "msg_ids": list[int]}
        self._detail_counter = 0
        # Pagination caches (keyed by user_id)
        self._projects_cache: dict[str, list] = {}
        self._conversations_cache: dict[str, list] = {}

    def register(self) -> None:
        """Register command and callback handlers on the Telegram app."""
        self._app.add_handler(CommandHandler("cc", self._cmd_cc))
        self._app.add_handler(CallbackQueryHandler(
            self._handle_callback, pattern=r"^cc:"))

    def get_commands(self) -> list[tuple[str, str]]:
        """Return bot menu commands for this handler."""
        return [("cc", "Claude Code mode")]

    def get_help_lines(self) -> list[str]:
        """Return help text lines for this handler."""
        return ["/cc - Claude Code mode", "/cc exit - Exit Claude Code mode"]

    def is_active(self, user_id: str) -> bool:
        return self._bridge.is_claude_code_mode(user_id)

    def match_button(self, text: str) -> str | None:
        """Check if text matches a CC reply keyboard button.

        Returns "exit", "status", or None.
        """
        stripped = text.strip()
        if stripped == CC_BTN_EXIT:
            return "exit"
        if stripped.startswith(CC_BTN_STATUS_PREFIX):
            return "status"
        return None

    def _get_project_display_name(self, user_id: str) -> str:
        """Get the display name of the active project for a user."""
        state = self._bridge.get_user_state(user_id)
        if state.active_project_path:
            return state.active_project_path.rsplit("/", 1)[-1]
        return "Claude Code"

    async def process_message(self, user_id: str, text: str, chat_id: int) -> None:
        """Process a text message while in Claude Code mode."""
        lock = self._user_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            await self._process_message_locked(user_id, text, chat_id)

    def _store_tool_details(self, items: list[str]) -> str:
        """Store tool detail items and return the lookup key."""
        self._detail_counter += 1
        key = str(self._detail_counter)
        self._tool_details[key] = {"items": items, "msg_ids": []}
        if len(self._tool_details) > _MAX_STORED_DETAILS:
            oldest = sorted(self._tool_details, key=int)[
                :len(self._tool_details) - _MAX_STORED_DETAILS]
            for k in oldest:
                del self._tool_details[k]
        return key

    async def _send_response(self, chat_id: int, str_chat_id: str,
                             compact: str, keyboard, inline_markup) -> None:
        """Send response with reply keyboard; attach tool-details button as reply."""
        result = await self._send(str_chat_id, compact, reply_markup=keyboard)
        if inline_markup and result:
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text="\U0001f4cb",
                    reply_markup=inline_markup,
                    reply_to_message_id=int(result.message_id),
                )
            except Exception:
                pass

    async def _process_message_locked(self, user_id: str, text: str, chat_id: int) -> None:
        str_chat_id = str(chat_id)
        project_name = self._get_project_display_name(user_id)
        keyboard = _cc_reply_keyboard(project_name)

        # Send placeholder
        try:
            placeholder = await self._app.bot.send_message(
                chat_id=chat_id,
                text="Processing\u2026",
                reply_markup=keyboard,
            )
        except Exception:
            placeholder = None

        try:
            async with typing_indicator(self._app.bot, chat_id):
                cc_resp = await asyncio.wait_for(
                    self._bridge.send_message(user_id, text),
                    timeout=300,
                )

            compact, tool_detail_items = _render_cc_response(cc_resp)

            if compact:
                # Build inline button for tool details if available
                inline_markup = None
                if tool_detail_items:
                    key = self._store_tool_details(tool_detail_items)
                    inline_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "\U0001f4cb Tool details",
                            callback_data=f"cc:tools:{key}"),
                    ]])

                converted = md_to_telegram_html(compact)
                chunks = split_text(converted, TELEGRAM_MAX_MESSAGE_LEN)

                if len(chunks) == 1 and placeholder:
                    try:
                        await placeholder.edit_text(
                            chunks[0], parse_mode="HTML",
                            reply_markup=inline_markup)
                    except Exception:
                        try:
                            await placeholder.delete()
                        except Exception:
                            pass
                        await self._send_response(
                            chat_id, str_chat_id, compact, keyboard, inline_markup)
                else:
                    if placeholder:
                        try:
                            await placeholder.delete()
                        except Exception:
                            pass
                    await self._send_response(
                        chat_id, str_chat_id, compact, keyboard, inline_markup)
            elif placeholder:
                try:
                    await placeholder.delete()
                except Exception:
                    pass

        except TimeoutError:
            error_text = "Request timed out."
            if placeholder:
                try:
                    await placeholder.delete()
                except Exception:
                    pass
            await self._send(str_chat_id, error_text, reply_markup=keyboard)

        except Exception as e:
            logger.exception("Error in Claude Code message for user %s", user_id)
            error_text = f"Claude Code error: {e}"
            if placeholder:
                try:
                    await placeholder.delete()
                except Exception:
                    pass
            await self._send(str_chat_id, error_text, reply_markup=keyboard)

    # --- Public methods for channel.py reply keyboard intercepts ---

    async def exit_with_keyboard_remove(self, user_id: str, chat_id: str) -> None:
        """Exit CC mode and remove the reply keyboard."""
        if self._bridge.is_claude_code_mode(user_id):
            self._bridge.exit_mode(user_id)
        await self._send(
            chat_id,
            "Exited Claude Code mode. Messages go to Ciana again.",
            reply_markup=ReplyKeyboardRemove(),
        )

    async def show_status(self, user_id: str, chat_id: str) -> None:
        """Show CC mode status with persistent keyboard."""
        if not self._bridge.is_claude_code_mode(user_id):
            await self._send(
                chat_id,
                "You're not in Claude Code mode. Use /cc to enter.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        state = self._bridge.get_user_state(user_id)
        project_name = self._get_project_display_name(user_id)
        await self._send(
            chat_id,
            f"**Claude Code mode active**\n"
            f"Project: `{html.escape(state.active_project_path or 'unknown')}`\n"
            f"Session: `{(state.active_session_id or 'new')[:8]}...`",
            reply_markup=_cc_reply_keyboard(project_name),
        )

    # --- Command handler ---

    async def _cmd_cc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat.type != "private":
            await update.message.reply_text(
                "Claude Code mode is only available in private chats.")
            return

        user_id = str(user.id) if user else "unknown"
        args = update.message.text.split(maxsplit=1)

        # /cc exit
        if len(args) > 1 and args[1].strip().lower() == "exit":
            if self._bridge.is_claude_code_mode(user_id):
                self._bridge.exit_mode(user_id)
                await update.message.reply_text(
                    "Exited Claude Code mode. Messages go to Ciana again.",
                    reply_markup=ReplyKeyboardRemove(),
                )
            else:
                await update.message.reply_text("You're not in Claude Code mode.")
            return

        # If already in mode, show status
        if self._bridge.is_claude_code_mode(user_id):
            state = self._bridge.get_user_state(user_id)
            project_name = self._get_project_display_name(user_id)
            await update.message.reply_text(
                f"<b>Claude Code mode active</b>\n"
                f"Project: <code>{state.active_project_path or 'unknown'}</code>\n"
                f"Session: <code>{(state.active_session_id or 'new')[:8]}...</code>",
                parse_mode="HTML",
                reply_markup=_cc_reply_keyboard(project_name),
            )
            return

        # Show project list
        await self._show_project_list(update.message, user_id)

    # --- List views ---

    async def _show_project_list(self, message, user_id: str, page: int = 0,
                                  edit: bool = False) -> None:
        projects = self._bridge.list_projects()
        self._projects_cache[user_id] = projects

        if not projects:
            text = "No Claude Code projects found."
            if edit:
                await message.edit_text(text)
            else:
                await message.reply_text(text)
            return

        total_pages = (len(projects) + CC_PAGE_SIZE - 1) // CC_PAGE_SIZE
        start = page * CC_PAGE_SIZE
        page_projects = projects[start:start + CC_PAGE_SIZE]

        lines = ["<b>Claude Code Projects</b>\n"]
        buttons = []
        for i, proj in enumerate(page_projects):
            idx = start + i
            rel = _relative_time(proj.last_activity)
            lines.append(f"{idx + 1}. <b>{html.escape(proj.display_name)}</b>"
                         f" — {proj.conversation_count} conv · {rel}")
            buttons.append([InlineKeyboardButton(
                f"{proj.display_name} ({proj.conversation_count})",
                callback_data=f"cc:proj:{idx}",
            )])

        nav = _pagination_row("cc:projects", page, total_pages)
        if nav:
            buttons.append(nav)

        text = "\n".join(lines)
        markup = InlineKeyboardMarkup(buttons)
        if edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    async def _show_conversation_list(self, message, user_id: str, proj_idx: int,
                                       page: int = 0, edit: bool = False) -> None:
        projects = self._projects_cache.get(user_id, [])

        if proj_idx >= len(projects):
            text = "Project cache expired. Try /cc again."
            if edit:
                await message.edit_text(text)
            else:
                await message.reply_text(text)
            return

        project = projects[proj_idx]
        conversations = self._bridge.list_conversations(project.encoded_name)
        self._conversations_cache[user_id] = conversations

        total_pages = max(1, (len(conversations) + CC_PAGE_SIZE - 1) // CC_PAGE_SIZE)
        start = page * CC_PAGE_SIZE
        page_convs = conversations[start:start + CC_PAGE_SIZE]

        lines = [f"<b>{html.escape(project.display_name)}</b> — conversations\n"]
        buttons = []
        for i, conv in enumerate(page_convs):
            conv_idx = start + i
            preview = conv.first_message[:50] + "..." if len(conv.first_message) > 50 else conv.first_message
            rel = _relative_time(conv.timestamp)
            branch_tag = f" [{conv.git_branch}]" if conv.git_branch else ""
            lines.append(f"{conv_idx + 1}. {html.escape(preview)}"
                         f" · {conv.message_count} msg · {rel}{branch_tag}")
            buttons.append([InlineKeyboardButton(
                f"{preview} ({conv.message_count} msg)",
                callback_data=f"cc:conv:{proj_idx}:{conv_idx}",
            )])

        buttons.append([
            InlineKeyboardButton("+ New", callback_data=f"cc:new:{proj_idx}"),
            InlineKeyboardButton("<< Back", callback_data="cc:projects:0"),
        ])

        nav = _pagination_row(f"cc:cpage:{proj_idx}", page, total_pages)
        if nav:
            buttons.append(nav)

        text = "\n".join(lines)
        markup = InlineKeyboardMarkup(buttons)
        if edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    # --- Callback router ---

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        data = query.data or ""

        try:
            parts = data.split(":")

            if data.startswith("cc:projects:"):
                await query.answer("Loading projects\u2026")
                await self._show_project_list(query.message, user_id,
                                              page=int(parts[2]), edit=True)

            elif data.startswith("cc:proj:"):
                await query.answer("Loading conversations\u2026")
                await self._show_conversation_list(query.message, user_id,
                                                   proj_idx=int(parts[2]), edit=True)

            elif data.startswith("cc:conv:"):
                await query.answer("Activating session\u2026")
                await self._activate_conversation(query.message, user_id,
                                                   int(parts[2]), int(parts[3]))

            elif data.startswith("cc:cpage:"):
                await query.answer()
                await self._show_conversation_list(query.message, user_id,
                                                   proj_idx=int(parts[2]),
                                                   page=int(parts[3]), edit=True)

            elif data.startswith("cc:new:"):
                await query.answer("Starting new conversation\u2026")
                await self._start_new_conversation(query.message, user_id,
                                                    int(parts[2]))

            elif data.startswith("cc:tools:"):
                key = parts[2]
                entry = self._tool_details.get(key)
                if entry and entry.get("items"):
                    await query.answer()
                    msg_ids = []
                    for item_html in entry["items"]:
                        try:
                            msg = await self._app.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=item_html,
                                parse_mode="HTML",
                                disable_notification=True,
                            )
                            msg_ids.append(msg.message_id)
                        except BadRequest:
                            try:
                                msg = await self._app.bot.send_message(
                                    chat_id=query.message.chat_id,
                                    text=strip_html_tags(item_html),
                                    disable_notification=True,
                                )
                                msg_ids.append(msg.message_id)
                            except Exception:
                                logger.warning("Failed to send tool detail")
                    entry["msg_ids"] = msg_ids
                    try:
                        await query.message.edit_reply_markup(
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton(
                                    "\u2715 Hide details",
                                    callback_data=f"cc:tclose:{key}"),
                            ]]))
                    except Exception:
                        pass
                else:
                    await query.answer("Details no longer available")

            elif data.startswith("cc:tclose:"):
                key = parts[2]
                entry = self._tool_details.get(key)
                if entry and entry.get("msg_ids"):
                    await query.answer()
                    for mid in entry["msg_ids"]:
                        try:
                            await self._app.bot.delete_message(
                                chat_id=query.message.chat_id,
                                message_id=mid)
                        except Exception:
                            pass
                    entry["msg_ids"] = []
                    try:
                        await query.message.edit_reply_markup(
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton(
                                    "\U0001f4cb Tool details",
                                    callback_data=f"cc:tools:{key}"),
                            ]]))
                    except Exception:
                        pass
                else:
                    await query.answer()

            elif data == "cc:exit":
                await query.answer("Exiting Claude Code mode")
                self._bridge.exit_mode(user_id)
                await query.message.edit_reply_markup(reply_markup=None)
                await self._send(
                    str(query.message.chat_id),
                    "Exited Claude Code mode. Messages go to Ciana again.",
                    reply_markup=ReplyKeyboardRemove(),
                )

            else:
                await query.answer()

        except (IndexError, ValueError) as e:
            logger.warning("Bad callback data %r: %s", data, e)
            await query.answer("Something went wrong")
            await query.message.edit_text("Something went wrong. Try /cc again.")

    # --- Activate / new ---

    async def _activate_conversation(self, message, user_id: str,
                                      proj_idx: int, conv_idx: int) -> None:
        projects = self._projects_cache.get(user_id, [])
        conversations = self._conversations_cache.get(user_id, [])

        if proj_idx >= len(projects):
            await message.edit_text("Project cache expired. Try /cc again.")
            return
        if conv_idx >= len(conversations):
            await message.edit_text("Conversation cache expired. Try /cc again.")
            return

        project = projects[proj_idx]
        conv = conversations[conv_idx]
        self._bridge.activate_session(
            user_id, project.encoded_name, project.real_path, conv.session_id
        )

        preview = conv.first_message[:80] + "..." if len(conv.first_message) > 80 else conv.first_message
        await message.edit_text(
            f"<b>Claude Code mode active</b>\n\n"
            f"Project: <code>{html.escape(project.display_name)}</code>\n"
            f"Session: <code>{conv.session_id[:8]}...</code>\n"
            f"Preview: {html.escape(preview)}\n\n"
            f"Send a message to continue this conversation.",
            parse_mode="HTML",
            reply_markup=_cc_mode_buttons(),
        )
        await self._send(
            str(message.chat_id),
            "All messages now go to Claude Code.",
            reply_markup=_cc_reply_keyboard(project.display_name),
        )

    async def _start_new_conversation(self, message, user_id: str,
                                       proj_idx: int) -> None:
        projects = self._projects_cache.get(user_id, [])

        if proj_idx >= len(projects):
            await message.edit_text("Project cache expired. Try /cc again.")
            return

        project = projects[proj_idx]
        self._bridge.activate_session(
            user_id, project.encoded_name, project.real_path, session_id=None
        )

        await message.edit_text(
            f"<b>Claude Code mode active</b> (new conversation)\n\n"
            f"Project: <code>{html.escape(project.display_name)}</code>\n\n"
            f"Send your first message.",
            parse_mode="HTML",
            reply_markup=_cc_mode_buttons(),
        )
        await self._send(
            str(message.chat_id),
            "All messages now go to Claude Code.",
            reply_markup=_cc_reply_keyboard(project.display_name),
        )


# --- Helpers ---

def _cc_mode_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Switch Project", callback_data="cc:projects:0"),
        InlineKeyboardButton("Exit Mode", callback_data="cc:exit"),
    ]])


def _pagination_row(prefix: str, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("<<", callback_data=f"{prefix}:{page - 1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(">>", callback_data=f"{prefix}:{page + 1}"))
    return row


def _relative_time(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    now = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = int((now - dt).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return dt.strftime("%Y-%m-%d")
