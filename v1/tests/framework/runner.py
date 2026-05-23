"""Headless `claude` invocation + session-log capture, target-aware."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .result import Result
from .target import TestTarget


def _latest_session_log(project_root: Path) -> Path | None:
    logs = project_root / ".cbim" / "logs"
    if not logs.is_dir():
        return None
    candidates = sorted(logs.glob("session_*.log"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _parse_claude_json(stdout: str) -> tuple[int | None, int | None]:
    """Best-effort extraction of input/output token counts from `claude -p --output-format json`.

    The CLI's JSON shape is not part of CBIM's contract and may evolve. We try
    several plausible keys and silently fall back to (None, None) on any mismatch.
    """
    stdout = (stdout or "").strip()
    if not stdout:
        return (None, None)
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return (None, None)
    if not isinstance(data, dict):
        return (None, None)
    usage = data.get("usage") or data.get("token_usage") or {}
    if isinstance(usage, dict):
        i = usage.get("input_tokens") or usage.get("prompt_tokens")
        o = usage.get("output_tokens") or usage.get("completion_tokens")
        if isinstance(i, int) or isinstance(o, int):
            return (i if isinstance(i, int) else None, o if isinstance(o, int) else None)
    i = data.get("input_tokens")
    o = data.get("output_tokens")
    return (
        i if isinstance(i, int) else None,
        o if isinstance(o, int) else None,
    )


def run(target: TestTarget, prompt: str, timeout: int = 300) -> Result:
    """Run `claude -p <prompt>` against target.project_root and capture everything.

    Setup / teardown are driven by the target. JSON output is parsed best-effort
    for token usage; failures fall back to plain text and tokens stay None.
    """
    target.setup()
    try:
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = time.perf_counter()
        env = os.environ.copy()
        proc = subprocess.run(
            ["claude", "-p", "--output-format", "json", prompt],
            cwd=str(target.project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        wall = time.perf_counter() - start

        log_path = _latest_session_log(target.project_root)
        log_text = ""
        if log_path is not None and log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")

        in_tok, out_tok = _parse_claude_json(proc.stdout)

        return Result(
            target_root=target.project_root,
            prompt=prompt,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            wall_time_s=wall,
            session_log_path=log_path,
            session_log=log_text,
            started_at=started_at,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )
    finally:
        target.teardown()
