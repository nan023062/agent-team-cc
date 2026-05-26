"""actions/context_retrieval.py — ContextRetrieval leaf.

Runs after InitTick and before ModeClassify on every tick. Calls
``engine.retrieval.search`` four times (one per source) with the user
request as query, then writes the three-bucket dict to
``bb.retrieved_context``:

    {
        "recent_memory":    [Hit, ...],   # transcript + memory_medium
                                          #   merged by score desc
        "agents":           [Hit, ...],   # agents source
        "module_knowledge": [Hit, ...],   # dna source
    }

Each Hit is serialized via ``Hit.to_dict()`` so the blackboard payload is
JSON-friendly (the snapshot writer round-trips it through ``json.dumps``).

Failure semantics (per .dna/contract.md "失败不阻塞 tick"): every
retrieval call is individually try/except'd; whatever didn't crash gets
written, the rest land empty. The node always returns SUCCESS. The
outer ``@Catch`` wrapper in the tree is a belt-and-suspenders guarantee
for any unexpected blowup outside the per-source try blocks.
"""

from __future__ import annotations

from engine.core.node import Node, Status


# Per-source pull size. Kept modest — three buckets x 5 ≈ 15 hits per
# tick is enough recall for a downstream ModeClassify hint or a prompt
# rendering preamble, without bloating the bb snapshot.
_TOP_K_PER_SOURCE = 5


def _safe_search(source: str, query: str, top_k: int) -> list:
    """Call retrieval.search; swallow all errors and return [].

    Deferred import so test fixtures can monkeypatch
    ``engine.retrieval.search`` after the action module is imported.
    """
    try:
        from engine.retrieval import search
    except Exception:
        return []
    try:
        hits = search(source, query, top_k=top_k)
    except Exception:
        return []
    out = []
    for h in hits or []:
        try:
            out.append(h.to_dict())
        except AttributeError:
            # Already a dict (e.g. test stubs returning plain dicts).
            if isinstance(h, dict):
                out.append(h)
    return out


class ContextRetrieval(Node):
    """Pre-classify context pull.

    Reads ``bb.user_request``; writes ``bb.retrieved_context``. Never fails.
    """

    def __init__(self, *, name: str = "ContextRetrieval",
                 top_k_per_source: int = _TOP_K_PER_SOURCE) -> None:
        self.name = name
        self._top_k = top_k_per_source

    def tick(self, bb) -> Status:
        query = (bb.user_request or "").strip()
        empty = {
            "recent_memory": [],
            "agents": [],
            "module_knowledge": [],
        }
        if not query:
            bb.retrieved_context = empty
            return Status.SUCCESS

        transcript_hits = _safe_search("transcript", query, self._top_k)
        memory_hits = _safe_search("memory_medium", query, self._top_k)
        agents_hits = _safe_search("agents", query, self._top_k)
        dna_hits = _safe_search("dna", query, self._top_k)

        # BM25 scores are not comparable across independent corpora
        # (different N, avgdl, IDF scales) — fuse by rank instead.
        try:
            from engine.retrieval.index.vector import rrf_fuse

            transcript_ranked = [
                (h.get("doc_id"), float(h.get("score") or 0.0))
                for h in transcript_hits
                if h.get("doc_id") is not None
            ]
            memory_ranked = [
                (h.get("doc_id"), float(h.get("score") or 0.0))
                for h in memory_hits
                if h.get("doc_id") is not None
            ]
            # Build doc_id → hit lookup. Transcript first so transcript wins
            # on collision; setdefault preserves first-occurrence semantics.
            lookup: dict = {}
            for h in transcript_hits:
                did = h.get("doc_id")
                if did is not None:
                    lookup.setdefault(did, h)
            for h in memory_hits:
                did = h.get("doc_id")
                if did is not None:
                    lookup.setdefault(did, h)
            fused = rrf_fuse(
                [transcript_ranked, memory_ranked],
                top_k=2 * self._top_k,
                k=60,
            )
            recent = []
            for doc_id, rrf_score in fused:
                hit = lookup.get(doc_id)
                if hit is None:
                    continue
                hit = dict(hit)
                hit["score"] = rrf_score
                recent.append(hit)
        except ImportError:
            recent = transcript_hits + memory_hits

        bb.retrieved_context = {
            "recent_memory": recent,
            "agents": agents_hits,
            "module_knowledge": dna_hits,
        }
        return Status.SUCCESS
