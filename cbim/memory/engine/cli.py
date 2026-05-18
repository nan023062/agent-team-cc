"""
cli.py — Command-line interface for MemoryEngine.

Used by hooks and agents. Run from project root (cwd matters for default paths).

Commands:
  write-session <transcript_path>               # Stop hook
  load-context                                  # SessionStart hook
  add     <path> [--tier short|medium]
  query   <text> [--top-k N] [--verbose]        # balanced by default (both tiers)
  query   <text> --tier short|medium [--top-k N]
  delete  <path>
  reindex [--tier short|medium]
  cleanup [--keep-days N]
  preview [--port N]
"""

import argparse
import sys
from pathlib import Path

from .config import load_config


def _build_engine(args: argparse.Namespace):
    from .chroma_backend import ChromaBackend
    from .engine import MemoryEngine

    db_path = Path(getattr(args, "db_path", None) or "memory/store/.chroma")
    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    return MemoryEngine(backend=ChromaBackend(db_path=db_path), store_dir=store_dir)


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
    if args.verbose:
        results = engine.query_verbose(args.text, tier=tier, top_k=args.top_k)
        for r in results:
            meta = r["metadata"]
            print(
                f"{r['doc_id']}  "
                f"# tier={meta.get('tier','')} "
                f"date={meta.get('date','')} "
                f"score={r['score']:.4f}"
            )
    else:
        for path in engine.query(args.text, tier=tier, top_k=args.top_k):
            print(path)
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

    cbim_dir = Path(__file__).parent.parent.parent  # cbim/
    preview_dir = cbim_dir / "preview"
    cbim_str = str(cbim_dir)
    if cbim_str not in _sys.path:
        _sys.path.insert(0, cbim_str)
    from preview.server import start_server

    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    root_dir = cbim_dir.parent
    start_server(store_dir, preview_dir, cbim_dir, root_dir, port=args.port)
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config()

    parser = argparse.ArgumentParser(prog="memory/engine/cli.py")
    sub = parser.add_subparsers(dest="command")

    # write-session (Stop hook)
    p_write = sub.add_parser("write-session")
    p_write.add_argument("transcript_path")

    # load-context (SessionStart hook)
    sub.add_parser("load-context")

    # add
    p_add = sub.add_parser("add")
    p_add.add_argument("path")
    p_add.add_argument("--tier", default="short", choices=["short", "medium"])

    # query
    p_query = sub.add_parser("query")
    p_query.add_argument("text")
    p_query.add_argument("--tier", choices=["short", "medium"], default=None)
    p_query.add_argument("--top-k", type=int, default=cfg["query"]["default_top_k"],
                         dest="top_k")
    p_query.add_argument("--verbose", action="store_true")

    # delete
    p_del = sub.add_parser("delete")
    p_del.add_argument("path")

    # reindex
    p_reindex = sub.add_parser("reindex")
    p_reindex.add_argument("--tier", choices=["short", "medium"], default=None)

    # cleanup
    p_cleanup = sub.add_parser("cleanup")
    p_cleanup.add_argument(
        "--keep-days", type=int, default=cfg["short_term"]["keep_days"],
        dest="keep_days",
        help=f"Keep entries from the last N days (default: {cfg['short_term']['keep_days']})",
    )

    # preview
    p_preview = sub.add_parser("preview")
    p_preview.add_argument(
        "--port", type=int, default=8765,
        help="Local port to serve on (default: 8765)",
    )

    # shared path overrides for all subcommands
    for p in [p_write, p_add, p_query, p_del, p_reindex, p_cleanup, p_preview,
              sub.choices["load-context"]]:
        p.add_argument("--db-path", dest="db_path", default=None)
        p.add_argument("--store-dir", dest="store_dir", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "write-session": cmd_write_session,
        "load-context": cmd_load_context,
        "add": cmd_add,
        "query": cmd_query,
        "delete": cmd_delete,
        "reindex": cmd_reindex,
        "cleanup": cmd_cleanup,
        "preview": cmd_preview,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
