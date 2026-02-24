---
title: Code Conventions
---

# Code Conventions

This page documents the coding standards and patterns used throughout CianaParrot. Following these conventions keeps the codebase consistent and makes contributions easier to review.

---

## Type Hints

Type hints are used throughout the codebase. All function signatures, return types, and class attributes should be annotated.

```python
# Good
async def send(self, chat_id: str, text: str, *, reply_to_message_id: Optional[str] = None) -> Optional[SendResult]:
    ...

# Bad -- missing type hints
async def send(self, chat_id, text, reply_to_message_id=None):
    ...
```

!!! note "Type hint style"
    - Use `Optional[str]` for values that may be `None`
    - Use lowercase generics for built-in types: `list[str]`, `dict[str, int]`, `tuple[int, ...]`
    - Import from `typing` when needed: `Optional`, `Any`, `Protocol`

---

## Pydantic v2 for Configuration

All configuration validation uses **Pydantic v2** models. Config sections are defined as `BaseModel` subclasses with typed fields and defaults.

```python title="src/config.py (pattern)"
from pydantic import BaseModel, Field


class WebConfig(BaseModel):
    """Web search and fetch configuration."""
    search_provider: str = "brave"
    search_api_key: str = ""
    fetch_timeout: int = 30
    max_results: int = 5
```

!!! warning "Never use dict access for config"
    Always use attribute access (`config.web.search_provider`), never dict-style access (`config["web"]["search_provider"]`). Pydantic models provide type safety and IDE autocompletion.

---

## Async-First

All I/O operations use `async def`. CianaParrot runs on a single asyncio event loop shared by all channels, the scheduler, and the agent.

```python
# Good -- async I/O
async def fetch_url(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text

# Bad -- blocking I/O on the event loop
def fetch_url(url: str) -> str:
    response = requests.get(url)  # blocks the entire bot
    return response.text
```

!!! tip "If you must call blocking code"
    Use `asyncio.to_thread()` to run blocking functions in a thread pool:
    ```python
    result = await asyncio.to_thread(blocking_function, arg1, arg2)
    ```

---

## Imports

Use **relative imports** within the `src/` package:

```python
# Good -- relative imports within src/
from .config import AppConfig
from .channels.base import AbstractChannel, IncomingMessage
from ..tools.web import init_web_tools

# Bad -- absolute imports for internal modules
from src.config import AppConfig
```

!!! info "Exception"
    Test files use absolute imports (`from src.config import AppConfig`) since they live outside the `src/` package.

---

## Tool Pattern

Agent-callable tools use the `@tool` decorator from `langchain_core.tools`. Tools follow the **module-level config pattern**: an `init_*()` function sets module-level globals at startup, and `@tool`-decorated functions read those globals at call time.

```python title="src/tools/example.py (pattern)"
"""Example tool module."""

import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Module-level state, set by init_example_tools()
_api_key: str = ""
_timeout: int = 30


def init_example_tools(api_key: str, timeout: int = 30) -> None:
    """Initialize module-level config. Called once at startup."""
    global _api_key, _timeout
    _api_key = api_key
    _timeout = timeout


@tool
def example_search(query: str) -> str:
    """Search for something using the example API.

    Args:
        query: The search query string.

    Returns:
        Search results as a formatted string.
    """
    if not _api_key:
        return "Error: example tool not configured"
    # ... implementation using _api_key and _timeout
```

!!! note "Tool docstrings matter"
    The docstring of a `@tool` function is what the LLM sees when deciding whether to call the tool. Write clear, descriptive docstrings that explain what the tool does, what arguments it expects, and what it returns.

---

## Logging

Use `logging.getLogger(__name__)` for all logging. Never use `print()`.

```python
import logging

logger = logging.getLogger(__name__)

# Good
logger.info("Channel started: %s", self.name)
logger.warning("Message too long, chunking at %d chars", max_len)
logger.error("Failed to send message: %s", exc)

# Bad
print("Channel started")
print(f"Error: {exc}")
```

| Level | Use For |
|-------|---------|
| `debug` | Detailed diagnostic information (message payloads, internal state) |
| `info` | Normal operations (startup, shutdown, task execution) |
| `warning` | Recoverable problems (missing optional config, retry attempts) |
| `error` | Failures that affect functionality (API errors, send failures) |

---

## Data Containers

Use **dataclasses** for simple data containers that hold structured data without validation logic:

```python
from dataclasses import dataclass
from typing import Optional


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
```

Key dataclasses in the codebase: `IncomingMessage`, `SendResult`, `GatewayResult`, `CCResponse`.

---

## Interfaces

Use **Protocol classes** for interfaces where multiple implementations are expected:

```python
from typing import Protocol


class ModeHandler(Protocol):
    """Protocol for channel mode handlers."""

    async def handle_command(self, chat_id: str, args: str) -> None: ...
    async def handle_message(self, chat_id: str, text: str) -> Optional[str]: ...
    def is_active(self, chat_id: str) -> bool: ...
```

This enables duck typing -- any class that implements the required methods satisfies the protocol without explicit inheritance.

---

## Error Handling

- **Raise specific exceptions** for errors that callers should handle.
- **Log warnings** for recoverable problems.
- **Never silently swallow exceptions** -- at minimum, log them.

```python
# Good -- specific exception with context
if not config.channels.telegram.token:
    raise ValueError("Telegram bot token is required but not configured")

# Good -- log and continue for recoverable errors
try:
    await self.send(chat_id, response_text)
except TelegramError as exc:
    logger.warning("Failed to send message to %s: %s", chat_id, exc)

# Bad -- bare except that hides problems
try:
    result = await dangerous_operation()
except:
    pass
```

---

## File Structure

One module per concern. Keep files focused on a single responsibility.

| Principle | Example |
|-----------|---------|
| One channel per package | `src/channels/telegram/`, `src/channels/discord/` |
| One bridge per package | `src/gateway/bridges/claude_code/`, `src/gateway/bridges/spotify/` |
| One tool module per domain | `src/tools/web.py`, `src/tools/cron.py`, `src/tools/host.py` |
| Config models together | All Pydantic models in `src/config.py` |

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Functions and variables | `snake_case` | `handle_message`, `chat_id` |
| Classes | `PascalCase` | `TelegramChannel`, `AppConfig` |
| Constants | `UPPER_CASE` | `MAX_MESSAGE_LENGTH`, `DEFAULT_TIMEOUT` |
| Private attributes | Leading underscore | `_callback`, `_client` |
| Module-level config globals | Leading underscore | `_api_key`, `_gateway_client` |
| Test functions | `test_` prefix with descriptive name | `test_group_message_without_trigger` |

---

## Summary

| Convention | Rule |
|-----------|------|
| Type hints | Always annotate function signatures and return types |
| Config | Pydantic v2 models, attribute access only |
| I/O | `async def` for everything; `asyncio.to_thread()` for blocking calls |
| Imports | Relative within `src/`, absolute in tests |
| Tools | `@tool` decorator + module-level config pattern |
| Logging | `logging.getLogger(__name__)`, never `print()` |
| Data | Dataclasses for containers, Protocols for interfaces |
| Errors | Specific exceptions, log warnings for recoverable issues |
| Naming | `snake_case` functions, `PascalCase` classes, `UPPER_CASE` constants |
