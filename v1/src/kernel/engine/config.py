"""
engine/config.py — Read/write .cbim/config.json (unified user config).

All user-facing CBIM settings live here:
  memory          — overrides for memory engine defaults (optional)

The project root is always the directory containing .cbim/. There is no
configurable target-project path.

Usage:
  python .cbim/engine config get <key>
  python .cbim/engine config set <key> <value>
  python .cbim/engine config show
"""

import json
import sys
from pathlib import Path


def find_config_path(start: Path | None = None) -> Path:
    """Walk up from start (default: cwd) to locate .cbim/config.json."""
    p = (start or Path.cwd()).resolve()
    for _ in range(6):
        candidate = p / ".cbim" / "config.json"
        if candidate.exists():
            return candidate
        if p.parent == p:
            break
        p = p.parent
    return (start or Path.cwd()).resolve() / ".cbim" / "config.json"


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


def _split_path(key: str) -> list[str]:
    return key.split(".")


def _coerce(value_str: str):
    try:
        return json.loads(value_str)
    except (json.JSONDecodeError, ValueError):
        return value_str


def cmd_config_get(args) -> int:
    data = load_config()
    node = data
    for part in _split_path(args.key):
        if not isinstance(node, dict) or part not in node:
            print("(not set)", file=sys.stderr)
            return 1
        node = node[part]
    print(node)
    return 0


def cmd_config_set(args) -> int:
    data = load_config()
    parts = _split_path(args.key)
    value = _coerce(args.value)
    node = data
    for part in parts[:-1]:
        existing = node.get(part)
        if not isinstance(existing, dict):
            existing = {}
            node[part] = existing
        node = existing
    node[parts[-1]] = value
    save_config(data)
    print(f"[config] {args.key} = {value}")
    return 0


def cmd_config_show(args) -> int:
    path = find_config_path()
    data = load_config()
    if not data:
        print(f"(empty — {path})", file=sys.stderr)
        return 0
    print(f"# {path}")
    sys.stdout.buffer.write((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return 0
