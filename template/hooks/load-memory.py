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


def _load_config(cwd: Path) -> dict:
    defaults = {
        "query": {"load_top_k": 3, "entry_preview_chars": 800},
        "hooks": {"timeout_seconds": 30},
    }
    config_path = cwd / "memory" / "config.json"
    if config_path.exists():
        try:
            user = json.loads(config_path.read_text(encoding="utf-8"))
            for section, values in user.items():
                if section in defaults and isinstance(values, dict):
                    defaults[section].update(values)
        except Exception:
            pass
    return defaults


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
    cfg = _load_config(cwd)
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

    load_top_k = cfg["query"]["load_top_k"]
    timeout = cfg["hooks"]["timeout_seconds"]
    preview_chars = cfg["query"]["entry_preview_chars"]

    # Balanced query: engine queries each tier with load_top_k independently and interleaves
    try:
        result = subprocess.run(
            cli + ["query", "最近任务 决策 问题 阻塞", "--top-k", str(load_top_k), "--verbose"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
        )
        all_lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    except Exception:
        all_lines = []

    if not all_lines:
        sys.exit(0)

    # Parse "path  # tier=... date=... score=x.xx" lines (engine already deduplicates)
    entries = []
    for line in all_lines:
        path_str = line.split("#")[0].strip()
        p = Path(path_str) if Path(path_str).is_absolute() else cwd / path_str
        try:
            content = p.read_text(encoding="utf-8")
            entries.append(f"**{p.name}**\n{content[:preview_chars]}")
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
