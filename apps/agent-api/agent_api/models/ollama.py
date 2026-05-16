"""Ollama model client.

Talks to a local (or remote) Ollama instance via its HTTP API.
"""

import httpx

from agent_api.models.base import ChatMessage, ChatResponse, ModelClient


class OllamaClient(ModelClient):
    """Model client backed by an Ollama server."""

    def __init__(self, host: str, timeout: float = 120.0) -> None:
        """Initialize the client.

        Args:
            host: Base URL of the Ollama server (e.g., http://localhost:11434).
            timeout: Per-request timeout in seconds. Generous default because
                local model inference can take a while.
        """
        self._host = host.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=timeout,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Send a chat request to Ollama and return the response."""
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        return ChatResponse(
            content=data["message"]["content"],
            model=data.get("model", model),
            finish_reason=data.get("done_reason"),
        )

    async def health_check(self) -> bool:
        """Return True if Ollama responds to a basic request."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()