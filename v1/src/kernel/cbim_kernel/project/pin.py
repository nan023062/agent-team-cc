"""Single accessor for ``.cbim/.pin`` — the project's pinned kernel version.

Reads only. All pin *writes* live in ``updater.migrate`` (or
``updater.upgrade.cli`` for the post-apply pin bump). The kernel is read-only
with respect to ``.cbim/.pin``.

Format: plain text, single-line version + trailing newline (e.g. ``1.3.1\n``).
"""
# write_pin moved to updater.migrate — kernel is read-only for .pin
from __future__ import annotations

from pathlib import Path

_PIN_FILE = ".pin"


def read_pin(project_root: Path) -> str | None:
    path = project_root / ".cbim" / _PIN_FILE
    try:
        text = path.read_text(encoding="utf-8").strip()
        return text if text else None
    except FileNotFoundError:
        return None
