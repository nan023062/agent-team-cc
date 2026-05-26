"""engine.retrieval — Vector + keyword retrieval primitives.

Public API (5 functions, locked by contract.md):
  - index_upsert(source, doc_id, content, metadata)
  - index_delete(source, doc_id)
  - search(source, query, top_k=10, filters=None) -> list[Hit]
  - verify_consistency(source, mode) -> DriftReport
  - stats(source=None) -> IndexStats | list[IndexStats]

Public dataclasses:
  - Hit, DriftReport, IndexStats, RetrievalError

The facade is the only legitimate entry point. Provider selection, BM25 vs
vector routing, index file layout — all internal.
"""
from __future__ import annotations

from engine.retrieval.facade import (
    DriftReport,
    Hit,
    IndexStats,
    RetrievalError,
    index_delete,
    index_upsert,
    search,
    stats,
    verify_consistency,
)

__all__ = [
    "Hit",
    "DriftReport",
    "IndexStats",
    "RetrievalError",
    "index_upsert",
    "index_delete",
    "search",
    "verify_consistency",
    "stats",
]
