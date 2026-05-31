# Policy Engine Decision-Correctness Baseline (Phase C)

Canonical record of the policy engine's decision correctness, measured by
`evals/policy_eval.py`. Mirrors `BASELINE.md` (retrieval) for the agentic
safety layer. Re-run after any change to the engine, classifier, or
sensitivity rules: `python -m evals.policy_eval`.

## What this measures

The DECISION ENGINE (`evaluate()`): given an intent's attributes + computed
risk signals + resource sensitivity, is the allow/approve/deny decision
correct? This is engine-focused. The shell allowlist is a separate tool-level
guard (tested in the Day 34 shell synthesis test), not part of this eval.

## The metric that matters: false-allows

A **false-allow** is a case that should be approve/deny but the engine returned
`allow` — an un-gated dangerous action. This is the only safety-critical error
class and **must be zero**. False-denies are a usability cost (legitimate thing
refused), reported but not safety-critical.

## Baseline (Day 36)

- **23/23 cases correct**
- **False-allows: 0** (the headline safety result)
- **False-denies: 0**
- Decision distribution: allow=4, approve=7, deny=12

The distribution confirms the engine is non-degenerate and conservative: a
small set of read-only auto-allows, mutations gated to human approval, and the
largest bucket denied outright (secrets, destructive flags, remote writes,
outside-repo, command chains).

## Coverage

Cases span every risk category the threat model recognizes:
- read / auto-allow (incl. config-class readable, unlike secrets)
- mutate / approve (file write, commit, branch, shell, code exec)
- secret (deny on BOTH read and write; nested paths)
- config write (deny)
- path jail (outside-repo write deny)
- destructive flags (rm -rf, force push)
- remote writes (push deny-by-default)
- command chains (; && | as standalone tokens → deny)
- **regression locks**: ';' inside `-c` code must NOT be treated as a chain
  (the Day 34 false-positive fix — if these flip to deny, the bug regressed)

## Known properties (by design, not bugs)

- **Normal git push is denied**, not just force push — off-machine consequence,
  "push manually" is the conservative default.
- **Reading a secret is denied**, not approved — secrets must never enter the
  model's context (Day 28 in_context=False).
- **All shell is approve-minimum** — never auto-allowed, even read-ish commands.

## What this eval does NOT cover

- The shell allowlist (tool-level, tested separately).
- The sandbox containment (tested by the Day 33 containment proofs).
- End-to-end tool execution (filesystem/git/shell tool tests).
- Model-initiated intents in a live agent loop (not yet wired — Phase D).

This eval is the decision-layer baseline. Containment and execution are proven
in their own tests; together they form the Phase C verification record.
