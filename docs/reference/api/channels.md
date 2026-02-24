# Channels API

::: src.channels.base
::: src.channels.telegram.channel

---

## Overview

The channels layer provides a pluggable adapter pattern for messaging platforms. Every channel implements `AbstractChannel`, normalizes incoming messages into `IncomingMessage` dataclasses, and sends responses back through `send()`.

**Source files:**

- `src/channels/base.py` -- abstract base class and dataclasses
- `src/channels/telegram/channel.py` -- Telegram adapter and mode handler protocol

---

## `SendResult`

:octicons-file-code-16: `src/channels/base.py`

Dataclass returned by `send()` to communicate the platform message ID back to the caller.

```python
@dataclass
class SendResult:
    """Result of a send operation."""
    message_id: Optional[str] = None
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message_id` | `Optional[str]` | `None` | Platform-specific message ID of the sent message |

---

## `IncomingMessage`

:octicons-file-code-16: `src/channels/base.py`

Normalized incoming message from any channel. This is the universal representation that the router and agent receive, regardless of the originating platform.

```python
@dataclass
class IncomingMessage:
    """Normalized incoming message from any channel."""
    channel: str
    chat_id: str
    user_id: str
    user_name: str
    text: str
    is_private: bool = False
    reply_to: Optional[str] = None
    file_path: Optional[str] = None
    reset_session: bool = False
    message_id: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime_type: str = "image/jpeg"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channel` | `str` | *required* | Channel identifier (e.g. `"telegram"`) |
| `chat_id` | `str` | *required* | Platform-specific chat/conversation ID |
| `user_id` | `str` | *required* | Platform-specific user ID |
| `user_name` | `str` | *required* | Human-readable display name |
| `text` | `str` | *required* | Message text content |
| `is_private` | `bool` | `False` | Whether this is a direct/private message |
| `reply_to` | `Optional[str]` | `None` | ID of the message being replied to |
| `file_path` | `Optional[str]` | `None` | Path to an attached file (if any) |
| `reset_session` | `bool` | `False` | Set to `True` by `/new` command to trigger session reset |
| `message_id` | `Optional[str]` | `None` | Platform-specific message ID |
| `image_base64` | `Optional[str]` | `None` | Base64-encoded photo for vision LLMs |
| `image_mime_type` | `str` | `"image/jpeg"` | MIME type of the image; channels should override as needed |

---

## `AbstractChannel`

:octicons-file-code-16: `src/channels/base.py`

Abstract base class that all channel adapters must implement. Defines the contract for receiving and sending messages.

```python
class AbstractChannel(ABC):
    """Base class for all channel adapters."""

    name: str = "base"

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, chat_id: str, text: str, *,
                   reply_to_message_id: Optional[str] = None,
                   disable_notification: bool = False) -> Optional[SendResult]: ...

    @abstractmethod
    async def send_file(self, chat_id: str, path: str, caption: str = "") -> None: ...

    def on_message(self, callback: Callable[[IncomingMessage], Awaitable[Optional["AgentResponse"]]]) -> None: ...
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Channel identifier. Subclasses must set this (e.g. `"telegram"`). |

### Methods

#### `start() -> None` {: #abstractchannel-start }

Start receiving messages. Must be non-blocking -- implementation should use polling or webhooks in the background.

#### `stop() -> None` {: #abstractchannel-stop }

Gracefully stop the channel. Drain any active tasks before returning.

#### `send(chat_id, text, *, reply_to_message_id=None, disable_notification=False) -> Optional[SendResult]` {: #abstractchannel-send }

Send a text message to a chat.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chat_id` | `str` | *required* | Target chat ID |
| `text` | `str` | *required* | Message text |
| `reply_to_message_id` | `Optional[str]` | `None` | Thread the reply to this message |
| `disable_notification` | `bool` | `False` | Send silently |

**Returns:** `Optional[SendResult]` -- the sent message ID, or `None` on failure.

#### `send_file(chat_id, path, caption="") -> None` {: #abstractchannel-send-file }

