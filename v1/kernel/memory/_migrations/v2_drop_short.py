"""
One-shot migration: drop `.cbim/memory/short/` directory.

v2 of the memory module removed the short tier entirely (CC transcripts are
now the short-term layer). Pre-v2 stores carried 300+ short entries that are
not worth distilling — most were near-empty signal stubs.

Per the Phase 2 work order this migration deletes short/ outright (no copy,
no per-entry preservation) and prints a one-line audit so the deletion is
visible in the operator's terminal / hook log.

Usage:
    python -m memory._migrations.v2_drop_short [--store-dir <path>]

If --store-dir is omitted the migration resolves <project>/.cbim/memory via
the standard `context.cbim_dir()` walk. Idempotent: running on a store that
already lacks short/ prints "no short/ directory (already migrated)" and
exits 0.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _resolve_store_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    try:
        from context import cbim_dir
        return cbim_dir() / "memory"
    except Exception:
        return Path.cwd() / ".cbim" / "memory"


def run(store_dir: Path) -> int:
    short_dir = store_dir / "short"
    if not short_dir.exists():
        print(f"[migration] {short_dir}: no short/ directory (already migrated)")
        return 0

    entries = [p for p in short_dir.glob("*.md") if p.is_file()]
    extras = [p for p in short_dir.iterdir() if p.is_file() and p not in entries]
    print(
        f"[migration] {short_dir}: deleting {len(entries)} .md entries "
        f"and {len(extras)} other files"
    )
    shutil.rmtree(short_dir)
    print(f"[migration] {short_dir}: removed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Drop .cbim/memory/short/ (v2 migration).")
    ap.add_argument("--store-dir", default=None,
                    help="Memory store directory (default: <project>/.cbim/memory)")
    args = ap.parse_args()
    return run(_resolve_store_dir(args.store_dir))


if __name__ == "__main__":
    sys.exit(main())
