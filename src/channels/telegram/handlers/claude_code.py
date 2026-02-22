"""Claude Code mode handler for Telegram — inline keyboard UI."""

import asyncio
import html
import logging

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

from ....bridges.claude_code.bridge import CCResponse
from ..formatting import md_to_telegram_html, split_text, strip_html_tags, TELEGRAM_MAX_MESSAGE_LEN
from ..rendering import render_events
from ..utils import typing_indicator

logger = logging.getLogger(__name__)

CC_PAGE_SIZE = 6
_VALID_EFFORTS = {"low", "medium", "high"}

# Button labels — imported by channel.py for intercept matching
CC_BTN_EXIT = "\u2190 Exit CC"
CC_BTN_CONVERSATIONS = "\U0001f4cb Conversations"


def _cc_reply_keyboard(project_name: str) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard shown while in CC mode."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CC_BTN_CONVERSATIONS),
          KeyboardButton(CC_BTN_EXIT)]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=f"Message Claude Code ({project_name})...",
    )


_MAX_STORED_DETAILS = 50


def _render_cc_response(cc_resp: CCResponse) -> tuple[str, list[str]]:
    """Render a CCResponse into (compact_text, tool_detail_items).

    Delegates to the shared render_events(), with CC-specific error prefix.
    """
    if cc_resp.error:
        if "\n" in cc_resp.error:
            return f"Claude Code error:\n```\n{cc_resp.error}\n```", []
        return f"Claude Code error: {cc_resp.error}", []

    return render_events(cc_resp.events)


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
        return [
            "/cc - Claude Code mode",
            "/cc exit - Exit Claude Code mode",
            "cc:help - Claude Code commands (in CC mode)",
        ]

    def is_active(self, user_id: str) -> bool:
        return self._bridge.is_claude_code_mode(user_id)

    def match_button(self, text: str) -> str | None:
        """Check if text matches a CC reply keyboard button.

        Returns "exit", "conversations", or None.
        """
        stripped = text.strip()
        if stripped == CC_BTN_EXIT:
            return "exit"
        if stripped == CC_BTN_CONVERSATIONS:
            return "conversations"
        return None

    def _get_project_display_name(self, user_id: str) -> str:
        """Get the display name of the active project for a user."""
        state = self._bridge.get_user_state(user_id)
        if state.active_project_path:
            return state.active_project_path.rsplit("/", 1)[-1]
        return "Claude Code"

    async def process_message(self, user_id: str, text: str, chat_id: int) -> None:
        """Process a text message while in Claude Code mode."""
        if text.strip().lower().startswith("cc:"):
            await self._handle_cc_command(user_id, text.strip(), chat_id)
            return
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

    # --- cc: command dispatch ---

    async def _handle_cc_command(self, user_id: str, text: str, chat_id: int) -> None:
        """Dispatch a cc: command (e.g. cc:help, cc:model sonnet)."""
        str_chat_id = str(chat_id)
        project_name = self._get_project_display_name(user_id)
        keyboard = _cc_reply_keyboard(project_name)

        raw = text[3:]  # strip "cc:"
        parts = raw.strip().split(None, 1)
        command = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "help":
            await self._cc_cmd_help(str_chat_id, keyboard)
        elif command == "model":
            await self._cc_cmd_model(user_id, args, str_chat_id, keyboard)
        elif command == "effort":
            await self._cc_cmd_effort(user_id, args, str_chat_id, keyboard)
        elif command == "compact":
            await self._cc_cmd_compact(user_id, str_chat_id, chat_id, keyboard)
        elif command == "clear":
            await self._cc_cmd_clear(user_id, str_chat_id, keyboard)
        elif command == "status":
            await self._cc_cmd_status(user_id, str_chat_id, keyboard)
        elif command == "cost":
            await self._cc_cmd_cost(str_chat_id, keyboard)
        else:
            await self._send(
                str_chat_id,
                f"Unknown command: <code>cc:{html.escape(command)}</code>\n"
                f"Type <code>cc:help</code> for available commands.",
                reply_markup=keyboard,
            )

    async def _cc_cmd_help(self, chat_id: str, keyboard) -> None:
        await self._send(chat_id, (
            "<b>Claude Code Commands</b>\n\n"
            "<code>cc:help</code> — Show this help\n"
            "<code>cc:model [name]</code> — Show or switch model\n"
            "<code>cc:effort [level]</code> — Set effort (low, medium, high)\n"
            "<code>cc:compact</code> — Fork session to reduce context\n"
            "<code>cc:clear</code> — Start new conversation\n"
            "<code>cc:status</code> — Show session info\n"
            "<code>cc:cost</code> — Token usage info"
        ), reply_markup=keyboard)

    async def _cc_cmd_model(self, user_id: str, args: str, chat_id: str, keyboard) -> None:
        state = self._bridge.get_user_state(user_id)
        if not args:
            current = state.active_model or "default"
            await self._send(chat_id, (
                f"Current model: <code>{html.escape(current)}</code>\n"
                f"Usage: <code>cc:model sonnet</code> or full ID"
            ), reply_markup=keyboard)
            return
        self._bridge.set_model(user_id, args)
        await self._send(chat_id,
                         f"Model set to <code>{html.escape(args)}</code>",
                         reply_markup=keyboard)

    async def _cc_cmd_effort(self, user_id: str, args: str, chat_id: str, keyboard) -> None:
        state = self._bridge.get_user_state(user_id)
        if not args:
            current = state.active_effort or "default"
            await self._send(chat_id, (
                f"Current effort: <code>{html.escape(current)}</code>\n"
                f"Usage: <code>cc:effort low|medium|high</code>"
            ), reply_markup=keyboard)
            return
        level = args.lower()
        if level not in _VALID_EFFORTS:
            await self._send(chat_id,
                             f"Invalid effort: <code>{html.escape(level)}</code> "
                             f"(valid: low, medium, high)",
                             reply_markup=keyboard)
            return
        self._bridge.set_effort(user_id, level)
        await self._send(chat_id,
                         f"Effort set to <code>{level}</code>",
                         reply_markup=keyboard)

    async def _cc_cmd_compact(self, user_id: str, chat_id: str,
                              int_chat_id: int, keyboard) -> None:
        state = self._bridge.get_user_state(user_id)
        if not state.active_session_id:
            await self._send(chat_id,
                             "No active session. Start a conversation first.",
                             reply_markup=keyboard)
            return
        await self._send(chat_id, "Forking session\u2026", reply_markup=keyboard)
        lock = self._user_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            async with typing_indicator(self._app.bot, int_chat_id):
                cc_resp = await self._bridge.fork_session(user_id)
        if cc_resp.error:
            await self._send(chat_id,
                             f"Fork failed: {html.escape(cc_resp.error)}",
                             reply_markup=keyboard)
        else:
            new_state = self._bridge.get_user_state(user_id)
            sid = (new_state.active_session_id or "unknown")[:8]
            await self._send(chat_id,
                             f"Session forked: <code>{sid}\u2026</code>\n"
                             f"Context has been reduced.",
                             reply_markup=keyboard)

    async def _cc_cmd_clear(self, user_id: str, chat_id: str, keyboard) -> None:
        state = self._bridge.get_user_state(user_id)
        self._bridge.activate_session(
            user_id, state.active_project, state.active_project_path,
            session_id=None)
        await self._send(chat_id,
                         "Conversation cleared. Send a message to start fresh.",
                         reply_markup=keyboard)

    async def _cc_cmd_status(self, user_id: str, chat_id: str, keyboard) -> None:
        state = self._bridge.get_user_state(user_id)
        project_name = self._get_project_display_name(user_id)
        session = (state.active_session_id or "new")[:8]
        model = state.active_model or "default"
        effort = state.active_effort or "default"
        await self._send(chat_id, (
            f"<b>Claude Code Status</b>\n\n"
            f"Project: <code>{html.escape(project_name)}</code>\n"
            f"Session: <code>{session}\u2026</code>\n"
            f"Model: <code>{html.escape(model)}</code>\n"
            f"Effort: <code>{html.escape(effort)}</code>"
        ), reply_markup=keyboard)

    async def _cc_cmd_cost(self, chat_id: str, keyboard) -> None:
        await self._send(chat_id,
                         "Token usage is not available in piped mode.\n"
                         "Check the Claude Code dashboard for details.",
                         reply_markup=keyboard)

    async def _send_response(self, chat_id: int, str_chat_id: str,
                             compact: str, keyboard, inline_markup) -> None:
        """Send response with reply keyboard or inline tool-details button.

        Inline markup takes priority — the persistent reply keyboard stays
        regardless, so we can attach the inline button directly to the message.
        """
        markup = inline_markup if inline_markup else keyboard
        await self._send(str_chat_id, compact, reply_markup=markup)

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
            logger.debug("Failed to send placeholder message", exc_info=True)
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
            timeout_text = (
                "Claude Code is taking longer than expected. "
                "It may still be working in the background \u2014 "
                "try sending a follow-up message in a moment."
            )
            if placeholder:
                try:
                    await placeholder.edit_text(timeout_text)
                except Exception:
                    await self._send(str_chat_id, timeout_text, reply_markup=keyboard)
            else:
                await self._send(str_chat_id, timeout_text, reply_markup=keyboard)

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

    async def show_menu(self, user_id: str, chat_id: str) -> None:
        """Show conversation list for the active project (reply keyboard action)."""
        if not self._bridge.is_claude_code_mode(user_id):
            await self._send(
                chat_id,
                "You're not in Claude Code mode. Use /cc to enter.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        state = self._bridge.get_user_state(user_id)
        projects = self._bridge.list_projects()
        self._projects_cache[user_id] = projects

        proj_idx = next(
            (i for i, p in enumerate(projects)
             if p.encoded_name == state.active_project),
            None,
        )
        if proj_idx is None:
            await self._send(chat_id, "Project not found. Use /cc to select one.")
            return

        await self._show_conversation_list(
            user_id=user_id, proj_idx=proj_idx, chat_id=int(chat_id))

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

        # If already in mode, show status with navigation
        if self._bridge.is_claude_code_mode(user_id):
            state = self._bridge.get_user_state(user_id)
            project_name = self._get_project_display_name(user_id)
            await update.message.reply_text(
                f"<b>Claude Code mode active</b>\n"
                f"Project: <code>{html.escape(state.active_project_path or 'unknown')}</code>\n"
                f"Session: <code>{(state.active_session_id or 'new')[:8]}...</code>",
                parse_mode="HTML",
                reply_markup=_cc_status_buttons(),
            )
            return

        # Show project list
        await self._show_project_list(user_id, message=update.message)

    # --- List views ---

    async def _send_list_view(self, text: str, markup: InlineKeyboardMarkup, *,
                               message=None, chat_id: Optional[int] = None,
                               edit: bool = False) -> None:
        """Send a list view via edit, reply, or new message."""
        if message and edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        elif message:
            await message.reply_text(text, parse_mode="HTML", reply_markup=markup)
        elif chat_id:
            await self._app.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="HTML", reply_markup=markup)

    async def _show_project_list(self, user_id: str, page: int = 0, *,
                                  message=None, chat_id: Optional[int] = None,
                                  edit: bool = False) -> None:
        projects = self._bridge.list_projects()
        self._projects_cache[user_id] = projects

        if not projects:
            await self._send_list_view(
                "No Claude Code projects found.", InlineKeyboardMarkup([]),
                message=message, chat_id=chat_id, edit=edit)
            return

        total_pages = (len(projects) + CC_PAGE_SIZE - 1) // CC_PAGE_SIZE
        start = page * CC_PAGE_SIZE
        page_projects = projects[start:start + CC_PAGE_SIZE]

        text = "\U0001f4c2 <b>Projects</b>"
        buttons = []
        for i, proj in enumerate(page_projects):
            idx = start + i
            rel = _relative_time(proj.last_activity)
            btn_label = f"{proj.display_name} \u00b7 {proj.conversation_count} conv \u00b7 {rel}"
            if len(btn_label) > 60:
                btn_label = btn_label[:57] + "\u2026"
            buttons.append([InlineKeyboardButton(
                btn_label,
                callback_data=f"cc:proj:{idx}",
            )])

        nav = _pagination_row("cc:projects", page, total_pages)
        if nav:
            buttons.append(nav)

        markup = InlineKeyboardMarkup(buttons)
        await self._send_list_view(
            text, markup, message=message, chat_id=chat_id, edit=edit)

    async def _show_conversation_list(self, user_id: str, proj_idx: int,
                                       page: int = 0, *, message=None,
                                       chat_id: Optional[int] = None,
                                       edit: bool = False) -> None:
        projects = self._projects_cache.get(user_id, [])

        if proj_idx >= len(projects):
            await self._send_list_view(
                "Project cache expired. Try /cc again.", InlineKeyboardMarkup([]),
                message=message, chat_id=chat_id, edit=edit)
            return

        project = projects[proj_idx]
        conversations = self._bridge.list_conversations(project.encoded_name)
        self._conversations_cache[user_id] = conversations

        total_pages = max(1, (len(conversations) + CC_PAGE_SIZE - 1) // CC_PAGE_SIZE)
        start = page * CC_PAGE_SIZE
        page_convs = conversations[start:start + CC_PAGE_SIZE]

        text = f"\U0001f4c1 <b>{html.escape(project.display_name)}</b>"
        buttons = []
        for i, conv in enumerate(page_convs):
            conv_idx = start + i
            preview = conv.first_message[:35] + "\u2026" if len(conv.first_message) > 35 else conv.first_message
            rel = _relative_time(conv.timestamp)
            branch_tag = f" [{conv.git_branch}]" if conv.git_branch else ""
            btn_label = f"{preview} \u00b7 {rel}{branch_tag}"
            if len(btn_label) > 60:
                btn_label = btn_label[:57] + "\u2026"
            buttons.append([InlineKeyboardButton(
                btn_label,
                callback_data=f"cc:conv:{proj_idx}:{conv_idx}",
            )])

        buttons.append([
            InlineKeyboardButton("\u2795 New session", callback_data=f"cc:new:{proj_idx}"),
            InlineKeyboardButton("\u2b05\ufe0f Projects", callback_data="cc:projects:0"),
        ])

        nav = _pagination_row(f"cc:cpage:{proj_idx}", page, total_pages)
        if nav:
            buttons.append(nav)

        markup = InlineKeyboardMarkup(buttons)
        await self._send_list_view(
            text, markup, message=message, chat_id=chat_id, edit=edit)

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
                await self._show_project_list(
                    user_id, page=int(parts[2]),
                    message=query.message, edit=True)

            elif data.startswith("cc:proj:"):
                await query.answer("Loading conversations\u2026")
                await self._show_conversation_list(
                    user_id, proj_idx=int(parts[2]),
                    message=query.message, edit=True)

            elif data.startswith("cc:conv:"):
                await query.answer("Activating session\u2026")
                await self._activate_conversation(query.message, user_id,
                                                   int(parts[2]), int(parts[3]))

            elif data.startswith("cc:cpage:"):
                await query.answer()
                await self._show_conversation_list(
                    user_id, proj_idx=int(parts[2]),
                    page=int(parts[3]), message=query.message, edit=True)

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

            elif data == "cc:convs_menu":
                await query.answer("Loading conversations\u2026")
                state = self._bridge.get_user_state(user_id)
                projects = self._bridge.list_projects()
                self._projects_cache[user_id] = projects
                proj_idx = next(
                    (i for i, p in enumerate(projects)
                     if p.encoded_name == state.active_project),
                    None,
                )
                if proj_idx is not None:
                    await self._show_conversation_list(
                        user_id, proj_idx=proj_idx,
                        message=query.message, edit=True)
                else:
                    await self._show_project_list(
                        user_id, message=query.message, edit=True)

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
        InlineKeyboardButton("\U0001f504 Switch Project", callback_data="cc:projects:0"),
        InlineKeyboardButton("\u274c Exit CC", callback_data="cc:exit"),
    ]])


def _cc_status_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("\U0001f4ac Conversations", callback_data="cc:convs_menu"),
        InlineKeyboardButton("\U0001f504 Switch Project", callback_data="cc:projects:0"),
        InlineKeyboardButton("\u274c Exit", callback_data="cc:exit"),
    ]])


def _pagination_row(prefix: str, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("\u2039 Prev", callback_data=f"{prefix}:{page - 1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("Next \u203a", callback_data=f"{prefix}:{page + 1}"))
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
