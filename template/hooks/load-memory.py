"""
load-memory.py — SessionStart hook: inject recent memory entries as context.

Receives JSON via stdin (Claude Code SessionStart event):
  { "cwd": "...", "session_id": "..." }

Queries both short-term and medium-term memory via the engine CLI and outputs
them as additionalContext so the main agent starts each session with relevant
team memory already loaded.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def find_python(cwd: Path) -> str | None:
    for candidate in [
        cwd / ".venv" / "bin" / "python",
        cwd / ".venv" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = Path(event.get("cwd", os.getcwd()))
    store_dir = cwd / "memory" / "store"

    # Bail out early if memory store isn't set up yet
    if not store_dir.exists():
        sys.exit(0)
    has_entries = any((store_dir / t).glob("*.md") for t in ("short", "medium"))
    if not has_entries:
        sys.exit(0)

    python = find_python(cwd)
    if not python:
        sys.exit(0)

    cli = [python, "-m", "memory.engine.cli"]

    def run_query(extra_args: list[str]) -> list[str]:
        try:
            result = subprocess.run(
                cli + ["query", "最近任务 决策 问题 阻塞"] + extra_args,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                timeout=30,
            )
            return [l.strip() for l in result.stdout.splitlines() if l.strip()]
        except Exception:
            return []

    # Query both tiers independently to ensure both are represented
    short_lines = run_query(["--tier", "short", "--top-k", "3", "--verbose"])
    medium_lines = run_query(["--tier", "medium", "--top-k", "3", "--verbose"])
    all_lines = short_lines + medium_lines

    if not all_lines:
        sys.exit(0)

    # Parse "path  # tier=... date=... score=x.xx" lines
    entries = []
    seen: set[str] = set()
    for line in all_lines:
        path_str = line.split("#")[0].strip()
        if path_str in seen:
            continue
        seen.add(path_str)
        p = Path(path_str) if Path(path_str).is_absolute() else cwd / path_str
        try:
            content = p.read_text(encoding="utf-8")
            entries.append(f"**{p.name}**\n{content[:800]}")
        except (FileNotFoundError, PermissionError):
            pass

    if not entries:
        sys.exit(0)

    context = (
        "以下是团队近期工作记忆（自动加载，供本次 session 参考）：\n\n"
        + "\n\n---\n\n".join(entries)
    )

    print(json.dumps({"additionalContext": context}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
