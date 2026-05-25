"""persistence/trace.py — append-only trace.jsonl writer.

One JSON object per line. Summary only — full payloads stay in bb.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append(tick_dir: Path, entry: dict) -> None:
    tick_dir.mkdir(parents=True, exist_ok=True)
    target = tick_dir / "trace.jsonl"
    entry = {"ts": _now_iso(), **entry}
    line = json.dumps(entry, ensure_ascii=False)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
