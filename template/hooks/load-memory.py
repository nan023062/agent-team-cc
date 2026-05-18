"""
load-memory.py — SessionStart hook: inject recent memory entries as context.

Receives JSON via stdin (Claude Code SessionStart event):
  { "cwd": "...", "session_id": "..." }

Queries memory_query.py for recent entries and outputs them as additionalContext
so the main agent starts each session with recent team memory already loaded.
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
    query_script = cwd / "memory" / "scripts" / "memory_query.py"
    entries_dir = cwd / "memory" / "entries"

    # Bail out if memory system isn't set up yet
    if not query_script.exists() or not entries_dir.exists():
        sys.exit(0)
    if not any(entries_dir.glob("*.md")):
        sys.exit(0)

    python = find_python(cwd)
    if not python:
        sys.exit(0)

    try:
        result = subprocess.run(
            [python, str(query_script), "最近任务 决策 问题 阻塞", "--top-k", "5", "--verbose"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=30,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    except Exception:
        sys.exit(0)

    if not lines:
        sys.exit(0)

    # Parse "path  # agent=xxx date=xxx score=x.xx" lines
    entries = []
    for line in lines:
        path_str = line.split("#")[0].strip()
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
