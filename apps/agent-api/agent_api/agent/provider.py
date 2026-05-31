"""ModelProvider — the provider-agnostic seam. Each implementation normalizes
its vendor's wire format into the canonical types (types.py).

OllamaProvider does DUAL EXTRACTION because Ollama's tool-call output is
model-dependent (verified empirically):
  - llama3.1:8b      -> native message.tool_calls  (clean)
  - qwen2.5-coder:14b -> JSON object in message.content (no native field)
The provider tries the native field first, then falls back to parsing a JSON
tool-call object out of content. Downstream (loop/gate/tools) never sees this —
they get canonical ToolCalls regardless of model.

Anthropic/OpenAI providers are later implementations of the same protocol.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Protocol

import httpx

from agent_api.agent.types import ToolDescriptor, ToolCall, ToolCallResult, ProviderResponse
from agent_api.settings import settings


class ModelProvider(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDescriptor],
    ) -> ProviderResponse: ...


def _descriptors_to_ollama(tools: list[ToolDescriptor]) -> list[dict[str, Any]]:
    """Canonical descriptors -> Ollama/OpenAI tools format."""
    return [
        {"type": "function",
         "function": {"name": t.name, "description": t.description, "parameters": t.params}}
        for t in tools
    ]


def _try_parse_content_toolcall(content: str) -> dict[str, Any] | None:
    """Fallback: some models emit a tool call as a JSON object in content
    instead of the native tool_calls field. Try to extract {name, arguments}.
    Returns the parsed dict or None if content isn't a tool-call JSON."""
    if not content:
        return None
    text = content.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    # Must look like a JSON object to bother.
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    # Accept {"name":..., "arguments":{...}} shape.
    if isinstance(obj, dict) and "name" in obj and isinstance(obj.get("arguments", {}), dict):
        return {"name": obj["name"], "arguments": obj.get("arguments", {})}
    return None


class OllamaProvider(ModelProvider):
    def __init__(self, model: str = "llama3.1:8b", host: str | None = None) -> None:
        self._model = model
        self._host = host or "http://127.0.0.1:11434"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDescriptor],
    ) -> ProviderResponse:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": messages,
            "tools": _descriptors_to_ollama(tools),
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._host}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        calls: list[ToolCall] = []

        # Path 1: native tool_calls (llama3.1 style)
        native = msg.get("tool_calls") or []
        for tc in native:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):  # some providers stringify args
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            calls.append(ToolCall(
                call_id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                name=fn.get("name", ""),
                args=args if isinstance(args, dict) else {},
            ))

        # Path 2: fallback — JSON tool-call in content (qwen2.5-coder style)
        if not calls:
            parsed = _try_parse_content_toolcall(msg.get("content", ""))
            if parsed:
                calls.append(ToolCall(
                    call_id=f"call_{uuid.uuid4().hex[:8]}",
                    name=parsed["name"],
                    args=parsed["arguments"],
                ))

        if calls:
            return ProviderResponse(tool_calls=calls)
        # No tool calls -> final text answer. Guard against explicit null content.
        return ProviderResponse(text=msg.get("content") or "")