Send a file to a chat.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chat_id` | `str` | *required* | Target chat ID |
| `path` | `str` | *required* | Filesystem path to the file |
| `caption` | `str` | `""` | Optional caption |

#### `on_message(callback) -> None` {: #abstractchannel-on-message }

Register the message handler callback. The callback receives an `IncomingMessage` and returns an optional `AgentResponse`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `callback` | `Callable[[IncomingMessage], Awaitable[Optional[AgentResponse]]]` | Async handler function |

```python
# Registration example from src/main.py
channel.on_message(lambda msg: router.handle_message(msg, channel_config))
```

---

## `ModeHandler`

:octicons-file-code-16: `src/channels/telegram/channel.py`

Runtime-checkable protocol for pluggable mode handlers. Mode handlers intercept messages in private chats when a mode is active (e.g. Claude Code mode). Used by `TelegramChannel` to delegate message processing.

```python
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
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Mode identifier (e.g. `"claude_code"`) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `register()` | `None` | Called during `TelegramChannel.start()` to register Telegram handlers |
| `is_active(user_id)` | `bool` | Whether mode is currently active for a given user |
| `match_button(text)` | `str | None` | Check if text matches a ReplyKeyboard button. Returns `"exit"`, `"conversations"`, or `None`. |
| `process_message(user_id, text, chat_id)` | `None` | Process a message within the active mode |
| `exit_with_keyboard_remove(user_id, chat_id)` | `None` | Exit mode and remove the custom keyboard |
| `show_menu(user_id, chat_id)` | `None` | Show the mode's conversation/project menu |
| `get_commands()` | `list[tuple[str, str]]` | Return bot command tuples `(command, description)` for registration |
| `get_help_lines()` | `list[str]` | Return help text lines for the `/help` command |

---

## `ModeHandlerFactory`

:octicons-file-code-16: `src/channels/telegram/channel.py`

Type alias for factories that create mode handlers. Receives the Telegram `Application` and a `send` function, returns a `ModeHandler`.

```python
ModeHandlerFactory = Callable[[Application, Callable], "ModeHandler"]
```

---

## `TelegramChannel`

:octicons-file-code-16: `src/channels/telegram/channel.py`

Concrete `AbstractChannel` implementation for Telegram using `python-telegram-bot` v22+. Uses manual polling (no `run_polling()`) to share the asyncio event loop with the rest of the application.

```python
class TelegramChannel(AbstractChannel):
    name = "telegram"

    def __init__(self, config: TelegramChannelConfig): ...
    def register_mode_handler(self, factory: ModeHandlerFactory) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, chat_id, text, *, reply_to_message_id=None,
                   reply_markup=None, disable_notification=False) -> Optional[SendResult]: ...
    async def send_file(self, chat_id, path, caption="") -> None: ...
```

### Constructor

```python
def __init__(self, config: TelegramChannelConfig):
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `TelegramChannelConfig` | Telegram channel configuration (token, trigger, allowed users) |

### `register_mode_handler(factory)` {: #telegramchannel-register-mode-handler }

Register a mode handler factory. Must be called **before** `start()`. The factory is invoked during `start()` with `(app, send_fn)` and must return a `ModeHandler` instance.

```python
def register_mode_handler(self, factory: ModeHandlerFactory) -> None:
    """Register a mode handler factory. Called before start()."""
    self._mode_handler_factories.append(factory)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `factory` | `ModeHandlerFactory` | `Callable[[Application, Callable], ModeHandler]` |

### `send(...)` {: #telegramchannel-send }

Send a message via Telegram. Automatically converts Markdown to Telegram HTML via `md_to_telegram_html()`, then chunks at 4096 characters. Falls back to plain text if HTML parsing fails.

```python
async def send(self, chat_id: str, text: str, *,
               reply_to_message_id: Optional[str] = None,
               reply_markup: Optional[object] = None,
               disable_notification: bool = False) -> Optional[SendResult]:
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chat_id` | `str` | *required* | Target chat ID |
| `text` | `str` | *required* | Message text (Markdown) |
| `reply_to_message_id` | `Optional[str]` | `None` | Reply to this message (first chunk only) |
| `reply_markup` | `Optional[object]` | `None` | Telegram reply markup (last chunk only) |
| `disable_notification` | `bool` | `False` | Send silently |

**Returns:** `Optional[SendResult]` -- ID of the last sent message, or `None`.

### Key Implementation Details

- **Deduplication**: Tracks `update_id` in `_seen_updates` set (max 1000) to skip duplicate updates
- **Background processing**: Messages are processed via `asyncio.create_task()` for non-blocking handling
- **Mode interception**: In private chats, checks all registered mode handlers before normal processing
- **Voice/photo support**: Downloads and transcribes voice messages; downloads photos as base64 for vision LLMs
- **Graceful shutdown**: `stop()` drains all active tasks before shutting down the Telegram application
