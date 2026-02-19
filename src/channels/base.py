"""Abstract base class for channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

if TYPE_CHECKING:
    from ..agent_response import AgentResponse


@dataclass
class SendResult:
    """Result of a send operation."""
    message_id: Optional[str] = None


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
    async def send(self, chat_id: str, text: str, *,
                   reply_to_message_id: Optional[str] = None,
                   disable_notification: bool = False) -> Optional[SendResult]:
        """Send a text message to a chat."""
        ...

    @abstractmethod
    async def send_file(self, chat_id: str, path: str, caption: str = "") -> None:
        """Send a file to a chat."""
        ...

    def on_message(self, callback: Callable[[IncomingMessage], Awaitable[Optional["AgentResponse"]]]) -> None:
        """Register the message handler callback."""
        self._callback = callback
