"""
_io.py — Atomic write helpers shared across resource objects.

All resource save paths go through atomic_write_text so a crash mid-write
leaves either the old file intact or no visible .tmp residue.
"""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text to path atomically via <path>.tmp + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
