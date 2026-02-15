"""Message router - trigger detection, user allowlist, thread mapping, session logging."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .channels.base import IncomingMessage
from .tools.cron import set_current_context

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages from channels to the agent."""

    def __init__(self, agent, config: dict):
        self._agent = agent
        self._config = config
        self._workspace = config["agent"]["workspace"]
        self._allowed_users = self._load_allowed_users()
        # Track session resets (channel_chatid -> counter)
        self._session_counters: dict[str, int] = {}

    def _load_allowed_users(self) -> dict[str, list[str]]:
        """Load allowed users from data/allowed_users.json."""
        path = Path("data/allowed_users.json")
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}

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

    async def handle_message(self, msg: IncomingMessage, channel_config: dict) -> Optional[str]:
        """Process an incoming message and return the agent's response."""
        # User allowlist check
        if not self.is_user_allowed(msg.channel, msg.user_id):
            logger.warning("Blocked message from unauthorized user: %s/%s", msg.channel, msg.user_id)
            return None

        # Trigger check
        trigger = channel_config.get("trigger", "@Ciana")
        should_respond, clean_text = self.should_respond(msg, trigger)
        if not should_respond:
            return None

        if not clean_text:
            return None

        # Thread ID for LangGraph persistence
        thread_id = self.get_thread_id(msg.channel, msg.chat_id)

        # Set context so schedule_task knows where to send results
        set_current_context(msg.channel, msg.chat_id)

        # Format user message with context
        formatted = f"[{msg.user_name}]: {clean_text}"

        # Log incoming
        self._log_message(thread_id, "user", clean_text, msg)

        logger.info("Processing: channel=%s chat=%s user=%s thread=%s",
                     msg.channel, msg.chat_id, msg.user_name, thread_id)

        # Invoke agent
        try:
            result = await self._agent.ainvoke(
                {"messages": [{"role": "user", "content": formatted}]},
                config={"configurable": {"thread_id": thread_id}},
            )
            response = result["messages"][-1].content
        except Exception as e:
            logger.exception("Agent error for thread %s", thread_id)
            response = f"Sorry, I encountered an error: {e}"

        # Log response
        self._log_message(thread_id, "assistant", response, msg)

        return response

    def _log_message(self, thread_id: str, role: str, content: str, msg: IncomingMessage) -> None:
        """Append message to JSONL session log."""
        sessions_dir = Path(self._workspace, "sessions")
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
