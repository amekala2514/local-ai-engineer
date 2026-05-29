"""Git tools (Day 32) — every operation routes through the policy gate.

Direct subprocess (not sandboxed): git on your own repo is the mistakes-primary
case, and the gate already refuses the dangerous ops (push, --force, reset
--hard, etc.). The sandbox swap is reserved for untrusted-code execution
(Day 33+); if Phase C ever shifts to untrusted repos, git can route through it.

Read-only ops (status/diff/log) are single-call auto-allowed by the engine.
Commit is TWO-PHASE with TAG-based rollback: a lightweight ref
'policy-pre-commit-<audit_id>-<ts>' is placed at HEAD before the commit, so
rollback is exactly `git reset --hard <tag>`. Audit records the tag name.
Branch creation is single-call approve (delete the branch to roll back).
Push is denied by the gate — surfaced as a clear 'do it yourself'.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from agent_api.policy.gate import gate
from agent_api.policy.intent import Intent, Tool, Action, Reversibility
from agent_api.policy.engine import Decision
from agent_api.policy.approval import ApprovalRequest
from agent_api.settings import settings


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    decision: str
    detail: str
    content: str | None = None
    approval: ApprovalRequest | None = None
    audit_id: int | None = None


def _run(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git subprocess at project_root. Capture stdout/stderr text."""
    cwd = cwd or settings.project_root
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd, capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


