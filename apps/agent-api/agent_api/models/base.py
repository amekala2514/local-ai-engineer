"""Abstract base class for model clients."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class ChatResponse:
    """Response from a non-streaming chat request."""

    content: str
    model: str
    finish_reason: str | None = None


@dataclass
class ChatChunk:
    """A single chunk from a streaming chat request."""

    content: str  # The new text in this chunk (may be empty on the final chunk)
    model: str
    done: bool = False
    finish_reason: str | None = None


class ModelClient(ABC):
    """Abstract interface every model backend must implement."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Non-streaming chat completion."""
        raise NotImplementedError

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Streaming chat completion - yields ChatChunks as they arrive."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is reachable and ready."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources."""
        raise NotImplementedError
