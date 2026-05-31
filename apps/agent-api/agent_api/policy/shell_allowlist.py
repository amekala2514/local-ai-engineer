"""Shell command allowlist (Day 34, v1) — DATA ONLY.

The TIGHTEST of the three layers a shell command passes:
  1. allowlist (here) — is argv[0] a known-workflow binary at all?
  2. policy gate    — risk signals (destructive flag, chaining, network, ...)
  3. sandbox        — runs contained (network off, host read-only)

v1 is just-the-binary: we check argv[0] against a small set and let the
classifier's existing risk machinery handle the arguments (destructive flags,
';'/'&&'/'|' chaining) and the sandbox contain whatever runs. A full
arg-constraint DSL is deliberately deferred — the sandbox bounds the blast
radius, so the allowlist can stay small and pure (the 'mistakes-primary'
threat model cashing out: the allowlist stops categories of mistake, the
sandbox contains the rest).
"""

from __future__ import annotations

# Known-workflow binaries permitted in shell v1. Everything else is refused
# before it reaches the policy gate.
ALLOWED_BINARIES: frozenset[str] = frozenset({
    # test / build / run
    "pytest", "python", "python3", "go", "npm", "node", "uv",
    # read-only introspection
    "ls", "cat", "head", "tail", "wc", "rg", "grep", "find", "echo",
    # git (read-only subcommands only — the classifier/gate still apply)
    "git",
})


def binary_allowed(argv: list[str]) -> bool:
    """True if argv[0] (the binary) is on the allowlist. Empty argv -> False."""
    if not argv:
        return False
    # argv[0] may be a path like /usr/bin/pytest; check the basename too.
    import os
    binary = argv[0]
    return binary in ALLOWED_BINARIES or os.path.basename(binary) in ALLOWED_BINARIES
