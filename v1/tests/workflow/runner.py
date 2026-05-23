"""Headless `claude` invocation + session-log capture."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClaudeRun:
    exit_code: int
    stdout: str
    stderr: str
    session_log_path: Path | None
    session_log: str
    wall_time_s: float


def _latest_session_log(project_root: Path) -> Path | None:
    logs = project_root / ".cbim" / "logs"
    if not logs.is_dir():
        return None
    candidates = sorted(logs.glob("session_*.log"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def run_claude(project_root: Path, prompt: str, timeout: int = 300) -> ClaudeRun:
    """Run `claude -p '<prompt>'` in project_root with a hard timeout.

    Uses `-p` (print/headless) so the CLI exits after one turn. Permissions
    are bypassed via the per-project settings.json `defaultMode` ("bypassPermissions")
    written by `engine init`, so no extra flags are needed.
    """
    start = time.monotonic()
    env = os.environ.copy()
    # Keep ANTHROPIC_API_KEY inheritance explicit; nothing else to inject.
    proc = subprocess.run(
        ["claude", "-p", prompt],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    wall = time.monotonic() - start

    log_path = _latest_session_log(project_root)
    log_text = ""
    if log_path is not None and log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")

    return ClaudeRun(
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        session_log_path=log_path,
        session_log=log_text,
        wall_time_s=wall,
    )
