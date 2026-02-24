---
title: Add a Channel
---

# Add a Channel

This guide walks you through creating a new channel adapter so CianaParrot can communicate via a new messaging platform (Discord, Slack, a webhook endpoint, etc.).

---

## Introduction

Channels are the entry and exit points for user messages. Each channel implements `AbstractChannel`, which defines a standard interface for starting/stopping the listener, sending messages, and registering a callback for incoming messages. The router doesn't know or care which channel a message came from -- it receives a normalized `IncomingMessage` dataclass.

---

## Prerequisites

- A working CianaParrot installation ([Installation Guide](../getting-started/installation.md))
- Python 3.13+
- The client library for your target platform (e.g., `discord.py`, `slack-sdk`)

---

## Step 1: Understand the Base Classes

The channel system is built on three dataclasses and one abstract class in `src/channels/base.py`:

```python title="src/channels/base.py (reference)"
@dataclass
class SendResult:
    """Result of a send operation."""
    message_id: Optional[str] = None


@dataclass
class IncomingMessage:
    """Normalized incoming message from any channel."""
    channel: str                              # channel name (e.g. "telegram", "discord")
    chat_id: str                              # unique chat/conversation identifier
    user_id: str                              # unique user identifier
    user_name: str                            # display name
    text: str                                 # message text
    is_private: bool = False                  # True for DMs
    reply_to: Optional[str] = None            # message ID being replied to
    file_path: Optional[str] = None           # path to an attached file
    reset_session: bool = False               # True for /new-style resets
    message_id: Optional[str] = None          # platform message ID
    image_base64: Optional[str] = None        # base64-encoded photo for vision LLMs
    image_mime_type: str = "image/jpeg"       # MIME type for the image


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

    def on_message(self, callback): ...  # registers self._callback
```

!!! info "Key contract"
    Your channel must normalize every incoming message into an `IncomingMessage` and call `self._callback(msg)`. The callback returns an `AgentResponse` (or `None`) that your channel sends back to the user.

---

## Step 2: Create the Channel Package

Create a new directory under `src/channels/`:

```
src/channels/discord/
    __init__.py
    channel.py
```

```python title="src/channels/discord/__init__.py"
"""Discord channel package."""

from .channel import DiscordChannel

__all__ = ["DiscordChannel"]
```

---

## Step 3: Implement the Channel Adapter

```python title="src/channels/discord/channel.py"
"""Discord channel adapter."""

import asyncio
import logging
from typing import Optional

from ..base import AbstractChannel, IncomingMessage, SendResult

logger = logging.getLogger(__name__)


class DiscordChannel(AbstractChannel):
    """Discord channel adapter."""

    name = "discord"

    def __init__(self, config):
        self._token = config.token
        self._callback = None
        self._client = None  # your Discord client instance

    async def start(self) -> None:
        """Start the Discord bot (non-blocking)."""
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message):
            if message.author.bot:
                return
            await self._handle_message(message)

        # Start in background so it doesn't block the event loop
        asyncio.create_task(self._client.start(self._token))
        logger.info("Discord channel started")

    async def stop(self) -> None:
        """Gracefully disconnect."""
        if self._client:
            await self._client.close()
            logger.info("Discord channel stopped")

    async def send(self, chat_id: str, text: str, *,
                   reply_to_message_id: Optional[str] = None,
                   disable_notification: bool = False) -> Optional[SendResult]:
        """Send a text message to a Discord channel."""
        if not self._client:
            return None
        channel = self._client.get_channel(int(chat_id))
        if not channel:
            logger.warning("Discord channel %s not found", chat_id)
            return None
        msg = await channel.send(text)
        return SendResult(message_id=str(msg.id))

    async def send_file(self, chat_id: str, path: str, caption: str = "") -> None:
        """Send a file to a Discord channel."""
        import discord
        if not self._client:
            return
        channel = self._client.get_channel(int(chat_id))
        if channel:
            await channel.send(content=caption, file=discord.File(path))

    async def _handle_message(self, message) -> None:
        """Normalize a Discord message and pass to the callback."""
        if not self._callback:
            return

        is_private = message.guild is None

        msg = IncomingMessage(
            channel=self.name,
            chat_id=str(message.channel.id),
            user_id=str(message.author.id),
            user_name=message.author.display_name,
            text=message.content,
            is_private=is_private,
            message_id=str(message.id),
        )

        agent_resp = await self._callback(msg)
        if agent_resp and agent_resp.text:
            await self.send(str(message.channel.id), agent_resp.text)
```

!!! warning "Event loop sharing"
    CianaParrot runs a single asyncio event loop for all channels. Your channel must not call blocking APIs on the main loop. Use `asyncio.create_task()` or `asyncio.to_thread()` for blocking operations.

---

## Step 4: Add Configuration

You need a config model for your channel. See [Add a Config Section](add-config-section.md) for details. In brief:

=== "Config model"

    ```python title="src/config.py (add to existing file)"
    class DiscordChannelConfig(BaseModel):
        enabled: bool = False
        token: str = ""
        trigger: str = "@Ciana"
    ```

=== "Add to ChannelsConfig"

    ```python title="src/config.py (modify ChannelsConfig)"
    class ChannelsConfig(BaseModel):
        telegram: TelegramChannelConfig = Field(default_factory=TelegramChannelConfig)
        discord: DiscordChannelConfig = Field(default_factory=DiscordChannelConfig)
    ```

=== "YAML section"

    ```yaml title="config.yaml"
    channels:
      discord:
        enabled: true
        token: "${DISCORD_BOT_TOKEN}"
        trigger: "@Ciana"
    ```

---

## Step 5: Wire It Up in main.py

Follow the same pattern used for the Telegram channel:

```python title="src/main.py (add after Telegram block)"
from .channels.discord import DiscordChannel

# ... inside main(), after the Telegram channel block:

if config.channels.discord.enabled:
    discord_config = config.channels.discord
    discord_ch = DiscordChannel(discord_config)

    async def discord_callback(msg):
        return await router.handle_message(msg, discord_config)

    discord_ch.on_message(discord_callback)
    channels.append(discord_ch)
    logger.info("Discord channel configured")
```

!!! note "Channel config type"
    The `router.handle_message()` second argument is currently typed as `TelegramChannelConfig`. If your channel config has the same fields (`trigger`, `allowed_users`), it will work. Otherwise, consider refactoring the router to accept a protocol or base channel config type.

---

## Step 6: Test It

### Unit test for message normalization

```python title="tests/test_discord_channel.py"
import pytest
from src.channels.base import IncomingMessage


def test_incoming_message_fields():
    """Verify IncomingMessage can be constructed with Discord-specific values."""
    msg = IncomingMessage(
        channel="discord",
        chat_id="123456789",
        user_id="987654321",
        user_name="TestUser",
        text="Hello, Ciana!",
        is_private=True,
        message_id="111222333",
    )
    assert msg.channel == "discord"
    assert msg.is_private is True
    assert msg.image_base64 is None
```

### Integration test

1. Set your Discord bot token in `.env`
2. Enable the channel in `config.yaml`
3. Run `make up` and send a message to your Discord bot
4. Check logs with `make logs`

---

## Summary

| Step | What You Did |
|------|-------------|
| 1 | Reviewed `AbstractChannel`, `IncomingMessage`, and `SendResult` |
| 2 | Created `src/channels/discord/` package |
| 3 | Implemented all abstract methods |
| 4 | Added config model and YAML section |
| 5 | Wired the channel in `main.py` |
| 6 | Wrote tests and verified end-to-end |
