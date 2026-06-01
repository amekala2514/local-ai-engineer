"""The agent loop — provider-agnostic, gated, with human-in-the-loop approval.

    run = await run_agent(msg, provider, registry, store)
    if run.is_paused:
        # surface run.pending.approval to the human; get yes/no
        run = await resume_agent(run.pending, approved, provider, registry, store)
    # ... may pause again; loop until run.answer is set

Two-phase (approve-required) tools cause the loop to PAUSE: it returns an
AgentRun carrying a PendingApproval (the rich Day-30 approval payload + enough
state to resume) WITHOUT executing. The caller approves/rejects, then
resume_agent confirms-or-discards and continues. This is the human-in-the-loop
interrupt the Phase C two-phase tools were built for.

D38: write_file is the one approve-required tool. Pause-state is held in-memory
(PendingApproval carries the messages). NOTE for D39 (UI over HTTP): the Phase C
write tool's pending-write dict is in-process, so a confirm must hit the same
process that proposed. A durable pending-store is the D39 requirement; for this
harness, in-process is fine.

D37 limitation note (llama3.1:8b arg-mangling / prose-embedded JSON) still
applies; the gate contains every call regardless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_api.agent.provider import ModelProvider
from agent_api.agent.registry import ToolRegistry
from agent_api.agent.types import ToolCall, ToolCallResult
from agent_api.policy.approval import ApprovalRequest
from agent_api.policy.engine import Decision


@dataclass
class AgentTurn:
    tool_calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolCallResult] = field(default_factory=list)
    final_text: str | None = None


@dataclass
class PendingApproval:
    """The loop paused here, awaiting a human decision on a two-phase tool."""
    approval: ApprovalRequest        # rich payload: path, content, rollback, etc.
    audit_id: int
    tool_name: str
    call_id: str
    tool_args: dict[str, Any]        # the staged call's args (e.g. write path+content)
    messages: list[dict[str, Any]]   # conversation state to resume from
    turns_used: int                  # budget already consumed
    max_turns: int


@dataclass
class AgentRun:
    answer: str | None = None
    pending: PendingApproval | None = None
    turns: list[AgentTurn] = field(default_factory=list)
    hit_max_turns: bool = False

    @property
    def is_paused(self) -> bool:
        return self.pending is not None


_SYSTEM = (
    "You are a coding assistant operating on a local repository. You have tools "
    "to read files, list directories, inspect git, summarize the repo, and write "
    "files. Use a tool only when needed. Writing a file requires human approval. "
    "When you have enough information, answer directly in plain text without "
    "calling a tool."
)


def _assistant_toolcall_msg(calls: list[ToolCall]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"type": "function", "function": {"name": c.name, "arguments": c.args}}
            for c in calls
        ],
    }


def _tool_result_msg(call: ToolCall, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_name": call.name, "content": content}


async def _drive(
    messages: list[dict[str, Any]],
    provider: ModelProvider,
    registry: ToolRegistry,
    audit_store,
    max_turns: int,
    turns_used: int,
    run: AgentRun,
) -> AgentRun:
    """Run turns until a final answer, a pause (two-phase approve), or max_turns."""
    descriptors = registry.descriptors()

    while turns_used < max_turns:
        turns_used += 1
        resp = await provider.chat(messages, descriptors)
        turn = AgentTurn()

        if resp.is_final:
            turn.final_text = resp.text
            run.turns.append(turn)
            run.answer = resp.text or ""
            return run

        turn.tool_calls = list(resp.tool_calls)
        # Record the assistant's tool-call turn BEFORE executing, so the message
        # history is consistent across any pause boundary.
        messages.append(_assistant_toolcall_msg(resp.tool_calls))

        for call in resp.tool_calls:
            if registry.is_two_phase(call.name):
                # Propose: gate + stage, execute NOTHING.
                tr = await registry.propose(call, audit_store)
                if tr is None:
                    messages.append(_tool_result_msg(call, f"tool {call.name} not available"))
                    continue
                if tr.decision == Decision.DENY.value or tr.decision == "deny":
                    # Denied — feed back to the model, keep going.
                    res = ToolCallResult(call.call_id, call.name, tr.detail, False, "deny", tr.audit_id)
                    turn.results.append(res)
                    messages.append(_tool_result_msg(call, f"denied: {tr.detail}"))
                    continue
                # APPROVE -> pause. Return the rich payload + resume state.
                run.turns.append(turn)
                run.pending = PendingApproval(
                    approval=tr.approval, audit_id=tr.audit_id, tool_name=call.name,
                    call_id=call.call_id, tool_args=dict(call.args), messages=messages,
                    turns_used=turns_used, max_turns=max_turns,
                )
                return run
            else:
                # Single-phase (auto-allow / read-only) — execute now.
                result = await registry.execute(call, audit_store)
                turn.results.append(result)
                messages.append(_tool_result_msg(call, result.content))

        run.turns.append(turn)

    run.hit_max_turns = True
    run.answer = "(stopped: reached max tool-calling turns without a final answer)"
    return run


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
    return await _drive(messages, provider, registry, audit_store, max_turns, 0, AgentRun())


async def resume_agent(
    pending: PendingApproval,
    approved: bool,
    provider: ModelProvider,
    registry: ToolRegistry,
    audit_store,
) -> AgentRun:
    """Continue after a human decision: confirm (or discard) the staged action,
    feed the result back, and keep driving the loop."""
    tr = await registry.confirm(pending.tool_name, pending.audit_id, approved, audit_store)
    fake_call = ToolCall(call_id=pending.call_id, name=pending.tool_name, args={})
    content = (tr.detail if tr is not None else "tool unavailable")
    result = ToolCallResult(
        pending.call_id, pending.tool_name, content,
        bool(tr and tr.ok), (tr.decision if tr else "error"), pending.audit_id,
    )
    run = AgentRun()
    # Record the confirm as its own turn for the log.
    t = AgentTurn(results=[result])
    run.turns.append(t)
    # Feed the outcome back to the model and continue.
    pending.messages.append(_tool_result_msg(fake_call,
        f"{'approved and executed' if approved else 'rejected by human'}: {content}"))
    return await _drive(pending.messages, provider, registry, audit_store,
                        pending.max_turns, pending.turns_used, run)


async def resume_from_pending(
    row: dict,
    approved: bool,
    provider: ModelProvider,
    registry: ToolRegistry,
    audit_store,
) -> AgentRun:
    """Durable HTTP resume (D39): continue a paused loop loaded from the
    pending_approvals store. Unlike resume_agent (in-memory PendingApproval),
    this reconstructs from persisted state and confirms the write from the
    stored (path, content) via confirm_write_explicit — so it works across
    requests / restarts with no in-process dependency.

    Currently specialized to write_file (the one approve-required tool in D39);
    extends as more two-phase tools are wired (D40).
    """
    from agent_api.tools.filesystem import confirm_write_explicit

    tool_name = row["tool_name"]
    audit_id = row["audit_id"]
    call_id = row["call_id"]
    messages = row["messages"]

    if tool_name == "write_file":
        tr = await confirm_write_explicit(
            audit_id, approved, row["write_path"] or "", row["write_content"] or "",
            audit_store,
        )
    else:
        # Fallback to the registry's confirm for any future two-phase tool.
        tr = await registry.confirm(tool_name, audit_id, approved, audit_store)

    content = tr.detail if tr is not None else "tool unavailable"
    result = ToolCallResult(call_id, tool_name, content,
                            bool(tr and tr.ok), (tr.decision if tr else "error"), audit_id)
    run = AgentRun()
    run.turns.append(AgentTurn(results=[result]))
    messages.append(_tool_result_msg(
        ToolCall(call_id=call_id, name=tool_name, args={}),
        f"{'approved and executed' if approved else 'rejected by human'}: {content}"))
    return await _drive(messages, provider, registry, audit_store,
                        row["max_turns"], row["turns_used"], run)
