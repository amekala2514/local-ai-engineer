"""The gate: the single chokepoint every action-taking tool passes through.

    decision, approval, audit_id = await gate(intent, audit_store)

Flow: evaluate (Day 29 pure logic) -> log the decision (audit) -> if approval
is required, build the human-facing approval payload. Tools act on the result:
  ALLOW   -> proceed, then call audit_store.record_execution(audit_id, ...)
  APPROVE -> present `approval` to the human; on yes, mark_approved + proceed
  DENY    -> refuse (the approval is None)

The evaluator stays pure; all I/O (audit writes) lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_api.policy import THREAT_MODEL_VERSION
from agent_api.policy.intent import Intent
from agent_api.policy.engine import evaluate, Decision, PolicyResult
from agent_api.policy.approval import ApprovalRequest, build_approval


@dataclass(frozen=True)
class GateResult:
    decision: Decision
    result: PolicyResult
    approval: ApprovalRequest | None
    audit_id: int


async def gate(intent: Intent, audit_store) -> GateResult:
    """Evaluate, log, and (if needed) build the approval payload."""
    result = evaluate(intent)
    audit_id = await audit_store.record_decision(intent, result, THREAT_MODEL_VERSION)
    approval = (
        build_approval(intent, result)
        if result.decision is Decision.APPROVE
        else None
    )
    return GateResult(
        decision=result.decision,
        result=result,
        approval=approval,
        audit_id=audit_id,
    )
