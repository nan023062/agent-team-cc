"""VectorIndex — cosine similarity over a VectorBlob.

Pure stdlib (math.fsum + sqrt). numpy is optional; if present we use it
for batch scoring but we never depend on it.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from engine.retrieval.store import VectorBlob


class VectorIndex:
    def __init__(self, blob: VectorBlob) -> None:
        self.blob = blob

    def upsert(self, doc_id: str, vec: list) -> None:
        self.blob.upsert(doc_id, vec)

    def delete(self, doc_id: str) -> None:
        self.blob.delete(doc_id)

    def search(
        self,
        query_vec: list,
        top_k: int,
        allowed_ids: Optional[set] = None,
    ) -> List[Tuple[str, float]]:
        if not self.blob.doc_ids:
            return []
        q_norm = _l2_norm(query_vec)
        if q_norm == 0.0:
            return []
        scored: List[Tuple[str, float]] = []
        for doc_id, vec in zip(self.blob.doc_ids, self.blob.vectors):
            if allowed_ids is not None and doc_id not in allowed_ids:
                continue
            d_norm = _l2_norm(vec)
            if d_norm == 0.0:
                continue
            dot = math.fsum(a * b for a, b in zip(query_vec, vec))
            sim = dot / (q_norm * d_norm)
            scored.append((doc_id, sim))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_k]


def _l2_norm(vec) -> float:
    return math.sqrt(math.fsum(x * x for x in vec))


def rrf_fuse(
    ranked_lists: List[List[Tuple[str, float]]],
    top_k: int,
    k: int = 60,
) -> List[Tuple[str, float]]:
    """Reciprocal Rank Fusion. k=60 per the original Cormack et al. 2009 paper.

    Returns combined ranking [(doc_id, rrf_score)] desc.
    """
    agg: dict = {}
    for ranked in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked, start=1):
            agg[doc_id] = agg.get(doc_id, 0.0) + 1.0 / (k + rank)
    out = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    return out[:top_k]
