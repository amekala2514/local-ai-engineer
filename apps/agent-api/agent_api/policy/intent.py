"""The tool-agnostic Intent — a structured description of a proposed action.

Every action-taking tool (filesystem, git, shell, code_exec) constructs an
Intent and submits it to the policy engine BEFORE doing anything. Tools never
decide their own safety; they declare what they want to do, and the engine
(Day 29) decides whether it happens.

Design principle: policy quality depends on the structure of the thing being
evaluated. A raw command string can't be reasoned about safely; typed
attributes can. So the Intent is tool-agnostic — a filesystem write and a
shell command that writes a file converge on the same "write resource X"
shape, so policy rules don't have to be reinvented per tool.

This module defines DATA ONLY. The evaluator that consumes Intents and the
classifier that computes risk_signals are Day 29.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Tool(StrEnum):
    FILESYSTEM = "filesystem"
    GIT = "git"
    SHELL = "shell"
    CODE_EXEC = "code_exec"


class Action(StrEnum):
    # filesystem
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    LIST_DIR = "list_dir"
    # git
    GIT_STATUS = "git_status"      # status / diff / log — read-only
    GIT_COMMIT = "git_commit"
    GIT_BRANCH = "git_branch"      # create / checkout
    GIT_PUSH = "git_push"
    # shell / code
    RUN_COMMAND = "run_command"
    EXEC_CODE = "exec_code"


class Scope(StrEnum):
    SINGLE = "single"      # one specific resource
    GLOB = "glob"          # a glob pattern
    SUBTREE = "subtree"    # a directory subtree


class Reversibility(StrEnum):
    REVERSIBLE = "reversible"          # read-only or trivially undoable
    PATCH_BACKUP = "patch_backup"      # a backup/patch is saved before the change
    TEMP_BRANCH = "temp_branch"        # git op shielded by a temp branch
    IRREVERSIBLE = "irreversible"      # cannot be undone (e.g. force push)


# Risk signals are COMPUTED by the classifier (Day 29) and attached to the
# Intent before evaluation. Defined here as the canonical vocabulary so tools,
# classifier, and engine all agree on the strings.
class RiskSignal(StrEnum):
    SECRET_ADJACENT = "secret_adjacent"        # touches a secrets-class path
    SENSITIVE_CONFIG = "sensitive_config"      # CI / deploy / git-internal config
    OUTSIDE_REPO = "outside_repo"              # resource escapes the project root
    DESTRUCTIVE_FLAG = "destructive_flag"      # rm -rf, reset --hard, etc.
    REMOTE_WRITE = "remote_write"              # writes to a remote (git push)
    NETWORK = "network"                        # requires outbound network
    MULTI_COMMAND = "multi_command"            # chained/compound shell command


class Intent(BaseModel):
    """A proposed action, submitted to the policy engine before execution.

    Validation-at-construction is itself a safety property: a malformed intent
    can't reach the evaluator. Frozen so an intent can't be mutated after the
    classifier/engine has seen it.
    """
    model_config = {"frozen": True}

    tool: Tool
    action: Action
    resource: str | None = Field(default=None, description="normalized path / branch / remote")
    scope: Scope = Scope.SINGLE
    args: list[str] = Field(default_factory=list, description="structured args, never a raw string")
    cwd: str | None = None
    env_profile: str = Field(default="minimal", description="which env/secret profile this runs under")
    network: bool = Field(default=False, description="does this action need outbound network")
    reversibility: Reversibility = Reversibility.REVERSIBLE
    risk_signals: list[RiskSignal] = Field(
        default_factory=list,
        description="computed by the classifier (Day 29); empty at construction time",
    )
