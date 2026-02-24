"""Message router - trigger detection, user allowlist, thread mapping, session logging."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .agent_response import AgentResponse, extract_agent_response
from .channels.base import IncomingMessage
from .config import AppConfig, TelegramChannelConfig
from .store import JsonStore
from .tools.cron import set_current_context

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages from channels to the agent."""

    def __init__(self, agent, config: AppConfig, checkpointer=None):
        self._agent = agent
        self._config = config
        self._workspace = config.agent.workspace
        self._data_dir = config.agent.data_dir
        self._allowed_users = self._load_allowed_users()
        if not self._allowed_users:
            logger.warning("No allowed_users configured for any channel — bot is open to ALL users")
        # Track session resets (persisted so /new survives container restarts)
        self._session_store = JsonStore(Path(self._data_dir, "session_counters.json"))
        self._session_counters: dict[str, int] = {
            k: v for k, v in self._session_store.all().items()
            if isinstance(v, int)
        }
        # Ensure counters don't collide with existing checkpoint threads
        self._sync_counters_with_checkpoints(checkpointer)

    def _sync_counters_with_checkpoints(self, checkpointer) -> None:
        """Ensure session counters are higher than any existing checkpoint thread."""
        if checkpointer is None:
            return
        try:
            import sqlite3
            # Find the DB path from the checkpointer's connection
            db_path = Path(self._data_dir, "checkpoints.db")
            if not db_path.exists():
                return
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT thread_id FROM checkpoints")
            for (thread_id,) in cur.fetchall():
                parts = thread_id.rsplit("_s", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    base_key = parts[0]
                    existing = int(parts[1])
                    current = self._session_counters.get(base_key, 0)
                    if existing >= current:
                        self._session_counters[base_key] = existing + 1
                        self._session_store.set(base_key, existing + 1)
                        logger.info("Session counter synced: %s -> s%d (was %d)", base_key, existing + 1, current)
            conn.close()
        except Exception as e:
            logger.warning("Failed to sync session counters with checkpoints: %s", e)

    def _load_allowed_users(self) -> dict[str, list[str]]:
        """Load allowed users from channel configs."""
        result: dict[str, list[str]] = {}
        tg = self._config.channels.telegram
        if tg.allowed_users:
            result["telegram"] = [str(u) for u in tg.allowed_users]
        return result

    def get_thread_id(self, channel: str, chat_id: str) -> str:
        """Map channel+chat to a LangGraph thread_id."""
        key = f"{channel}_{chat_id}"
        counter = self._session_counters.get(key, 0)
        if counter > 0:
            return f"{key}_s{counter}"
        return key

    def reset_session(self, channel: str, chat_id: str) -> None:
        """Reset session for a chat (called by /new command)."""
        key = f"{channel}_{chat_id}"
        self._session_counters[key] = self._session_counters.get(key, 0) + 1
        self._session_store.set(key, self._session_counters[key])
        logger.info("Session reset: %s -> s%d", key, self._session_counters[key])

    def is_user_allowed(self, channel: str, user_id: str) -> bool:
        """Check if user is in the allowlist (empty = allow all)."""
        allowed = self._allowed_users.get(channel, [])
        if not allowed:
            return True
        return user_id in allowed

    def should_respond(self, msg: IncomingMessage, trigger: str) -> tuple[bool, str]:
        """Check if we should respond and extract the clean message text.

        Returns:
            (should_respond, cleaned_text)
        """
        text = msg.text.strip()

        # Private chat: always respond
        if msg.is_private:
            return True, text

        # Group chat: check trigger
        trigger_lower = trigger.lower()
        text_lower = text.lower()

        if text_lower.startswith(trigger_lower):
            cleaned = text[len(trigger):].strip()
            return True, cleaned

        return False, text

    async def handle_message(self, msg: IncomingMessage, channel_config: TelegramChannelConfig) -> Optional[AgentResponse]:
        """Process an incoming message and return the agent's structured response."""
        # User allowlist check
        if not self.is_user_allowed(msg.channel, msg.user_id):
            logger.warning("Blocked message from unauthorized user: %s/%s", msg.channel, msg.user_id)
            return None

        # Handle session reset
        if msg.reset_session:
            self.reset_session(msg.channel, msg.chat_id)
            return None

        # Trigger check
        trigger = channel_config.trigger
        should_respond, clean_text = self.should_respond(msg, trigger)
        if not should_respond:
            return None

        if not clean_text and not msg.image_base64:
            return None

        # Thread ID for LangGraph persistence
        thread_id = self.get_thread_id(msg.channel, msg.chat_id)

        # Set context so schedule_task knows where to send results
        set_current_context(msg.channel, msg.chat_id)

        # Format user message with context
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        formatted = f"[{now}] [{msg.user_name}]: {clean_text}"

        # Log incoming
        self._log_message(thread_id, "user", clean_text, msg)

        logger.info("Processing: channel=%s chat=%s user=%s thread=%s",
                     msg.channel, msg.chat_id, msg.user_name, thread_id)

        # Build message content (multimodal if image present)
        if msg.image_base64:
            content = [
                {"type": "text", "text": formatted},
                {"type": "image_url", "image_url": {
                    "url": f"data:{msg.image_mime_type};base64,{msg.image_base64}",
                }},
            ]
        else:
            content = formatted

        # Invoke agent
        try:
            result = await self._agent.ainvoke(
                {"messages": [{"role": "user", "content": content}]},
                config={"configurable": {"thread_id": thread_id}},
            )
            agent_resp = extract_agent_response(result)
        except Exception as e:
            logger.exception("Agent error for thread %s", thread_id)
            agent_resp = AgentResponse(text="Sorry, I encountered an error. Please try again.")

        # Log response
        self._log_message(thread_id, "assistant", agent_resp.text, msg)

        return agent_resp

    def _log_message(self, thread_id: str, role: str, content: str, msg: IncomingMessage) -> None:
        """Append message to JSONL session log."""
        sessions_dir = Path(self._data_dir, "sessions")
        sessions_dir.mkdir(parents=True, exist_ok=True)

        log_path = sessions_dir / f"{thread_id}.jsonl"
        entry = {
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
            "channel": msg.channel,
            "user_id": msg.user_id if role == "user" else None,
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to log message: %s", e)
