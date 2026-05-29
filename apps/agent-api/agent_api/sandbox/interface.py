"""The Sandbox interface — the swappability contract.

Threat-model commitment (THREAT_MODEL.md T11): Docker now, but behind an
abstract interface so stronger isolation (gVisor / Kata / Firecracker) can
replace it later without touching consumers. Day 33 ships DockerSandbox;
Day 34's shell takes a Sandbox-typed parameter so the swap is transparent.

Pure types — no Docker imports here, so this module is the stable contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ExecStatus(StrEnum):
    COMPLETED = "completed"     # ran to completion (exit_code may be nonzero)
    TIMEOUT = "timeout"          # killed by wall-clock timeout
    OOM = "oom"                  # killed by memory cap
    ERROR = "error"              # sandbox / infrastructure error


class MountMode(StrEnum):
    NONE = "none"                # no host filesystem visibility
    RO_PROJECT = "ro_project"    # project_root mounted read-only at /work


@dataclass(frozen=True)
class ExecRequest:
    """A request to run something inside the sandbox. argv is a structured
    list (not a shell string) — the sandbox does NOT spawn a shell unless the
    caller put 'sh -c' in argv themselves. That keeps shell semantics explicit."""
    argv: list[str]
    timeout_s: int = 30                    # wall-clock kill if exceeded
    memory_mb: int = 512
    cpus: float = 1.0
    network: bool = False                  # default OFF (no outbound)
    mount: MountMode = MountMode.RO_PROJECT
    workdir: str = "/work"                 # cwd inside the container
    stdin: str | None = None               # optional stdin piped in


@dataclass(frozen=True)
class ExecResult:
    status: ExecStatus
    exit_code: int                          # -1 if not completed
    stdout: str
    stderr: str
    duration_ms: int
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    error: str | None = None                # populated on status=error


class Sandbox(Protocol):
    """Implementations: DockerSandbox today, gVisor/microVM later."""
    async def execute(self, req: ExecRequest) -> ExecResult: ...
