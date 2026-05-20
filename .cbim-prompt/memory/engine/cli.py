"""
cli.py — Memory engine command implementations.

These cmd_* functions are dispatched by the unified `engine` CLI
(see cbim-prompt/engine/cli.py). This module no longer exposes a `main()`
or `__main__` block — invoke via `python -m engine memory <command>`.
"""

import argparse
import sys
from pathlib import Path

from .config import load_config


def _build_engine(args: argparse.Namespace):
    """Build MemoryEngine with the default FileBackend.

    To swap backends: replace FileBackend with any MemoryBackend subclass
    (e.g. ChromaBackend from .chroma_backend) — callers above are unaffected.
    """
    from .engine import MemoryEngine
    from .file_backend import FileBackend

    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    return MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)


# ---------------------------------------------------------------------------
# Hook-facing commands
# ---------------------------------------------------------------------------

def cmd_write_session(args: argparse.Namespace) -> int:
    from .writer import write_session

    cfg = load_config()
    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    engine = _build_engine(args)
    path = write_session(args.transcript_path, store_dir, engine, cfg)
    if path:
        print(f"[memory] wrote {path.name}", file=sys.stderr)
    return 0


def cmd_load_context(args: argparse.Namespace) -> int:
    from .loader import load_context

    cfg = load_config()
    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    engine = _build_engine(args)
    output = load_context(store_dir, engine, cfg)
    if output:
        print(output)
    return 0


# ---------------------------------------------------------------------------
# Agent-facing commands
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> int:
    engine = _build_engine(args)
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1
    engine.add(path, args.tier)
    print(f"[memory] indexed {path.name} (tier={args.tier})", file=sys.stderr)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    engine = _build_engine(args)
    tier = args.tier or None
    results = engine.query_verbose(args.text, tier=tier, top_k=args.top_k)
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
    engine = _build_engine(args)
    engine.delete(Path(args.path))
    print(f"[memory] deleted {args.path}", file=sys.stderr)
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    engine = _build_engine(args)
    tier = args.tier or None
    count = engine.reindex(tier=tier)
    print(f"[memory] reindexed {count} entries (tier={tier or 'all'})", file=sys.stderr)
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    engine = _build_engine(args)
    count = engine.cleanup_short(keep_days=args.keep_days)
    print(f"[memory] deleted {count} short-term entries older than {args.keep_days} days",
          file=sys.stderr)
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    import sys as _sys

    cbim_dir = Path(__file__).parent.parent.parent  # cbim-prompt/
    preview_dir = cbim_dir / "preview"
    cbim_str = str(cbim_dir)
    if cbim_str not in _sys.path:
        _sys.path.insert(0, cbim_str)
    from preview.server import start_server

    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    root_dir = cbim_dir.parent
    start_server(store_dir, preview_dir, cbim_dir, root_dir, port=args.port)
    return 0


