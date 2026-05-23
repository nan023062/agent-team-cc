"""
loader.py — Session context loader.

Encapsulates querying recent memory and building the additionalContext payload
for Claude Code's SessionStart hook. Hooks are not aware of this logic.

Session recovery is done by reading .cbim/logs/session_*.log directly —
the last-session.md file is no longer used.
"""

import json
from pathlib import Path

from .engine import MemoryEngine


def load_context(store_dir: Path, engine: MemoryEngine, cfg: dict) -> str | None:
    """Build session context from recent memory entries.

    Returns JSON string '{"additionalContext": "..."}' on success, None if empty.
    The hook prints this directly to stdout — Claude Code picks it up automatically.
    """
    parts: list[str] = []

    # Recent memory — backend determines ordering (recency or semantic).
    if store_dir.exists():
        has_entries = any((store_dir / t).glob("*.md") for t in ("short", "medium"))
        if has_entries:
            top_k = cfg["query"]["load_top_k"]
            preview_chars = cfg["query"]["entry_preview_chars"]
            # FileBackend: recency order, text arg ignored.
            # SemanticBackend: cosine similarity to this query text.
            results = engine.query_verbose("最近任务 决策 问题 阻塞", top_k=top_k)
            entries = []
            for r in results:
                # doc_id is always an absolute path produced by the backend.
                p = Path(r["doc_id"])
                try:
                    content = p.read_text(encoding="utf-8")
                    entries.append(f"**{p.name}**\n{content[:preview_chars]}")
                except (FileNotFoundError, PermissionError):
                    pass
            if entries:
                parts.append(
                    "以下是团队近期工作记忆（自动加载，供本次 session 参考）：\n\n"
                    + "\n\n---\n\n".join(entries)
                )

    if not parts:
        return None

    context = "\n\n---\n\n".join(parts)
    return json.dumps({"additionalContext": context}, ensure_ascii=False)
