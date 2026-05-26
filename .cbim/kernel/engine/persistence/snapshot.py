"""persistence/snapshot.py — bb.json + resume.json atomic writers + readers.

Atomic write via temp file + rename. bb.json is rewritten in full on dirty
(no diff patches — by design, simpler recovery, per README §3).

Schema version is owned by core.blackboard.SCHEMA_VERSION (current: 2 after
the v3 simplification). Snapshots written by a different schema version are
treated as orphaned: read_bb() logs a warning and returns None so the engine
can drop them without crashing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from engine.core.blackboard import SCHEMA_VERSION

_log = logging.getLogger(__name__)


def write_bb(tick_dir: Path, bb) -> None:
    tick_dir.mkdir(parents=True, exist_ok=True)
    target = tick_dir / "bb.json"
    tmp = tick_dir / "bb.json.tmp"
    payload = bb.to_dict()
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
                   encoding="utf-8")
    os.replace(tmp, target)


def read_bb(tick_dir: Path):
    from engine.core.blackboard import Blackboard
    p = tick_dir / "bb.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    sv = raw.get("schema_version", 1)
    if sv != SCHEMA_VERSION:
        _log.warning(
            "bb.json at %s has schema_version=%s (expected %s); dropping as orphaned",
            p, sv, SCHEMA_VERSION,
        )
        return None
    return Blackboard.from_dict(raw)


def write_resume(tick_dir: Path, payload: dict) -> None:
    tick_dir.mkdir(parents=True, exist_ok=True)
    target = tick_dir / "resume.json"
    tmp = tick_dir / "resume.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
                   encoding="utf-8")
    os.replace(tmp, target)


def read_resume(tick_dir: Path) -> dict | None:
    p = tick_dir / "resume.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def delete_resume(tick_dir: Path) -> None:
    p = tick_dir / "resume.json"
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _json_default(obj):
    # Handle dataclass-like objects (DispatchRequest, Subtask) by attribute dict.
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    return str(obj)
