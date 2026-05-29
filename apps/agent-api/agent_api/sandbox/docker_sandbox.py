"""Docker-backed Sandbox implementation.

Defaults are deliberately conservative: network OFF, host repo read-only at
/work, non-root user (1000:1000), 512MB memory cap, 1 CPU, 30s wall-clock,
1MB output caps per stream. The conservative profile is the *Day 33 default*;
Day 34+ can adjust per-request via ExecRequest where genuinely needed.

Image is pinned (python:3.12-slim) — same 'never trust latest' lesson as
Tempo/Grafana from Phase B observability.

The container is run with --rm so it cleans up after each call; no persistent
sandbox container. That trades a small per-call startup cost (~hundreds of ms)
for cleaner isolation between calls.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from agent_api.sandbox.interface import (
    ExecRequest, ExecResult, ExecStatus, MountMode, Sandbox,
)
from agent_api.settings import settings

_DEFAULT_IMAGE = "python:3.12-slim"
_OUTPUT_CAP = 1_000_000   # 1MB per stream, truncate beyond


class DockerSandbox(Sandbox):
    def __init__(self, image: str = _DEFAULT_IMAGE) -> None:
        self._image = image

    async def execute(self, req: ExecRequest) -> ExecResult:
        # Build the docker run argv. Order matters: flags before image before argv.
        docker_args: list[str] = [
            "docker", "run", "--rm",
            "--user", "1000:1000",
            "--memory", f"{req.memory_mb}m",
            "--cpus", str(req.cpus),
            # Stop after timeout_s + a small grace; we also enforce wall-clock outside.
            "--stop-timeout", "1",
            # Hardening: drop all capabilities, no privilege escalation.
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            # Read-only root filesystem; /scratch is a writable tmpfs.
            "--read-only",
            "--tmpfs", "/scratch:size=64m,mode=0700",
            "--tmpfs", "/tmp:size=64m,mode=1777",
            "--workdir", req.workdir,
        ]
        if not req.network:
            docker_args += ["--network", "none"]
        if req.mount is MountMode.RO_PROJECT:
            root = Path(settings.project_root).resolve()
            docker_args += ["--volume", f"{root}:/work:ro"]
        # stdin support
        use_stdin = req.stdin is not None
        if use_stdin:
            docker_args.append("-i")

        docker_args += [self._image, *req.argv]

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_args,
                stdin=asyncio.subprocess.PIPE if use_stdin else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return ExecResult(
                status=ExecStatus.ERROR, exit_code=-1, stdout="", stderr="",
                duration_ms=0, error="docker binary not found",
            )

        async def _communicate():
            return await proc.communicate(
                input=req.stdin.encode() if use_stdin else None
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(_communicate(), timeout=req.timeout_s)
        except asyncio.TimeoutError:
            # Kill the docker client and let --rm clean the container.
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecResult(
                status=ExecStatus.TIMEOUT, exit_code=-1, stdout="", stderr="",
                duration_ms=duration_ms,
                error=f"wall-clock timeout after {req.timeout_s}s",
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        # Output caps — defend against runaway emitters.
        stdout_truncated = len(stdout_b) > _OUTPUT_CAP
        stderr_truncated = len(stderr_b) > _OUTPUT_CAP
        stdout_s = stdout_b[:_OUTPUT_CAP].decode("utf-8", errors="replace")
        stderr_s = stderr_b[:_OUTPUT_CAP].decode("utf-8", errors="replace")

        exit_code = proc.returncode if proc.returncode is not None else -1
        # Detect OOM kill (Docker exits 137 = SIGKILL, often OOM-driven).
        # Heuristic: exit 137 with empty stdout/short stderr suggests memory cap hit.
        status = ExecStatus.COMPLETED
        if exit_code == 137:
            status = ExecStatus.OOM

        return ExecResult(
            status=status, exit_code=exit_code,
            stdout=stdout_s, stderr=stderr_s, duration_ms=duration_ms,
            stdout_truncated=stdout_truncated, stderr_truncated=stderr_truncated,
        )
