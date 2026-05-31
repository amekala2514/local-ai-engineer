"""ToolRegistry — the MCP-ready tool-resolution seam.

Maps a tool name -> (descriptor the model sees, uniform executor). The loop
asks the registry for descriptors (to pass the provider) and calls
registry.execute(call, audit_store) to run a tool, getting a canonical
ToolCallResult back regardless of the underlying tool's shape.

D37 registers LOCAL read-only Phase C tools (which gate themselves internally).
Heterogeneous Phase C signatures (async vs sync onboard, audit_store or not,
ToolResult vs RepoSummary) are adapted by per-tool wrappers here, so the loop
sees one uniform interface. In D41, an MCPTool becomes another registry entry
behind the same interface — no loop change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agent_api.agent.types import ToolDescriptor, ToolCall, ToolCallResult
from agent_api.tools import filesystem as fs
from agent_api.tools import git as gt
from agent_api.tools.onboard import onboard as onboard_fn

# A uniform executor takes the whole ToolCall (so it has call_id + args) plus
# the audit store, and returns a canonical ToolCallResult.
Executor = Callable[[ToolCall, Any], Awaitable[ToolCallResult]]


@dataclass(frozen=True)
class RegisteredTool:
    descriptor: ToolDescriptor
    executor: Executor


def _from_phasec(call: ToolCall, tr) -> ToolCallResult:
    """Adapt a Phase C ToolResult to a canonical ToolCallResult."""
    content = tr.content if (tr.ok and tr.content is not None) else tr.detail
    return ToolCallResult(
        call_id=call.call_id, name=call.name, content=content or "",
        ok=tr.ok, decision=tr.decision, audit_id=tr.audit_id,
    )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        self._tools[tool.descriptor.name] = tool

    def descriptors(self) -> list[ToolDescriptor]:
        return [t.descriptor for t in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, call: ToolCall, audit_store) -> ToolCallResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolCallResult(call_id=call.call_id, name=call.name,
                                  content=f"unknown tool: {call.name}", ok=False, decision="error")
        return await tool.executor(call, audit_store)


# ---- executor wrappers (adapt each Phase C tool's specific signature) ----

async def _ex_read_file(call: ToolCall, store) -> ToolCallResult:
    tr = await fs.read_file(call.args.get("path", ""), store)
    return _from_phasec(call, tr)

async def _ex_list_dir(call: ToolCall, store) -> ToolCallResult:
    tr = await fs.list_dir(call.args.get("path", "."), store)
    return _from_phasec(call, tr)

async def _ex_git_status(call: ToolCall, store) -> ToolCallResult:
    tr = await gt.status(store)
    return _from_phasec(call, tr)

async def _ex_git_diff(call: ToolCall, store) -> ToolCallResult:
    tr = await gt.diff(call.args.get("path"), store)
    return _from_phasec(call, tr)

async def _ex_git_log(call: ToolCall, store) -> ToolCallResult:
    n = int(call.args.get("n", 10) or 10)
    tr = await gt.log(n, store)
    return _from_phasec(call, tr)

async def _ex_onboard(call: ToolCall, store) -> ToolCallResult:
    # onboard is SYNC and returns a RepoSummary (not a ToolResult). It composes
    # gated reads internally (secrets skipped). We ALSO submit one representative
    # intent through the gate so every model-initiated onboard is AUDITED (D37
    # audit-completeness fix — no model tool-call should be unlogged).
    from agent_api.policy.gate import gate as _gate
    from agent_api.policy.intent import Intent as _Intent, Tool as _Tool, Action as _Action
    from agent_api.policy.engine import Decision as _Decision
    subpath = call.args.get("subpath", ".")
    gr = await _gate(_Intent(tool=_Tool.FILESYSTEM, action=_Action.LIST_DIR, resource=subpath), store)
    if gr.decision is _Decision.DENY:
        await store.record_execution(gr.audit_id, "refused:deny")
        return ToolCallResult(call_id=call.call_id, name=call.name,
                              content=f"onboard denied: {'; '.join(gr.result.reasons)}",
                              ok=False, decision="deny", audit_id=gr.audit_id)
    try:
        s = onboard_fn(subpath)
        lines = [
            f"root: {s.root}",
            f"files: {len(s.tree)}",
            f"languages: {s.languages}",
            f"entry_points: {s.entry_points[:8]}",
            f"key_files: {s.key_files[:8]}",
            f"skipped_secrets: {len(s.skipped_secrets)}",
        ]
        await store.record_execution(gr.audit_id, f"onboard_ok:{len(s.tree)}_files")
        return ToolCallResult(call_id=call.call_id, name=call.name,
                              content="\n".join(lines), ok=True, decision="allow", audit_id=gr.audit_id)
    except Exception as e:
        return ToolCallResult(call_id=call.call_id, name=call.name,
                              content=f"onboard error: {type(e).__name__}: {e}",
                              ok=False, decision="error")


def build_default_registry() -> ToolRegistry:
    """Registry with the D37 read-only local tools (all auto-allow / self-gating)."""
    reg = ToolRegistry()
    reg.register(RegisteredTool(
        ToolDescriptor("read_file", "Read a text file from the repository (non-secret, in-repo only).",
            {"type":"object","required":["path"],
             "properties":{"path":{"type":"string","description":"file path relative to repo root"}}}),
        _ex_read_file))
    reg.register(RegisteredTool(
        ToolDescriptor("list_dir", "List the contents of a directory in the repository.",
            {"type":"object","required":["path"],
             "properties":{"path":{"type":"string","description":"directory path relative to repo root"}}}),
        _ex_list_dir))
    reg.register(RegisteredTool(
        ToolDescriptor("git_status", "Show the git working-tree status (porcelain).",
            {"type":"object","properties":{}}),
        _ex_git_status))
    reg.register(RegisteredTool(
        ToolDescriptor("git_diff", "Show the git diff, optionally for one path.",
            {"type":"object","properties":{"path":{"type":"string","description":"optional path to diff"}}}),
        _ex_git_diff))
    reg.register(RegisteredTool(
        ToolDescriptor("git_log", "Show recent git commits (oneline).",
            {"type":"object","properties":{"n":{"type":"integer","description":"how many commits (default 10)"}}}),
        _ex_git_log))
    reg.register(RegisteredTool(
        ToolDescriptor("onboard", "Summarize the repository structure: tree, languages, entry points, key files. Secrets are skipped.",
            {"type":"object","properties":{"subpath":{"type":"string","description":"sub-path to onboard (default repo root)"}}}),
        _ex_onboard))
    return reg
