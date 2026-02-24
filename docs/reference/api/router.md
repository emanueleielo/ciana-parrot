# Router API

::: src.router

---

## Overview

The `MessageRouter` is the central message-processing pipeline. It handles user authorization, trigger detection, session management, thread ID mapping, and agent invocation. All incoming messages pass through the router before reaching the LangGraph agent.

**Source file:** `src/router.py`

---

## `MessageRouter`

:octicons-file-code-16: `src/router.py`

Routes messages from channels to the agent. Manages thread IDs for LangGraph persistence, session counters for `/new` resets, and JSONL session logging.

### Constructor

```python
class MessageRouter:
    def __init__(self, agent, config: AppConfig, checkpointer=None):
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent` | `CompiledGraph` | *required* | LangGraph agent instance (from `create_cianaparrot_agent`) |
| `config` | `AppConfig` | *required* | Full application configuration |
| `checkpointer` | `AsyncSqliteSaver | None` | `None` | Checkpoint saver for session counter sync |

**Initialization steps:**

1. Loads allowed users from channel configs
2. Initializes `JsonStore` for session counters at `{data_dir}/session_counters.json`
3. Syncs session counters with existing checkpoint thread IDs to prevent collisions

### `get_thread_id(channel, chat_id) -> str` {: #router-get-thread-id }

Map a channel and chat ID to a LangGraph `thread_id`.

```python
def get_thread_id(self, channel: str, chat_id: str) -> str:
    """Map channel+chat to a LangGraph thread_id."""
    key = f"{channel}_{chat_id}"
    counter = self._session_counters.get(key, 0)
    if counter > 0:
        return f"{key}_s{counter}"
    return key
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | `str` | Channel name (e.g. `"telegram"`) |
| `chat_id` | `str` | Platform-specific chat ID |

**Returns:** Thread ID string in the format:

- `"{channel}_{chat_id}"` -- initial session (counter = 0)
- `"{channel}_{chat_id}_s{N}"` -- after N session resets

**Examples:**

```
telegram_123456        # first session
telegram_123456_s1     # after first /new
telegram_123456_s2     # after second /new
```

### `reset_session(channel, chat_id)` {: #router-reset-session }

Reset the session for a chat. Increments the session counter and persists it to disk.

```python
def reset_session(self, channel: str, chat_id: str) -> None:
    """Reset session for a chat (called by /new command)."""
    key = f"{channel}_{chat_id}"
    self._session_counters[key] = self._session_counters.get(key, 0) + 1
    self._session_store.set(key, self._session_counters[key])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | `str` | Channel name |
| `chat_id` | `str` | Chat ID |

Called by the `/new` command handler. The next call to `get_thread_id()` for this chat will return a new thread ID with the incremented suffix.

### `is_user_allowed(channel, user_id) -> bool` {: #router-is-user-allowed }

Check if a user is in the allowlist for a given channel.

```python
def is_user_allowed(self, channel: str, user_id: str) -> bool:
    """Check if user is in the allowlist (empty = allow all)."""
    allowed = self._allowed_users.get(channel, [])
    if not allowed:
        return True
    return user_id in allowed
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | `str` | Channel name |
| `user_id` | `str` | User ID to check |

**Returns:** `True` if the user is allowed or the allowlist is empty; `False` otherwise.

### `should_respond(msg, trigger) -> tuple[bool, str]` {: #router-should-respond }

Check if the bot should respond to a message and extract the cleaned text.

```python
def should_respond(self, msg: IncomingMessage, trigger: str) -> tuple[bool, str]:
    """Check if we should respond and extract the clean message text.

    Returns:
        (should_respond, cleaned_text)
    """
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `msg` | `IncomingMessage` | Incoming message to evaluate |
| `trigger` | `str` | Trigger prefix for group chats (e.g. `"@Ciana"`) |

**Returns:** `(should_respond, cleaned_text)` tuple.

**Rules:**

- **Private chat**: always responds; returns original text
- **Group chat**: responds only if text starts with `trigger` (case-insensitive); strips the trigger prefix from the returned text

```python
# Private chat
should_respond(msg_private, "@Ciana")  # (True, "what's the weather?")

# Group chat with trigger
msg.text = "@Ciana what's the weather?"
should_respond(msg_group, "@Ciana")    # (True, "what's the weather?")

# Group chat without trigger
msg.text = "hello everyone"
should_respond(msg_group, "@Ciana")    # (False, "hello everyone")
```

### `handle_message(msg, channel_config) -> Optional[AgentResponse]` {: #router-handle-message }

Process an incoming message through the full routing pipeline and return the agent's response.

```python
async def handle_message(self, msg: IncomingMessage,
                         channel_config: TelegramChannelConfig) -> Optional[AgentResponse]:
    """Process an incoming message and return the agent's structured response."""
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `msg` | `IncomingMessage` | Normalized incoming message |
| `channel_config` | `TelegramChannelConfig` | Channel-specific config (for trigger) |

**Returns:** `Optional[AgentResponse]` -- the agent's response, or `None` if the message was filtered.

**Pipeline steps:**

1. **User allowlist check** -- blocks unauthorized users (logs warning)
2. **Session reset** -- if `msg.reset_session` is `True`, increments counter and returns `None`
3. **Trigger check** -- calls `should_respond()` with channel trigger
4. **Empty check** -- skips messages with no text and no image
5. **Thread ID** -- calls `get_thread_id()` for LangGraph persistence
6. **Context** -- calls `set_current_context()` so cron tools know the originating channel/chat
7. **Format** -- prepends `[timestamp] [username]: ` to the message
8. **Log** -- writes incoming message to JSONL session log
9. **Invoke** -- calls `agent.ainvoke()` with thread configuration
10. **Extract** -- extracts `AgentResponse` from the LangGraph result
11. **Log** -- writes response to JSONL session log

**Multimodal support:** If `msg.image_base64` is set, the message content is sent as a list with both a text block and an `image_url` block (data URI with base64-encoded image).

### Session Counter Sync

At initialization, the router scans existing checkpoint thread IDs in `checkpoints.db` to ensure session counters are higher than any existing thread. This prevents thread ID collisions after container restarts when session counter files may be stale.

```python
def _sync_counters_with_checkpoints(self, checkpointer) -> None:
    """Ensure session counters are higher than any existing checkpoint thread."""
```

### JSONL Session Logging

Every message (incoming and outgoing) is logged to `{data_dir}/sessions/{thread_id}.jsonl`:

```json
{
  "role": "user",
  "content": "what's the weather?",
  "ts": "2025-06-15T10:30:00+00:00",
  "channel": "telegram",
  "user_id": "123456"
}
```
