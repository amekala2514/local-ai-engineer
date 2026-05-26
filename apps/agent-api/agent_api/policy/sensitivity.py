"""Resource-sensitivity definitions: which paths are protected and how.

DATA ONLY. The classifier that matches a path against these patterns and the
engine that acts on the labels are Day 29. This module is the single source of
truth for "what counts as sensitive" so policy, context-filtering, and audit
all agree.

Two distinct concerns the labels drive (Day 29+):
  1. WRITE policy — sensitive resources are write-denied (not just approve).
  2. CONTEXT policy — SECRET-class content never enters the model's context
     window (it can't leak what it can't see). CONFIG-class is readable as
     context but write-denied.
"""

from __future__ import annotations

from enum import StrEnum


class Sensitivity(StrEnum):
    SECRET = "secret"      # credentials/keys — write-denied AND excluded from context
    CONFIG = "config"      # CI/deploy/git-internal — readable as context, write-denied
    NORMAL = "normal"      # ordinary project files — read auto, write approve


# Glob-style patterns (matched against repo-relative paths in Day 29).
# Ordered most-sensitive-first; the classifier returns the first match.
SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    "**/id_rsa",
    "**/id_rsa.*",
    "**/id_ed25519",
    "**/id_ed25519.*",
    "**/known_hosts",
    "**/*.pem",
    "**/*.key",
    "**/credentials",
    "**/secrets.*",
    "**/*.secret",
    "**/.npmrc",          # can hold auth tokens
    "**/.pypirc",         # can hold auth tokens
)

CONFIG_PATTERNS: tuple[str, ...] = (
    ".github/workflows/**",
    ".gitlab-ci.yml",
    ".circleci/**",
    "deploy/**",
    "**/Dockerfile",
    "docker-compose*.yml",
    ".git/hooks/**",       # git hooks execute — treat as sensitive config
    ".git/config",
)

# The default policy per sensitivity class (consumed by the Day 29 engine).
# (write_decision, in_context) — write_decision is the hardest the engine may
# return for a write to this class; in_context gates whether reads feed the LLM.
DEFAULT_POLICY: dict[Sensitivity, dict[str, object]] = {
    Sensitivity.SECRET: {"write_decision": "deny", "in_context": False},
    Sensitivity.CONFIG: {"write_decision": "deny", "in_context": True},
    Sensitivity.NORMAL: {"write_decision": "approve", "in_context": True},
}
