"""Shared helpers for task success_check / arch_metrics_extract."""

from __future__ import annotations

import subprocess
from pathlib import Path


def code_lines_changed(project_root: Path, baseline_root: Path) -> tuple[int, int]:
    """(added, modified_or_deleted) compared file-by-file with the baseline copy.

    Walks current project_root, sums:
      - added lines = lines in files that don't exist in baseline + extra lines
        in modified files (current_len - baseline_len if positive).
      - modified_or_deleted = lines removed (baseline_len - current_len if positive).
    Counts only files under src/ and tests/, .py suffix.
    """
    added = 0
    removed = 0
    for sub in ("src", "tests"):
        cur_dir = project_root / sub
        base_dir = baseline_root / sub
        if not cur_dir.is_dir():
            continue
        for p in cur_dir.rglob("*.py"):
            rel = p.relative_to(project_root)
            base = baseline_root / rel
            cur_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            if not base.exists():
                added += len(cur_lines)
                continue
            base_lines = base.read_text(encoding="utf-8", errors="replace").splitlines()
            diff = len(cur_lines) - len(base_lines)
            if diff > 0:
                added += diff
            elif diff < 0:
                removed += -diff
    return added, removed


def base_arch_metrics(
    session_log: str,
    stdout: str,
    project_root: Path,
    baseline_root: Path,
) -> dict:
    """Extract architectural-stability metrics shared by all tasks.

    Heuristics (best-effort, no contract — same heuristic applied to both modes):
      - dispatch_count: occurrences of 'Agent(' or 'subagent_type' (Task tool calls)
      - dna_read_count: occurrences of '.dna/'
      - architect_invoked: dispatch lines that name 'architect'
      - turn_count: bullets/headings in session_log we can identify, falling back
        to count of '[TURN]' or assistant message separators.
      - code_lines_added / code_lines_removed
    """
    log = session_log or ""
    out = stdout or ""
    combined = log + "\n" + out
    dispatch_count = combined.count("subagent_type") + combined.count('"Agent("')
    if dispatch_count == 0:
        dispatch_count = combined.count("Task(") if "Task(" in combined else 0
    dna_read_count = combined.count(".dna/")
    architect_invoked = (
        combined.lower().count('"architect"') + combined.lower().count("'architect'")
    )
    turn_count = log.count("[TURN]")
    if turn_count == 0:
        turn_count = log.count("\n## ") + log.count("\n### ")
    added, removed = code_lines_changed(project_root, baseline_root)
    return {
        "dispatch_count": dispatch_count,
        "dna_read_count": dna_read_count,
        "architect_invoked": architect_invoked,
        "turn_count": turn_count,
        "code_lines_added": added,
        "code_lines_removed": removed,
    }


def run_pytest(project_root: Path) -> tuple[int, str]:
    """Run `pytest -q` in project_root. Returns (exit_code, combined output)."""
    try:
        proc = subprocess.run(
            ["pytest", "-q", "--no-header", "-x"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60,
            env=_pytest_env(project_root),
        )
    except FileNotFoundError:
        return (127, "pytest not on PATH")
    except subprocess.TimeoutExpired:
        return (124, "pytest timeout")
    return (proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


def _pytest_env(project_root: Path) -> dict:
    import os

    env = os.environ.copy()
    # Ensure project_root is importable so `from src.x import y` works.
    env["PYTHONPATH"] = f"{project_root}{':' + env['PYTHONPATH'] if env.get('PYTHONPATH') else ''}"
    return env
