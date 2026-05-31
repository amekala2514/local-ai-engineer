"""Classifier: enrich an Intent with computed sensitivity + risk signals.

Consumes the pattern data from sensitivity.py and produces the risk_signals
the engine (engine.py) evaluates. Pure functions over an Intent — no I/O, no
side effects, deterministic, so the mock-intent suite can assert exact output.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from agent_api.policy.intent import Intent, Tool, Action, Scope, RiskSignal
from agent_api.policy.sensitivity import (
    Sensitivity, SECRET_PATTERNS, CONFIG_PATTERNS,
)
from agent_api.settings import settings

# Destructive argument fragments scanned in args (shell/git). Conservative: a
# match flags destructive_flag, which the engine treats as deny-worthy.
_DESTRUCTIVE_FRAGMENTS = ("rm -rf", "rm -fr", "--force", "-f", "reset --hard",
                          "push --force", "force-with-lease", "clean -fd",
                          ":/", "> /", ">> /")
_MULTI_CMD_TOKENS = (";", "&&", "||", "|", "$(", "`", "\n")


def _norm_relpath(resource: str | None) -> tuple[str | None, bool]:
    """Resolve a resource against project_root. Returns (repo_relative_path,
    is_outside_repo). A resource that resolves outside the root is flagged."""
    if not resource:
        return None, False
    root = Path(settings.project_root).resolve()
    # Treat the resource as relative to root unless absolute.
    p = Path(resource)
    resolved = (p if p.is_absolute() else (root / p)).resolve()
    try:
        rel = resolved.relative_to(root)
        return str(rel), False
    except ValueError:
        return str(resolved), True   # escaped the root


def classify_sensitivity(rel_path: str | None) -> Sensitivity:
    """Match a repo-relative path against the pattern lists (most-sensitive
    first). Returns NORMAL if no match or no path."""
    if not rel_path:
        return Sensitivity.NORMAL
    # Match against both the bare path and its basename (patterns use ** and
    # bare forms). fnmatch doesn't treat ** specially, so also test basename.
    name = Path(rel_path).name
    for pat in SECRET_PATTERNS:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(name, pat.replace("**/", "")):
            return Sensitivity.SECRET
    for pat in CONFIG_PATTERNS:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(name, pat.replace("**/", "")):
            return Sensitivity.CONFIG
    return Sensitivity.NORMAL


def classify(intent: Intent) -> tuple[Sensitivity, list[RiskSignal]]:
    """Compute (sensitivity, risk_signals) for an intent. Pure + deterministic."""
    signals: list[RiskSignal] = []

    rel, outside = _norm_relpath(intent.resource)
    if outside:
        signals.append(RiskSignal.OUTSIDE_REPO)
    sensitivity = classify_sensitivity(rel)
    if sensitivity is Sensitivity.SECRET:
        signals.append(RiskSignal.SECRET_ADJACENT)
    elif sensitivity is Sensitivity.CONFIG:
        signals.append(RiskSignal.SENSITIVE_CONFIG)

    # Scan structured args for destructive fragments + multi-command tokens.
    joined = " ".join(intent.args).lower()
    if any(frag.lower() in joined for frag in _DESTRUCTIVE_FRAGMENTS):
        signals.append(RiskSignal.DESTRUCTIVE_FLAG)
    # multi_command: flag only when a shell separator appears as its OWN argv
    # element (a real chain like ['ls', ';', 'rm']), NOT when it's a character
    # inside a single element (e.g. the ';' in `python -c "import x; y"`, which
    # is legitimate code, not a shell chain). A separator hidden inside one
    # string element is left to the sandbox to contain — the allowlist + the
    # network-off, host-read-only sandbox are the hard guarantees; this signal
    # catches the obvious token-separated chain. (Day 34: fixed a false positive
    # where ';' inside `-c` code tripped this.)
    _SEPARATOR_TOKENS = {";", "&&", "||", "|", "&"}
    if any(arg.strip() in _SEPARATOR_TOKENS for arg in intent.args):
        signals.append(RiskSignal.MULTI_COMMAND)

    # Git push to a remote = remote write; force push is also destructive.
    if intent.action is Action.GIT_PUSH:
        signals.append(RiskSignal.REMOTE_WRITE)

    if intent.network:
        signals.append(RiskSignal.NETWORK)

    return sensitivity, signals
