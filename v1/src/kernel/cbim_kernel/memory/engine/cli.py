"""
cli.py — Memory engine command implementations.

These cmd_* functions are dispatched by the unified `engine` CLI
(see .cbim/engine/cli.py). This module no longer exposes a `main()`
or `__main__` block — invoke via `python .cbim/engine memory <command>`.
"""

import argparse
import sys
from pathlib import Path

from .config import load_config


def _default_store() -> Path:
    """Project state memory store: <project>/.cbim/memory/store/."""
    from cbim_kernel.context import cbim_dir
    return cbim_dir() / "memory" / "store"


def _build_engine(args: argparse.Namespace):
    """Build MemoryEngine with the default FileBackend.

    To swap backends: replace FileBackend with any MemoryBackend subclass
    (e.g. ChromaBackend from .chroma_backend) — callers above are unaffected.
    """
    from .engine import MemoryEngine
    from .file_backend import FileBackend

    store_dir = Path(getattr(args, "store_dir", None) or _default_store())
    return MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)


# ---------------------------------------------------------------------------
# Hook-facing commands
# ---------------------------------------------------------------------------

def cmd_write_session(args: argparse.Namespace) -> int:
    from .writer import write_session

    cfg = load_config()
    store_dir = Path(getattr(args, "store_dir", None) or _default_store())
    engine = _build_engine(args)
    path = write_session(args.transcript_path, store_dir, engine, cfg)
    if path:
        print(f"[memory] wrote {path.name}", file=sys.stderr)
    return 0


def cmd_load_context(args: argparse.Namespace) -> int:
    from .loader import load_context

    cfg = load_config()
    store_dir = Path(getattr(args, "store_dir", None) or _default_store())
    engine = _build_engine(args)
    output = load_context(store_dir, engine, cfg)
    if output:
        print(output)
    return 0


# ---------------------------------------------------------------------------
# Agent-facing commands
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> int:
    """Create a new memory entry file and index it."""
    from datetime import datetime

    cfg = load_config()
    store_dir = Path(getattr(args, "store_dir", None) or _default_store())
    tier = args.tier
    slug = args.slug.strip().replace(" ", "-")
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"{ts}-manual-{slug}.md"
    path = store_dir / tier / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args.content, encoding="utf-8")

    engine = _build_engine(args)
    engine.add(path, tier)
    print(path)
    return 0


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
    """Deprecated. Use `python .cbim/engine dashboard` instead.

    Kept as a forwarding shim so existing wrappers / docs that still
    invoke `memory preview` keep working. Emits a single stderr warning
    and delegates straight to the top-level dashboard command.
    """
    print(
        "[deprecated] `memory preview` is now `python .cbim/engine dashboard`",
        file=sys.stderr,
    )

    # Forward to the top-level command. We synthesize its argparse Namespace
    # so we don't re-parse argv — the caller already gave us --port.
    from cbim_kernel.engine.cli import cmd_dashboard as _cmd_dashboard

    class _Forward:
        port = getattr(args, "port", None)
        no_browser = False  # legacy command never had this knob

    return _cmd_dashboard(_Forward())


