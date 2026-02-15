"""Abstract base class for channel adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional


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


class AbstractChannel(ABC):
    """Base class for all channel adapters."""

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """Start receiving messages (non-blocking)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the channel."""
        ...

    @abstractmethod
    async def send(self, chat_id: str, text: str) -> None:
        """Send a text message to a chat."""
        ...

    @abstractmethod
    async def send_file(self, chat_id: str, path: str, caption: str = "") -> None:
        """Send a file to a chat."""
        ...

    def on_message(self, callback: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        """Register the message handler callback."""
        self._callback = callback
