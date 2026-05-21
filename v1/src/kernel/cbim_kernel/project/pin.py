"""Single accessor for ``.cbim/.pin`` — the project's pinned kernel version.

All reads and writes of the pin file go through this module. No other code in
the kernel should open ``.cbim/.pin`` directly.

Format: plain text, single-line version + trailing newline (e.g. ``1.3.1\n``).
"""
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


def write_pin(project_root: Path, version: str) -> None:
    cbim_dir = project_root / ".cbim"
    cbim_dir.mkdir(parents=True, exist_ok=True)
    tmp = cbim_dir / f"{_PIN_FILE}.tmp"
    tmp.write_text(f"{version}\n", encoding="utf-8")
    tmp.replace(cbim_dir / _PIN_FILE)