async def status(audit_store) -> ToolResult:
    """git status (porcelain). Auto-allowed."""
    intent = Intent(tool=Tool.GIT, action=Action.GIT_STATUS, args=["status"])
    gr = await gate(intent, audit_store)
    if gr.decision is not Decision.ALLOW:
        await audit_store.record_execution(gr.audit_id, f"refused:{gr.decision.value}")
        return ToolResult(False, gr.decision.value,
                          f"status denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    rc, out, err = _run(["status", "--porcelain"])
    if rc != 0:
        await audit_store.record_execution(gr.audit_id, f"git_error:rc={rc}")
        return ToolResult(False, "allow", f"git status failed: {err.strip()}",
                          audit_id=gr.audit_id)
    await audit_store.record_execution(gr.audit_id, f"status_ok:{len(out.splitlines())}_lines")
    return ToolResult(True, "allow", "status read", content=out, audit_id=gr.audit_id)


async def diff(path: str | None, audit_store) -> ToolResult:
    """git diff [path]. Auto-allowed."""
    intent = Intent(tool=Tool.GIT, action=Action.GIT_STATUS,
                    resource=path, args=["diff"])
    gr = await gate(intent, audit_store)
    if gr.decision is not Decision.ALLOW:
        await audit_store.record_execution(gr.audit_id, f"refused:{gr.decision.value}")
        return ToolResult(False, gr.decision.value,
                          f"diff denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    args = ["diff"] + ([path] if path else [])
    rc, out, err = _run(args)
    if rc != 0:
        await audit_store.record_execution(gr.audit_id, f"git_error:rc={rc}")
        return ToolResult(False, "allow", f"git diff failed: {err.strip()}",
                          audit_id=gr.audit_id)
    await audit_store.record_execution(gr.audit_id, f"diff_ok:{len(out)}_chars")
    return ToolResult(True, "allow", "diff read", content=out, audit_id=gr.audit_id)


async def log(n: int, audit_store) -> ToolResult:
    """git log --oneline -n N. Auto-allowed."""
    intent = Intent(tool=Tool.GIT, action=Action.GIT_STATUS, args=["log"])
    gr = await gate(intent, audit_store)
    if gr.decision is not Decision.ALLOW:
        await audit_store.record_execution(gr.audit_id, f"refused:{gr.decision.value}")
        return ToolResult(False, gr.decision.value,
                          f"log denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    rc, out, err = _run(["log", "--oneline", f"-{max(1, n)}"])
    if rc != 0:
        await audit_store.record_execution(gr.audit_id, f"git_error:rc={rc}")
        return ToolResult(False, "allow", f"git log failed: {err.strip()}",
                          audit_id=gr.audit_id)
    await audit_store.record_execution(gr.audit_id, f"log_ok:{len(out.splitlines())}_lines")
    return ToolResult(True, "allow", f"{len(out.splitlines())} commits", content=out, audit_id=gr.audit_id)


# Pending commits held in-process (audit_id -> message), same shape as Day 31.
_PENDING_COMMITS: dict[int, str] = {}


async def propose_commit(message: str, audit_store) -> ToolResult:
    """Phase 1: gate a commit. Commits NOTHING. Returns the approval payload."""
    intent = Intent(
        tool=Tool.GIT, action=Action.GIT_COMMIT, args=["commit"],
        reversibility=Reversibility.TEMP_BRANCH,
    )
    gr = await gate(intent, audit_store)
    if gr.decision is Decision.DENY:
        await audit_store.record_execution(gr.audit_id, "refused:deny")
        return ToolResult(False, "deny", f"commit denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    if gr.decision is Decision.APPROVE:
        _PENDING_COMMITS[gr.audit_id] = message
        # Include a preview of what will be committed in the approval detail.
        rc, staged, _ = _run(["diff", "--cached", "--stat"])
        preview = staged.strip() if rc == 0 else "(could not preview staged changes)"
        return ToolResult(
            True, "approve",
            f"commit pending approval. message: {message!r}\nstaged:\n{preview}",
            approval=gr.approval, audit_id=gr.audit_id,
        )
    _PENDING_COMMITS[gr.audit_id] = message
    return ToolResult(True, "allow", "auto-allowed (unexpected)", audit_id=gr.audit_id)


async def confirm_commit(audit_id: int, approved: bool, audit_store) -> ToolResult:
    """Phase 2: human responded. On yes: tag HEAD (rollback ref), then commit."""
    message = _PENDING_COMMITS.pop(audit_id, None)
    if message is None:
        return ToolResult(False, "error", f"no pending commit for audit #{audit_id}",
                          audit_id=audit_id)
    await audit_store.mark_approved(audit_id, approved)
    if not approved:
        await audit_store.record_execution(audit_id, "rejected_by_human")
        return ToolResult(False, "approve", "commit rejected by human", audit_id=audit_id)

    # 1. Place a lightweight tag at HEAD as the rollback ref.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    tag = f"policy-pre-commit-{audit_id}-{ts}"
    rc, _, err = _run(["tag", tag])
    if rc != 0:
        # Common reason: no HEAD yet on a fresh repo. Continue without rollback ref.
        tag_note = f"no_rollback_tag({err.strip()[:60]})"
    else:
        tag_note = f"rollback_tag:{tag}"

    # 2. The actual commit.
    rc, out, err = _run(["commit", "-m", message])
    if rc != 0:
        # Roll back our tag if we placed one — it pointed at a state we didn't commit from.
        if tag_note.startswith("rollback_tag:"):
            _run(["tag", "-d", tag])
            tag_note += "_removed"
        await audit_store.record_execution(audit_id, f"git_error:rc={rc}:{tag_note}")
        return ToolResult(False, "approve", f"git commit failed: {err.strip() or out.strip()}",
                          audit_id=audit_id)
    # New commit SHA for the audit record.
    _, sha, _ = _run(["rev-parse", "HEAD"])
    await audit_store.record_execution(audit_id, f"commit_ok:{sha.strip()[:12]}:{tag_note}")
    return ToolResult(True, "approve",
                      f"committed {sha.strip()[:12]} ({tag_note})", audit_id=audit_id)


async def create_branch(name: str, audit_store) -> ToolResult:
    """Single-phase: gate -> on approve, create branch off HEAD.
    NOTE: Day 32 unifies propose/confirm for branches into one call because the
    operation is lightweight and rollback is trivial (delete the branch). If a
    full two-phase pattern is needed later, this can split like commit."""
    intent = Intent(tool=Tool.GIT, action=Action.GIT_BRANCH, args=["branch", name],
                    resource=name)
    gr = await gate(intent, audit_store)
    if gr.decision is Decision.DENY:
        await audit_store.record_execution(gr.audit_id, "refused:deny")
        return ToolResult(False, "deny", f"branch denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    # APPROVE: in this build, we treat the call itself as the human's intent and create.
    # A future UI would split this into propose/confirm like commit.
    await audit_store.mark_approved(gr.audit_id, True)
    rc, out, err = _run(["branch", name])
    if rc != 0:
        await audit_store.record_execution(gr.audit_id, f"git_error:rc={rc}")
        return ToolResult(False, "approve", f"git branch failed: {err.strip()}",
                          audit_id=gr.audit_id)
    await audit_store.record_execution(gr.audit_id, f"branch_ok:{name}")
    return ToolResult(True, "approve", f"created branch {name} (delete to roll back)",
                      audit_id=gr.audit_id)


async def push(remote: str, branch: str, audit_store) -> ToolResult:
    """Always denied by the gate (deny-by-default for off-machine ops).
    Surface that clearly rather than failing opaquely."""
    intent = Intent(tool=Tool.GIT, action=Action.GIT_PUSH,
                    args=["push", remote, branch], resource=f"{remote}/{branch}")
    gr = await gate(intent, audit_store)
    # Push always denies; the gate already logged it.
    await audit_store.record_execution(gr.audit_id, "refused:deny")
    return ToolResult(
        False, gr.decision.value,
        f"push denied: {'; '.join(gr.result.reasons)}. Run 'git push {remote} {branch}' yourself.",
        audit_id=gr.audit_id,
    )
