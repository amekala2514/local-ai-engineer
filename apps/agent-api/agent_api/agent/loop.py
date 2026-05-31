"""The agent loop — provider-agnostic, gated, MCP-ready.

    answer = await run_agent(user_msg, provider, registry, audit_store)

Flow per turn:
  1. provider.chat(messages, registry.descriptors()) -> ProviderResponse
  2. if final text -> return it
  3. else execute each tool call through the registry (which self-gates), feed
     results back as tool-role messages, and loop again
A max-turns guard prevents runaway loops (small models can loop on tool calls).

D37: all registered tools auto-allow (read-only), so there's no approval pause.
D38 adds the approval interrupt for approve-required tools.

Known limitation (llama3.1:8b): small models sometimes (a) mangle tool args
(e.g. a wrong path), recovering on the next turn when the tool error is fed
back, or (b) emit a follow-up tool call as JSON embedded in prose, which the
provider's strict fallback parser does not extract (so the loop may end with
raw JSON in the answer). Both are model-quality issues, not loop/gate bugs —
the gate contains every call regardless. Mitigation is a stronger model
(qwen2.5-coder) or polish (D40), not speculative parser changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_api.agent.provider import ModelProvider
from agent_api.agent.registry import ToolRegistry
from agent_api.agent.types import ToolCall, ToolCallResult


@dataclass
class AgentTurn:
    """A record of what happened in one loop iteration (for the harness/log)."""
    tool_calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolCallResult] = field(default_factory=list)
    final_text: str | None = None


@dataclass
class AgentRun:
    answer: str
    turns: list[AgentTurn] = field(default_factory=list)
    hit_max_turns: bool = False


_SYSTEM = (
    "You are a coding assistant operating on a local repository. You have tools "
    "to read files, list directories, inspect git, and summarize the repo. Use a "
    "tool only when you need repository information to answer. When you have enough "
    "information, answer the user directly in plain text without calling a tool."
)


async def run_agent(
    user_message: str,
    provider: ModelProvider,
    registry: ToolRegistry,
    audit_store,
    max_turns: int = 6,
    system: str | None = None,
) -> AgentRun:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system or _SYSTEM},
        {"role": "user", "content": user_message},
    ]
    run = AgentRun(answer="")
    descriptors = registry.descriptors()

    for _ in range(max_turns):
        resp = await provider.chat(messages, descriptors)
        turn = AgentTurn()

        if resp.is_final:
            turn.final_text = resp.text
            run.turns.append(turn)
            run.answer = resp.text or ""
            return run

        # Execute each tool call through the registry (self-gating).
        turn.tool_calls = list(resp.tool_calls)
        # Record the assistant's tool-call turn in the message history.
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"type": "function",
                 "function": {"name": c.name, "arguments": c.args}}
                for c in resp.tool_calls
            ],
        })
        for call in resp.tool_calls:
            result = await registry.execute(call, audit_store)
            turn.results.append(result)
            # Feed the result back as a tool-role message the model can read.
            messages.append({
                "role": "tool",
                "tool_name": call.name,
                "content": result.content,
            })
        run.turns.append(turn)

    run.hit_max_turns = True
    run.answer = "(stopped: reached max tool-calling turns without a final answer)"
    return run
