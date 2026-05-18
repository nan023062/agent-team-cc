"""
cli.py — Command-line interface for MemoryEngine.

Used by hooks and agents. Run from project root (cwd matters for default paths).

Commands:
  add    <path> [--tier short|medium]
  query  <text> [--tier short|medium] [--top-k N] [--verbose]
  delete <path>
  reindex [--tier short|medium]
"""

import argparse
import sys
from pathlib import Path


def _build_engine(args: argparse.Namespace):
    """Instantiate ChromaBackend + MemoryEngine with resolved paths."""
    from .chroma_backend import ChromaBackend
    from .engine import MemoryEngine

    db_path = Path(getattr(args, "db_path", None) or "memory/store/.chroma")
    store_dir = Path(getattr(args, "store_dir", None) or "memory/store")
    backend = ChromaBackend(db_path=db_path)
    return MemoryEngine(backend=backend, store_dir=store_dir)


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="memory/engine/cli.py")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add")
    p_add.add_argument("path")
    p_add.add_argument("--tier", default="short", choices=["short", "medium"])

    # query
    p_query = sub.add_parser("query")
    p_query.add_argument("text")
    p_query.add_argument("--tier", choices=["short", "medium"], default=None)
    p_query.add_argument("--top-k", type=int, default=5, dest="top_k")
    p_query.add_argument("--verbose", action="store_true")

    # delete
    p_del = sub.add_parser("delete")
    p_del.add_argument("path")

    # reindex
    p_reindex = sub.add_parser("reindex")
    p_reindex.add_argument("--tier", choices=["short", "medium"], default=None)

    # shared optional overrides
    for p in [p_add, p_query, p_del, p_reindex]:
        p.add_argument("--db-path", dest="db_path", default=None)
        p.add_argument("--store-dir", dest="store_dir", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "add": cmd_add,
        "query": cmd_query,
        "delete": cmd_delete,
        "reindex": cmd_reindex,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
