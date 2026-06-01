"""Filesystem tools — the first real actions (Day 31).

Read/list are single-call (auto-allowed by the engine for non-secret,
in-repo paths). Write is TWO-PHASE to make the human-in-the-loop pause
concrete:
  propose_write() -> gate -> returns (audit_id, ApprovalRequest)   [nothing written]
  confirm_write(audit_id, ...) -> backup original -> write -> record  [the human said yes]

All paths are jailed to project_root by the classifier (outside-repo writes
deny). Writes save a timestamped backup under .policy_backups/ first, so
rollback is real: copy the backup back.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent_api.policy.gate import gate
from agent_api.policy.intent import Intent, Tool, Action, Reversibility
from agent_api.policy.engine import Decision
from agent_api.policy.approval import ApprovalRequest
from agent_api.settings import settings


def _root() -> Path:
    return Path(settings.project_root).resolve()


def _backup_dir() -> Path:
    d = _root() / ".policy_backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    decision: str
    detail: str
    content: str | None = None
    approval: ApprovalRequest | None = None
    audit_id: int | None = None


async def read_file(path: str, audit_store) -> ToolResult:
    """Read a file. Auto-allowed for non-secret, in-repo paths; denied otherwise."""
    intent = Intent(tool=Tool.FILESYSTEM, action=Action.READ_FILE, resource=path)
    gr = await gate(intent, audit_store)
    if gr.decision is not Decision.ALLOW:
        await audit_store.record_execution(gr.audit_id, f"refused:{gr.decision.value}")
        return ToolResult(False, gr.decision.value,
                          f"read denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    try:
        full = (_root() / path).resolve()
        text = full.read_text(encoding="utf-8")
        await audit_store.record_execution(gr.audit_id, f"read_ok:{len(text)}_chars")
        return ToolResult(True, "allow", f"read {len(text)} chars", content=text, audit_id=gr.audit_id)
    except Exception as e:
        await audit_store.record_execution(gr.audit_id, f"error:{type(e).__name__}")
        return ToolResult(False, "allow", f"read error: {type(e).__name__}: {e}", audit_id=gr.audit_id)


async def list_dir(path: str, audit_store) -> ToolResult:
    """List a directory. Auto-allowed for in-repo, non-secret paths."""
    intent = Intent(tool=Tool.FILESYSTEM, action=Action.LIST_DIR, resource=path)
    gr = await gate(intent, audit_store)
    if gr.decision is not Decision.ALLOW:
        await audit_store.record_execution(gr.audit_id, f"refused:{gr.decision.value}")
        return ToolResult(False, gr.decision.value,
                          f"list denied: {'; '.join(gr.result.reasons)}", audit_id=gr.audit_id)
    try:
        full = (_root() / path).resolve()
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in full.iterdir())
        await audit_store.record_execution(gr.audit_id, f"list_ok:{len(entries)}_entries")
        return ToolResult(True, "allow", f"{len(entries)} entries",
                          content="\n".join(entries), audit_id=gr.audit_id)
    except Exception as e:
        await audit_store.record_execution(gr.audit_id, f"error:{type(e).__name__}")
        return ToolResult(False, "allow", f"list error: {type(e).__name__}: {e}", audit_id=gr.audit_id)


# Pending writes held between propose and confirm (audit_id -> (path, content)).
# In-process only; a write must be confirmed in the same process that proposed it.
_PENDING: dict[int, tuple[str, str]] = {}


async def propose_write(path: str, content: str, audit_store) -> ToolResult:
    """Phase 1: submit a write intent to the gate. Writes NOTHING. Returns the
    approval payload (if approved-pending) or a deny."""
    intent = Intent(
        tool=Tool.FILESYSTEM, action=Action.WRITE_FILE, resource=path,
        reversibility=Reversibility.PATCH_BACKUP,
    )
    gr = await gate(intent, audit_store)
    if gr.decision is Decision.DENY:
        await audit_store.record_execution(gr.audit_id, "refused:deny")
        return ToolResult(False, "deny", f"write denied: {'; '.join(gr.result.reasons)}",
                          audit_id=gr.audit_id)
    if gr.decision is Decision.APPROVE:
        _PENDING[gr.audit_id] = (path, content)
        return ToolResult(True, "approve", "approval required before write",
                          approval=gr.approval, audit_id=gr.audit_id)
    # (filesystem writes never auto-allow under current policy, but handle it)
    _PENDING[gr.audit_id] = (path, content)
    return ToolResult(True, "allow", "auto-allowed", audit_id=gr.audit_id)


async def confirm_write(audit_id: int, approved: bool, audit_store) -> ToolResult:
    """Phase 2: the human responded. On approval: backup the original (if any),
    write the new content, record execution. On rejection: discard."""
    pending = _PENDING.pop(audit_id, None)
    if pending is None:
        return ToolResult(False, "error", f"no pending write for audit #{audit_id}", audit_id=audit_id)
    path, content = pending

    await audit_store.mark_approved(audit_id, approved)
    if not approved:
        await audit_store.record_execution(audit_id, "rejected_by_human")
        return ToolResult(False, "approve", "write rejected by human", audit_id=audit_id)

    try:
        full = (_root() / path).resolve()
        backup_note = "no_prior_file"
        if full.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            backup = _backup_dir() / f"{full.name}.{ts}.bak"
            shutil.copy2(full, backup)
            backup_note = f"backup:{backup.name}"
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        await audit_store.record_execution(audit_id, f"write_ok:{len(content)}_chars:{backup_note}")
        return ToolResult(True, "approve", f"wrote {len(content)} chars ({backup_note})", audit_id=audit_id)
    except Exception as e:
        await audit_store.record_execution(audit_id, f"error:{type(e).__name__}")
        return ToolResult(False, "approve", f"write error: {type(e).__name__}: {e}", audit_id=audit_id)


async def confirm_write_explicit(audit_id: int, approved: bool, path: str,
                                 content: str, audit_store) -> ToolResult:
    """Like confirm_write, but takes the (path, content) EXPLICITLY instead of
    reading the in-process _PENDING dict. Used by the durable HTTP resume path
    (D39) so a write survives across requests / server restarts. The harness
    path still uses confirm_write (in-process)."""
    await audit_store.mark_approved(audit_id, approved)
    if not approved:
        await audit_store.record_execution(audit_id, "rejected_by_human")
        return ToolResult(False, "approve", "write rejected by human", audit_id=audit_id)
    try:
        full = (_root() / path).resolve()
        backup_note = "no_prior_file"
        if full.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            backup = _backup_dir() / f"{full.name}.{ts}.bak"
            shutil.copy2(full, backup)
            backup_note = f"backup:{backup.name}"
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        await audit_store.record_execution(audit_id, f"write_ok:{len(content)}_chars:{backup_note}")
        return ToolResult(True, "approve", f"wrote {len(content)} chars ({backup_note})", audit_id=audit_id)
    except Exception as e:
        await audit_store.record_execution(audit_id, f"error:{type(e).__name__}")
        return ToolResult(False, "approve", f"write error: {type(e).__name__}: {e}", audit_id=audit_id)
