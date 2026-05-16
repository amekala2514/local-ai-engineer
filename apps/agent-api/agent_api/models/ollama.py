"""Ollama model client - supports both non-streaming and streaming chat."""

import json
from collections.abc import AsyncIterator

import httpx

from agent_api.models.base import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    ModelClient,
)


class OllamaClient(ModelClient):
    """Model client backed by an Ollama server."""

    def __init__(self, host: str, timeout: float = 300.0) -> None:
        """Initialize the client.

        Args:
            host: Base URL of the Ollama server.
            timeout: Per-request timeout in seconds. Generous default
                because streamed responses may take a while overall.
        """
        self._host = host.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._host, timeout=timeout)

    def _build_payload(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        stream: bool,
    ) -> dict:
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Non-streaming chat."""
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=False)
        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return ChatResponse(
            content=data["message"]["content"],
            model=data.get("model", model),
            finish_reason=data.get("done_reason"),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Stream chat completion chunks as they arrive from Ollama.

        Ollama's streaming format is newline-delimited JSON: each line is
        a JSON object representing one chunk.
        """
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True)
        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = data.get("message", {}).get("content", "")
                done = bool(data.get("done", False))
                yield ChatChunk(
                    content=content,
                    model=data.get("model", model),
                    done=done,
                    finish_reason=data.get("done_reason") if done else None,
                )

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        await self._client.aclose()
