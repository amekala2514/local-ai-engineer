"""Canonical agent types — the provider-agnostic contract.

These are what the loop, registry, gate-bridge, and tools speak. Every
ModelProvider normalizes ITS wire format (Ollama native tool_calls, Ollama
JSON-in-content, Anthropic content blocks, OpenAI tool_calls) into these, so
nothing downstream of the provider knows which model or vendor produced a call.

Pure data — no provider imports, no Ollama, no Phase C imports. The stable seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDescriptor:
    """A tool advertised to the model. params is a JSON Schema object (the
    format all of Ollama/OpenAI/Anthropic accept). Local tools and MCP tools
    both present as this."""
    name: str
    description: str
    params: dict[str, Any]   # JSON Schema: {"type":"object","properties":{...},"required":[...]}


@dataclass(frozen=True)
class ToolCall:
    """A model's request to call a tool, normalized from any provider's format.
    call_id ties a result back to a call (some providers require it)."""
    call_id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolCallResult:
    """The outcome of executing a ToolCall, to be fed back to the model.
    `content` is what the model sees; `ok` and `decision` are for the loop's
    own bookkeeping/logging. decision is the gate's allow/approve/deny."""
    call_id: str
    name: str
    content: str
    ok: bool
    decision: str            # allow / approve / deny / error
    audit_id: int | None = None


@dataclass(frozen=True)
class ProviderResponse:
    """What a ModelProvider returns from one turn: EITHER a final text answer
    OR a set of tool calls to execute. If tool_calls is non-empty, the loop
    executes them and continues; otherwise `text` is the final answer."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def is_final(self) -> bool:
        return not self.tool_calls
