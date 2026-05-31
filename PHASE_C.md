# Phase C — Agentic Safety Layer (Reflection)

Phase C gave the assistant the ability to take actions — read/write files, run
git operations, execute shell commands and code — under a centralized safety
layer. This document reflects on what was built, why, what's proven, and what's
deliberately deferred.

## What was built (Days 28-36)

A safety-first agentic layer, built foundation-before-features:

- **Day 28 — contracts.** Tool-agnostic `Intent` schema (frozen, validated),
  resource-sensitivity data (secret/config/normal), threat model T11 with a
  version string (`phase-c-v1`) logged per decision.
- **Day 29 — policy engine.** Attribute-based evaluator returning
  allow/approve/deny from a data-table of rules (OPA-shaped, no DSL).
  Classifier computes risk signals + sensitivity. Proven on a mock-intent suite
  before any tool existed.
- **Day 30 — audit + approval.** Every decision persisted (SQLite policy_audit,
  full intent JSON, threat-model version). Rich approval object (action, exact
  payload, risk reasons, containment, rollback). The gate ties decide -> log ->
  present together.
- **Day 31 — filesystem tools.** Read/list (auto-allow, secrets excluded),
  write (two-phase propose/confirm, real backup rollback).
- **Day 32 — git tools.** Status/diff/log (auto), commit (two-phase, tag-based
  rollback), branch (approve), push (deny-by-default). Verified on the real
  repo with strict cleanup.
- **Day 33 — Docker sandbox.** Swappable `Sandbox` interface + DockerSandbox
  (network off, host read-only, non-root, capped). Seven empirical containment
  proofs.
- **Day 34 — guarded shell.** Three layers: allowlist + gate + sandbox. First
  tool to compose both pillars. Surfaced and fixed a classifier false positive.
- **Day 35 — repo onboarding (capstone).** Composes the lower layers into
  structured repo understanding; secrets never read; repo content framed as
  untrusted data (prompt-injection hardening).
- **Day 36 — eval + reflection.** 23/23 decision-correctness, zero false-allows.

## The architecture: defense in depth, gate never trusts the model

The core idea: **no single layer is trusted to be perfect.**

- A shell command passes three independent layers (allowlist, policy gate,
  sandbox). Each is verified separately.
- Resource sensitivity is both a write-policy AND a context constraint: secrets
  are write-denied AND never read into context.
- The policy gate is the backstop for prompt injection. Framing repo content as
  untrusted data is mitigation (and documented honestly as not a guarantee —
  LLMs can be tricked). But even a SUCCESSFUL injection cannot make the
  assistant take a gate-forbidden action: the gate decides from intent
  attributes, never from the model's reasoning. Injection might corrupt intent;
  the gate contains the action.

This is the key design property: the safety model never depended on the model
being un-trickable. It depends on the gate not trusting the model.

## What's proven (empirically, not asserted)

- Policy decisions: 23/23 correct, **zero false-allows** (evals/policy_eval.py)
- Sandbox containment: 7/7 — host writes blocked, network blocked (Day 33 test)
- Filesystem: read/write/backup-rollback verified on real disk (Day 31 test)
- Git: commit + tag-rollback exercised on the real repo, restored bit-identical
- Shell: three-layer composition, real command run contained (Day 34 test)
- Onboarding: composition + secret-exclusion + injection-framed-as-data (Day 35)

## Threat model coverage and limits

**Defended (the stated model — trusted local copilot, mistakes-primary,
supervised, own repos):** accidental destructive actions (gated/denied),
secret exposure (never read), runaway execution (sandbox caps), and the one
acknowledged adversarial vector — prompt injection via repo content (framed +
gated).

**NOT defended (explicit, documented revisiting triggers):**
- Untrusted/public repos or unvetted external code — the design assumes you vet
  what it operates on. If this changes, weight microVM-class isolation and
  stricter onboarding (the Sandbox interface is the swap path).
- Detached/unsupervised operation.
- Multi-user.

## Deliberately deferred (the backlog)

None of these block the design; each was a conscious "not yet":
- Durable pending-store for writes/commits (currently in-process).
- Per-git-operation audit enums (status/diff/log share GIT_STATUS).
- Arg-constrained shell allowlist (v1 is just-the-binary; sandbox bounds risk).
- gVisor/microVM sandbox (interface exists; Docker is the only implementation).
- Harder retrieval eval cases (Day 27 noted saturation at 22/22).

## The one thing that turns this from built to usable: Phase D

**The Phase C tools are not yet wired to the chat/agent loop.** Every tool is
proven in isolation against the live gate, but the assistant cannot yet CALL
them in a conversation. That is the deliberate next phase:

> **Phase D — wire the proven tools into the agent loop** so the model can emit
> tool calls, the gate enforces safety on real model-initiated intents, and
> approvals surface in the UI. This is where the model-in-the-loop injection
> scenario stops being a test and becomes real — which is exactly why the
> gate-as-backstop was built and proven first.

Phase C built the safe foundation. Phase D makes it act.
