"""Guarded shell (Day 34) — the first tool that uses BOTH Phase C pillars.

Three layers, in order:
  1. allowlist (policy.shell_allowlist) — is argv[0] a known binary?
  2. gate (policy.gate) — risk signals: destructive flag, chaining, etc.
  3. sandbox (sandbox.DockerSandbox) — the command runs CONTAINED.

All shell commands are approve-minimum (never auto-allowed): a shell invocation
is broader and less introspectable than a typed filesystem read, so it always
gets the human approval gate. Two-phase like Day 31/32:
  propose_command(argv) -> allowlist -> gate -> approval payload (runs nothing)
  confirm_command(audit_id, approved) -> runs in the sandbox -> records result
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_api.policy.gate import gate
from agent_api.policy.intent import Intent, Tool, Action
from agent_api.policy.engine import Decision
from agent_api.policy.approval import ApprovalRequest
from agent_api.policy.shell_allowlist import binary_allowed, ALLOWED_BINARIES
from agent_api.sandbox.interface import ExecRequest, ExecStatus
from agent_api.sandbox.docker_sandbox import DockerSandbox


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    decision: str
    detail: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    approval: ApprovalRequest | None = None
    audit_id: int | None = None


# Pending commands held in-process (audit_id -> argv), same shape as Day 31/32.
_PENDING: dict[int, list[str]] = {}


async def propose_command(argv: list[str], audit_store, network: bool = False) -> ToolResult:
    """Phase 1: allowlist check -> gate. Runs NOTHING. Returns approval payload
    or a refusal. network defaults False (sandbox network stays off unless the
    caller explicitly requests it AND policy allows)."""
    # Layer 1: allowlist. Refuse non-allowlisted binaries before the gate.
    if not binary_allowed(argv):
        binary = argv[0] if argv else "(empty)"
        return ToolResult(
            False, "deny",
            f"shell denied: '{binary}' is not an allowed binary. "
            f"Allowed: {', '.join(sorted(ALLOWED_BINARIES))}",
        )

    # Layer 2: the policy gate (risk signals: destructive flag, chaining, net).
    intent = Intent(
        tool=Tool.SHELL, action=Action.RUN_COMMAND, args=argv, network=network,
    )
    gr = await gate(intent, audit_store)
    if gr.decision is Decision.DENY:
        await audit_store.record_execution(gr.audit_id, "refused:deny")
        return ToolResult(False, "deny", f"shell denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    # Shell is approve-minimum; APPROVE is the expected path.
    _PENDING[gr.audit_id] = argv
    return ToolResult(
        True, gr.decision.value,
        f"command pending approval: {' '.join(argv)}",
        approval=gr.approval, audit_id=gr.audit_id,
    )


async def confirm_command(audit_id: int, approved: bool, audit_store,
                          sandbox: DockerSandbox | None = None,
                          network: bool = False) -> ToolResult:
    """Phase 2: human responded. On yes: run argv inside the sandbox (Layer 3),
    record exit/output to audit. On no: discard."""
    argv = _PENDING.pop(audit_id, None)
    if argv is None:
        return ToolResult(False, "error", f"no pending command for audit #{audit_id}",
                          audit_id=audit_id)
    await audit_store.mark_approved(audit_id, approved)
    if not approved:
        await audit_store.record_execution(audit_id, "rejected_by_human")
        return ToolResult(False, "approve", "command rejected by human", audit_id=audit_id)

    sandbox = sandbox or DockerSandbox()
    # Layer 3: run CONTAINED (network off by default, host read-only).
    result = await sandbox.execute(ExecRequest(argv=argv, network=network))

    summary = f"{result.status.value}:exit={result.exit_code}:dur={result.duration_ms}ms"
    if result.stdout_truncated or result.stderr_truncated:
        summary += ":output_truncated"
    await audit_store.record_execution(audit_id, summary)

    ok = result.status is ExecStatus.COMPLETED and result.exit_code == 0
    return ToolResult(
        ok, "approve",
        f"ran in sandbox: {summary}",
        stdout=result.stdout, stderr=result.stderr, exit_code=result.exit_code,
        audit_id=audit_id,
    )
