"""arch_exec/_helpers.py — shared prompt/parser helpers for arch_exec leaves.

Kept minimal: every leaf needs (a) the user_request + knowledge_snapshot
header and (b) a tolerant JSON extractor that returns None on parse
failure so LlmActionLeaf can FAILURE-and-retry.
"""

from __future__ import annotations

import json
import re
from typing import Any

def render_header(bb) -> str:
    """Render the user_request + knowledge_snapshot block shared by all
    arch_exec sub-prompts."""
    user_request = (getattr(bb, "user_request", None) or "").strip() or "(空)"
    snapshot = getattr(bb, "knowledge_snapshot", None) or getattr(bb, "dna_snapshot", None)
    if snapshot is None:
        snap_block = "(无快照)"
    elif isinstance(snapshot, str):
        snap_block = snapshot.strip()[:2000] or "(空)"
    else:
        try:
            snap_block = json.dumps(snapshot, ensure_ascii=False, indent=2)[:2000]
        except (TypeError, ValueError):
            snap_block = repr(snapshot)[:2000]
    return (
        "### 用户请求\n"
        f"{user_request}\n\n"
        "### 知识快照\n"
        f"{snap_block}\n"
    )


def render_guide(node_id: str) -> str:
    """Render the per-node guidance lines from architect_execution._NODE_GUIDE.

    Imported lazily to avoid the circular import: loops/architect_execution.py
    tail-imports this package, and importing _NODE_GUIDE at module load
    would close the cycle.
    """
    from engine.execution.loops.architect_execution import _NODE_GUIDE
    lines = _NODE_GUIDE.get(node_id) or []
    return "\n".join(lines)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json(text: str) -> Any | None:
    """Best-effort JSON extractor.

    Tries (in order):
      1. parse the whole stripped string
      2. parse the first ```json ... ``` fenced block
      3. parse the first {...} or [...] balanced-ish substring
    Returns None on every failure so the caller can FAILURE.
    """
    if text is None:
        return None
    s = text.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        pass
    m = _JSON_BLOCK_RE.search(s)
    if m:
        try:
            return json.loads(m.group(1))
        except (ValueError, TypeError):
            pass
    # Fallback: slice from first '{' or '[' to its matching closer (greedy).
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        i = s.find(open_ch)
        j = s.rfind(close_ch)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(s[i : j + 1])
            except (ValueError, TypeError):
                continue
    return None
