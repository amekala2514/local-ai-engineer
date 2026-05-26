"""The rich approval object — the payload a human reviews when a decision is
'approve'. A generic "Allow?" is both dangerous and annoying; this shows
exactly what will happen, why it was flagged, how it's contained, and how to
undo it, so approval is safer AND lower-friction (per the design review).

Built by the gate (gate.py) from an Intent + PolicyResult. Pure data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_api.policy.intent import Intent, Reversibility
from agent_api.policy.engine import PolicyResult


_ROLLBACK_DESC = {
    Reversibility.REVERSIBLE: "Reversible (read-only or trivially undoable).",
    Reversibility.PATCH_BACKUP: "A backup patch is saved before the change; revert by applying it.",
    Reversibility.TEMP_BRANCH: "Shielded by a temporary git branch; discard the branch to undo.",
    Reversibility.IRREVERSIBLE: "NOT reversible — this cannot be undone.",
}


class ApprovalRequest(BaseModel):
    """What the human sees before approving a pending action."""
    action_summary: str = Field(description="human-readable one-liner")
    exact_payload: str = Field(description="the literal command / path / diff target")
    risk_reasons: list[str] = Field(default_factory=list)
    containment: str = Field(description="sandbox / path-jail / network posture")
    rollback: str = Field(description="how to undo, or that it can't be undone")


def build_approval(intent: Intent, result: PolicyResult) -> ApprovalRequest:
    """Construct the approval payload from a classified intent + its decision."""
    # Action summary
    summary = f"{intent.tool.value}:{intent.action.value}"
    if intent.resource:
        summary += f" {intent.resource}"

    # Exact payload — the literal thing that will run.
    if intent.args:
        exact = " ".join([intent.action.value] + intent.args)
    else:
        exact = f"{intent.action.value} {intent.resource or ''}".strip()

    # Risk reasons: engine reasons + the human-readable signals.
    reasons = list(result.reasons)
    if result.risk_signals:
        reasons.append("signals: " + ", ".join(s.value for s in result.risk_signals))

    # Containment posture.
    parts = []
    parts.append("network: on" if intent.network else "network: off")
    parts.append(f"path-jail: {intent.cwd or 'project root'}")
    containment = "; ".join(parts)

    rollback = _ROLLBACK_DESC.get(intent.reversibility, "Unknown reversibility.")

    return ApprovalRequest(
        action_summary=summary,
        exact_payload=exact,
        risk_reasons=reasons,
        containment=containment,
        rollback=rollback,
    )
