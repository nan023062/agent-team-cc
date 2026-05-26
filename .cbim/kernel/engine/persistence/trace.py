"""persistence/trace.py — append-only trace.jsonl writer.

One JSON object per line. Summary only — full payloads stay in bb.json.

Two write surfaces:
  - ``append`` — one event, one line. Used by the Runner for the
    legacy yield/resume markers it writes itself.
  - ``append_many`` — batched flush of N events in a single file open.
    Used by the Runner to drain ``bb.trace`` entries collected during a
    tick (BT-node enter/exit events emitted by the in-tree instrumentation
    wrapper). Each entry that lacks a ``ts`` key is stamped at flush time.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def append(tick_dir: Path, entry: dict) -> None:
    tick_dir.mkdir(parents=True, exist_ok=True)
    target = tick_dir / "trace.jsonl"
    entry = {"ts": _now_iso(), **entry}
    line = json.dumps(entry, ensure_ascii=False)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def append_many(tick_dir: Path, entries: Iterable[dict]) -> int:
    """Append a batch of entries to ``trace.jsonl`` in a single open.

    Returns the count of lines written. Empty/None entries are skipped.
    Entries without a ``ts`` field are stamped with the flush timestamp;
    entries that already carry ``ts`` (e.g. recorded at enter-time by
    the instrumentation wrapper) are written verbatim.

    No-op (and no file open) when ``entries`` is empty — callers can
    blindly invoke this on every yield/done without producing empty
    flushes.
    """
    items = [e for e in entries if e]
    if not items:
        return 0
    tick_dir.mkdir(parents=True, exist_ok=True)
    target = tick_dir / "trace.jsonl"
    stamped: list[str] = []
    fallback_ts = _now_iso()
    for e in items:
        if "ts" not in e:
            e = {"ts": fallback_ts, **e}
        stamped.append(json.dumps(e, ensure_ascii=False))
    with target.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(stamped) + "\n")
    return len(stamped)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
