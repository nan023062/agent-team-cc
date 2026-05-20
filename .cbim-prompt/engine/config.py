"""
engine/config.py — Read/write .cbim-prompt/config.json (unified user config).

All user-facing CBIM settings live here:
  target_project  — path of the project being developed
  memory          — overrides for memory engine defaults (optional)

Usage:
  python .cbim-prompt/engine config get <key>
  python .cbim-prompt/engine config set <key> <value>
  python .cbim-prompt/engine config show
"""

import json
import sys
from pathlib import Path


def find_config_path(start: Path | None = None) -> Path:
    """Walk up from start (default: cwd) to locate .cbim-prompt/config.json."""
    p = (start or Path.cwd()).resolve()
    for _ in range(6):
        candidate = p / ".cbim-prompt" / "config.json"
        if candidate.exists():
            return candidate
        if p.parent == p:
            break
        p = p.parent
    return (start or Path.cwd()).resolve() / ".cbim-prompt" / "config.json"


def load_config(start: Path | None = None) -> dict:
    """Return the parsed config dict (empty dict if file missing or invalid)."""
    path = find_config_path(start)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(data: dict, start: Path | None = None) -> None:
    path = find_config_path(start)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_config_get(args) -> int:
    data = load_config()
    val = data.get(args.key)
    if val is None:
        print("(not set)", file=sys.stderr)
        return 1
    print(val)
    return 0


def cmd_config_set(args) -> int:
    data = load_config()
    data[args.key] = args.value
    save_config(data)
    print(f"[config] {args.key} = {args.value}")
    return 0


def cmd_config_show(args) -> int:
    path = find_config_path()
    data = load_config()
    if not data:
        print(f"(empty — {path})", file=sys.stderr)
        return 0
    print(f"# {path}")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0
