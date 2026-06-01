"""The policy engine: classified Intent -> Decision (allow / approve / deny).

OPA-shaped without a YAML DSL yet: rules are a typed DATA TABLE (RULES below),
and evaluate() is generic logic over them. The decision is COMPUTED from intent
attributes + computed risk signals + resource sensitivity — not a static tier
lookup. Conservative by default: anything not explicitly auto-allowed and not
denied falls through to require-approval.

Evaluation order (first matching rule wins):
  1. DENY rules — hard refusals, returned even if the user would approve.
  2. ALLOW rules — read-only / reversible / safe auto-allows.
  3. Fallthrough — APPROVE (the safe default for every mutation).

Rules being data (not scattered ifs) means they can later move to YAML and be
swapped for OPA without touching tools. That's the OPA shape; the DSL is
deferred until the ruleset proves it needs one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from agent_api.policy.intent import Intent, Action, RiskSignal
from agent_api.policy.classify import classify
from agent_api.policy.sensitivity import Sensitivity


class Decision(StrEnum):
    ALLOW = "allow"        # auto-execute, no human needed
    APPROVE = "approve"    # require explicit human approval
    DENY = "deny"          # refuse, even if asked


@dataclass(frozen=True)
class PolicyResult:
    decision: Decision
    reasons: list[str] = field(default_factory=list)
    sensitivity: Sensitivity = Sensitivity.NORMAL
    risk_signals: list[RiskSignal] = field(default_factory=list)


# ---- the rule table (data) ----
# Each rule: (decision, predicate(intent, sensitivity, signals) -> bool, reason)
# DENY rules are checked first, then ALLOW; no match => APPROVE.

def _has(sig: RiskSignal):
    return lambda i, s, sigs: sig in sigs

# Read-only actions that are always safe.
_READ_ONLY_ACTIONS = {Action.READ_FILE, Action.LIST_DIR, Action.GIT_STATUS, Action.GIT_DIFF, Action.GIT_LOG}

_DENY_RULES = [
    (lambda i, s, sigs: RiskSignal.SECRET_ADJACENT in sigs and i.action not in _READ_ONLY_ACTIONS,
     "write/exec touching a secret-class resource is never allowed"),
    (lambda i, s, sigs: RiskSignal.SECRET_ADJACENT in sigs and i.action in _READ_ONLY_ACTIONS,
     "reading a secret-class resource is denied (secrets must never enter the model's context)"),
    (lambda i, s, sigs: RiskSignal.OUTSIDE_REPO in sigs and i.action not in _READ_ONLY_ACTIONS,
     "write/exec outside the project root is never allowed"),
    (lambda i, s, sigs: RiskSignal.DESTRUCTIVE_FLAG in sigs,
     "destructive flag (rm -rf / --force / reset --hard) is never allowed"),
    (lambda i, s, sigs: RiskSignal.REMOTE_WRITE in sigs,
     "remote write (git push) is denied by default; push manually"),
    (lambda i, s, sigs: RiskSignal.MULTI_COMMAND in sigs,
     "chained/compound commands are not allowed (one command per call)"),
    (lambda i, s, sigs: s is Sensitivity.CONFIG and i.action not in _READ_ONLY_ACTIONS,
     "writing CI/deploy/git-internal config is denied by default"),
]

_ALLOW_RULES = [
    (lambda i, s, sigs: i.action in _READ_ONLY_ACTIONS and RiskSignal.SECRET_ADJACENT not in sigs,
     "read-only action on a non-secret resource"),
]


def evaluate(intent: Intent) -> PolicyResult:
    """Classify then decide. The single chokepoint every tool call passes."""
    sensitivity, signals = classify(intent)

    for pred, reason in _DENY_RULES:
        if pred(intent, sensitivity, signals):
            return PolicyResult(Decision.DENY, [reason], sensitivity, signals)

    for pred, reason in _ALLOW_RULES:
        if pred(intent, sensitivity, signals):
            return PolicyResult(Decision.ALLOW, [reason], sensitivity, signals)

    return PolicyResult(
        Decision.APPROVE,
        ["mutation requires explicit human approval (conservative default)"],
        sensitivity, signals,
    )
