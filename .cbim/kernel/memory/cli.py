"""
cli.py — Memory command implementations.

Dispatched by the unified `engine` CLI (see kernel/engine/cli.py). Invoke
via `cbim memory <command>`.

v2: only medium tier is writable. Passing `--tier short` is rejected at
crud.primitives._check_tier with ValueError.
"""

import argparse
import sys
from pathlib import Path

from ._config import load_config


def _default_store() -> Path:
    """Project state memory store: <project>/.cbim/memory/."""
    from context import cbim_dir
    return cbim_dir() / "memory"


def _build_backend(args: argparse.Namespace):
    """Build the default FileBackend + resolved store dir."""
    from memory.crud.file_backend import FileBackend

    store_dir = Path(getattr(args, "store_dir", None) or _default_store())
    return FileBackend(store_dir), store_dir


# ---------------------------------------------------------------------------
# Agent-facing commands
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> int:
    """Create a new memory entry file and index it."""
    from datetime import datetime

    from memory.crud.primitives import write as _crud_write

    load_config()  # surfaces config errors early
    backend, store_dir = _build_backend(args)
    tier = args.tier
    slug = args.slug.strip().replace(" ", "-")
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"{ts}-manual-{slug}.md"
    path = store_dir / tier / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args.content, encoding="utf-8")

    try:
        _crud_write(path, tier, backend)
    except ValueError as e:
        # Best to remove the file we just wrote so users don't have an
        # un-indexed entry lying around after a bad --tier flag.
        try:
            path.unlink()
        except OSError:
            pass
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(path)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    from memory.crud.primitives import write as _crud_write

    backend, _ = _build_backend(args)
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1
    try:
        _crud_write(path, args.tier, backend)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"[memory] indexed {path.name} (tier={args.tier})", file=sys.stderr)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    from memory import query as _q

    backend, store = _build_backend(args)
    tier = args.tier or None
    try:
        results = _q(args.text, tier=tier, limit=args.top_k,
                     backend=backend, store_dir=store)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for r in results:
        meta = r["metadata"]
        if args.verbose:
            print(
                f"{r['doc_id']}  "
                f"# tier={meta.get('tier','')} "
                f"date={meta.get('date','')} "
                f"score={r['score']:.4f}"
            )
        else:
            print(r["doc_id"])
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    from memory.crud.primitives import delete as _crud_delete

    backend, _ = _build_backend(args)
    _crud_delete(Path(args.path), backend)
    print(f"[memory] deleted {args.path}", file=sys.stderr)
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    # When --store-dir is given the user is targeting a non-default store and
    # the service (which always resolves <project>/.cbim/memory/) doesn't fit;
    # drive compaction.rebuild_and_verify locally.
    if getattr(args, "store_dir", None):
        from memory.compaction.rebuilder import rebuild_and_verify

        backend, store_dir = _build_backend(args)
        report = rebuild_and_verify(store_dir, backend)
        print(
            f"[memory] reindexed {report.indexed_count} entries; "
            f"drift checked={report.drift_checked} "
            f"drifted={report.drift_drifted} "
            f"repaired={report.drift_repaired} "
            f"failed={report.drift_failed}",
            file=sys.stderr,
        )
        return 0
    from services import memory_reindex
    summary = memory_reindex(tier=args.tier or "")
    print(f"[memory] {summary}", file=sys.stderr)
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    if getattr(args, "store_dir", None):
        from memory.compaction import sweep_expired

        backend, store_dir = _build_backend(args)
        count = sweep_expired(store_dir, backend, keep_days=args.keep_days)
        print(
            f"[memory] swept {count} stale candidates older than {args.keep_days} days",
            file=sys.stderr,
        )
        return 0
    from services import memory_cleanup
    summary = memory_cleanup(keep_days=args.keep_days)
    print(f"[memory] {summary}", file=sys.stderr)
    return 0
