"""Abstract base class for model clients.

All concrete model backends (Ollama, vLLM, Bedrock, Vertex, etc.) inherit
from ModelClient and implement its methods. This is the single seam
that lets the rest of the application stay model-agnostic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class ChatResponse:
    """Response from a model client."""

    content: str
    model: str
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
        """Send a chat completion request and get a single response.

        Args:
            messages: Conversation history, oldest first.
            model: Name of the model to use (e.g., "llama3.1:8b").
            temperature: Sampling temperature, 0.0 to 2.0.
            max_tokens: Maximum tokens to generate, or None for the model default.

        Returns:
            A ChatResponse with the model's reply.
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is reachable and ready.

        Used by the API's health endpoint and by routing logic that needs
        to know whether a backend is available.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources (HTTP connections, etc.)."""
        raise NotImplementedError