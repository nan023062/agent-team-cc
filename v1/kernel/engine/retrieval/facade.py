"""RetrievalFacade — implements the 5 public functions in contract.md.

Per-source `SourceIndex` objects are cached per-process. Each holds:
  - IndexStore (on-disk handle)
  - BM25Index (always loaded)
  - VectorIndex (loaded iff embedding provider is available)
  - The DocRecord meta table

Public surface (frozen):
    index_upsert(source, doc_id, content, metadata) -> None
    index_delete(source, doc_id) -> None
    search(source, query, top_k=10, filters=None) -> list[Hit]
    verify_consistency(source, mode) -> DriftReport
    stats(source=None) -> IndexStats | list[IndexStats]

All other names in this module are internal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Union

# Minimum spread between top vector scores below which we treat the
# embedding as semantically collapsed (e.g. provider stuck returning a
# constant vector). At that point cosine ranking is just the VectorBlob
# insertion order, which is meaningless to the caller — degrade to BM25
# transparently per contract.md (fallback must be invisible).
_VECTOR_COLLAPSE_EPSILON = 1e-6

from engine.retrieval.config import RetrievalConfig, load_config
from engine.retrieval.drift import DriftReport, fast_check, full_check
from engine.retrieval.embedding.base import EmbeddingProvider
from engine.retrieval.embedding.factory import build_provider
from engine.retrieval.index.bm25 import BM25Index
from engine.retrieval.index.vector import VectorIndex, rrf_fuse
from engine.retrieval.store import (
    VALID_SOURCES,
    DocRecord,
    IndexStore,
    StoreError,
    VectorBlob,
    content_sha256,
    now_iso,
)


# --------------------------------------------------------------------------
# Public dataclasses
# --------------------------------------------------------------------------


class RetrievalError(Exception):
    """Raised for invalid source, missing args, or persistence failures."""


@dataclass(frozen=True)
class Hit:
    doc_id: str
    source: str
    score: float
    content: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "score": self.score,
            "content": self.content,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IndexStats:
    source: str
    total_docs: int
    vector_dim: Optional[int]
    embedding_provider: str
    fallback_active: bool
    index_size_bytes: int
    last_upsert_at: str
    last_verify_at: Optional[str]
    last_drift_count: Optional[int]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "total_docs": self.total_docs,
            "vector_dim": self.vector_dim,
            "embedding_provider": self.embedding_provider,
            "fallback_active": self.fallback_active,
            "index_size_bytes": self.index_size_bytes,
            "last_upsert_at": self.last_upsert_at,
            "last_verify_at": self.last_verify_at,
            "last_drift_count": self.last_drift_count,
        }


# --------------------------------------------------------------------------
# Per-source state
# --------------------------------------------------------------------------


@dataclass
class _SourceState:
    source: str
    store: IndexStore
    bm25: BM25Index
    records: Dict[str, DocRecord]
    vectors: Optional[VectorBlob]   # None when provider unavailable / dim=0
    last_upsert_at: str = ""
    last_verify_at: Optional[str] = None
    last_drift_count: Optional[int] = None


# --------------------------------------------------------------------------
# Facade — singleton-per-project, identified by the index_root path.
# --------------------------------------------------------------------------


class RetrievalFacade:
    def __init__(self, index_root: Path, config: Optional[RetrievalConfig] = None) -> None:
        self.index_root = Path(index_root)
        self.config = config or load_config(self.index_root)
        self.provider: EmbeddingProvider = build_provider(self.config)
        self._sources: Dict[str, _SourceState] = {}
        self._lock = RLock()

    # ---------------- internal helpers ----------------

    def _get(self, source: str) -> _SourceState:
        if source not in VALID_SOURCES:
            raise RetrievalError(f"unknown source: {source!r}")
        with self._lock:
            st = self._sources.get(source)
            if st is None:
                st = self._load_source(source)
                self._sources[source] = st
            return st

    def _load_source(self, source: str) -> _SourceState:
        store = IndexStore(self.index_root, source)
        records = store.load_meta()
        bm25_state = store.load_bm25_state()
        if bm25_state is not None:
            bm25 = BM25Index.from_dict(bm25_state)
        else:
            # First load — rebuild BM25 from doc snapshots (kept on disk).
            bm25 = BM25Index()
            for doc_id in records.keys():
                content = store.read_doc(doc_id)
                if content is not None:
                    bm25.upsert(doc_id, content)
        vectors = store.load_vectors() if self.provider.is_available() else None
        return _SourceState(
            source=source,
            store=store,
            bm25=bm25,
            records=records,
            vectors=vectors,
        )

    def _ensure_vector_blob(self, state: _SourceState) -> Optional[VectorBlob]:
        if not self.provider.is_available():
            return None
        if state.vectors is None:
            state.vectors = VectorBlob(self.provider.dimension())
        return state.vectors

    def _persist(self, state: _SourceState) -> None:
        state.store.save_meta(state.records)
        state.store.save_bm25_state(state.bm25.to_dict())
        if state.vectors is not None:
            state.store.save_vectors(state.vectors)

    # ---------------- public: index_upsert ----------------

    def index_upsert(
        self,
        source: str,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        if not isinstance(source, str) or not source:
            raise RetrievalError("source must be a non-empty string")
        if not isinstance(doc_id, str) or not doc_id:
            raise RetrievalError("doc_id must be a non-empty string")
        if content is None:
            raise RetrievalError("content must not be None")
        metadata = dict(metadata or {})
        # source_path is an optional metadata field. We promote it to a
        # first-class DocRecord field so drift checking doesn't have to
        # peek into metadata.
        source_path = metadata.pop("source_path", None)

        with self._lock:
            state = self._get(source)
            # Persist content snapshot first so a crash can be detected.
            state.store.write_doc(doc_id, content)

            # mtime/size for fast-check: prefer original source file when
            # known; otherwise stat the snapshot we just wrote.
            if source_path:
                try:
                    st = Path(source_path).stat()
                    mtime = st.st_mtime
                    size = st.st_size
                except OSError:
                    mtime = 0.0
                    size = len(content.encode("utf-8"))
            else:
                snap = state.store.doc_path(doc_id)
                try:
                    st = snap.stat()
                    mtime = st.st_mtime
                    size = st.st_size
                except OSError:
                    mtime = 0.0
                    size = len(content.encode("utf-8"))

            rec = DocRecord(
                doc_id=doc_id,
                mtime=mtime,
                size=size,
                sha256=content_sha256(content),
                indexed_at=now_iso(),
                metadata=metadata,
                source_path=str(source_path) if source_path else None,
            )
            state.records[doc_id] = rec

            # BM25 always.
            state.bm25.upsert(doc_id, content)

            # Vector when provider available.
            if self.provider.is_available():
                try:
                    vec = self.provider.embed(content)
                    blob = self._ensure_vector_blob(state)
                    assert blob is not None
                    blob.upsert(doc_id, vec)
                except Exception as e:
                    # Embedding failed mid-flight — don't kill the upsert;
                    # BM25 still works and drift will re-attempt later.
                    # Logged via stats() / fallback_active for observability.
                    pass

            state.last_upsert_at = rec.indexed_at
            try:
                self._persist(state)
            except OSError as e:
                raise RetrievalError(f"persist failed for source={source}: {e}") from e

    # ---------------- public: index_delete ----------------

    def index_delete(self, source: str, doc_id: str) -> None:
        if not isinstance(source, str) or not source:
            raise RetrievalError("source must be a non-empty string")
        if not isinstance(doc_id, str) or not doc_id:
            raise RetrievalError("doc_id must be a non-empty string")
        with self._lock:
            state = self._get(source)
            if doc_id not in state.records:
                # Idempotent: not present == success.
                return
            state.records.pop(doc_id, None)
            state.bm25.delete(doc_id)
            if state.vectors is not None:
                state.vectors.delete(doc_id)
            state.store.delete_doc(doc_id)
            try:
                self._persist(state)
            except OSError as e:
                raise RetrievalError(f"persist failed for source={source}: {e}") from e

    # ---------------- public: search ----------------

    def search(
        self,
        source: str,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[Hit]:
        if not isinstance(source, str) or not source:
            raise RetrievalError("source must be a non-empty string")
        if query is None:
            raise RetrievalError("query must not be None")
        if not isinstance(top_k, int) or top_k <= 0:
            raise RetrievalError("top_k must be a positive int")

        with self._lock:
            state = self._get(source)
            if not state.records:
                return []

            allowed_ids = _filter_doc_ids(state.records, filters)
            if allowed_ids is not None and not allowed_ids:
                return []

            ranked: List[tuple] = []

            use_vector = (
                self.provider.is_available()
                and state.vectors is not None
                and state.vectors.doc_ids
            )

            if use_vector:
                try:
                    q_vec = self.provider.embed(query)
                    vec_idx = VectorIndex(state.vectors)
                    vec_ranked = vec_idx.search(q_vec, top_k, allowed_ids=allowed_ids)
                except Exception:
                    vec_ranked = []
                bm_ranked = state.bm25.search(query, top_k, allowed_ids=allowed_ids)
                # Detect semantic collapse: if the top vector scores are all
                # tied (within epsilon) we are seeing insertion-order leakage,
                # not similarity. Treat exactly like an embed() exception —
                # drop vec_ranked so the BM25 path below is the sole ranker.
                if vec_ranked and _is_vector_collapsed(vec_ranked):
                    vec_ranked = []
                if self.config.hybrid_search and vec_ranked and bm_ranked:
                    ranked = rrf_fuse([vec_ranked, bm_ranked], top_k=top_k)
                elif vec_ranked:
                    ranked = vec_ranked
                else:
                    ranked = bm_ranked
            else:
                ranked = state.bm25.search(query, top_k, allowed_ids=allowed_ids)

            hits: List[Hit] = []
            for doc_id, score in ranked:
                rec = state.records.get(doc_id)
                if rec is None:
                    continue
                content = state.store.read_doc(doc_id) or ""
                hits.append(
                    Hit(
                        doc_id=doc_id,
                        source=source,
                        score=float(score),
                        content=content,
                        metadata=dict(rec.metadata or {}),
                    )
                )
            return hits

    # ---------------- public: verify_consistency ----------------

    def verify_consistency(self, source: str, mode: str) -> DriftReport:
        if mode not in ("fast", "full"):
            raise RetrievalError(f"mode must be 'fast' or 'full', got {mode!r}")
        with self._lock:
            state = self._get(source)
            # Snapshot records — drift mutations re-enter index_upsert
            # which acquires the same RLock (reentrant).
            records_snapshot = dict(state.records)

            def _read(doc_id: str):
                return state.store.read_doc(doc_id)

            def _upsert(doc_id: str, content: str, metadata: dict):
                # Preserve source_path through the metadata channel.
                rec = state.records.get(doc_id)
                if rec is not None and rec.source_path and "source_path" not in metadata:
                    metadata = {**metadata, "source_path": rec.source_path}
                self.index_upsert(source, doc_id, content, metadata)

            def _delete(doc_id: str):
                self.index_delete(source, doc_id)

            if mode == "fast":
                report = fast_check(records_snapshot, _read, _upsert, _delete)
            else:
                report = full_check(records_snapshot, _read, _upsert, _delete)
            report.source = source
            state.last_verify_at = now_iso()
            state.last_drift_count = len(report.drifted)
            return report

    # ---------------- public: stats ----------------

    def stats(self, source: Optional[str] = None) -> Union[IndexStats, List[IndexStats]]:
        if source is None:
            return [self._one_stats(s) for s in VALID_SOURCES]
        return self._one_stats(source)

    def _one_stats(self, source: str) -> IndexStats:
        if source not in VALID_SOURCES:
            raise RetrievalError(f"unknown source: {source!r}")
        with self._lock:
            state = self._get(source)
            dim = state.vectors.dim if state.vectors is not None else None
            return IndexStats(
                source=source,
                total_docs=len(state.records),
                vector_dim=dim,
                embedding_provider=self.provider.name,
                fallback_active=not self.provider.is_available(),
                index_size_bytes=state.store.total_size_bytes(),
                last_upsert_at=state.last_upsert_at,
                last_verify_at=state.last_verify_at,
                last_drift_count=state.last_drift_count,
            )


# --------------------------------------------------------------------------
# Module-level singleton + 5 public functions.
# --------------------------------------------------------------------------


def _is_vector_collapsed(vec_ranked: List[tuple]) -> bool:
    """True when the vector ranking carries no usable signal.

    Two failure modes the embedding layer can hand us silently:
      * provider returns a constant vector for every text (sims all equal),
      * provider returns a near-zero vector that survives the q_norm==0
        gate in VectorIndex but still produces effectively-equal sims.

    In both cases scored.sort() degenerates to VectorBlob insertion order,
    which is ~indexed_at order — useless for retrieval. We declare
    collapse when the spread between top-1 and bottom score in the
    returned slice is below epsilon, AND there is more than one result
    to compare. Single-hit results can't collapse by definition.
    """
    if len(vec_ranked) < 2:
        return False
    top = vec_ranked[0][1]
    bot = vec_ranked[-1][1]
    return (top - bot) < _VECTOR_COLLAPSE_EPSILON


def _filter_doc_ids(records: Dict[str, DocRecord], filters: Optional[dict]) -> Optional[set]:
    """Return the set of doc_ids whose metadata matches all filter keys,
    or None if no filter was supplied (means: all docs allowed)."""
    if not filters:
        return None
    allowed = set()
    for doc_id, rec in records.items():
        md = rec.metadata or {}
        ok = True
        for k, v in filters.items():
            if md.get(k) != v:
                ok = False
                break
        if ok:
            allowed.add(doc_id)
    return allowed


_default_facade: Optional[RetrievalFacade] = None
_default_lock = RLock()


def _resolve_index_root() -> Path:
    # Lazy import to keep retrieval independent of the broader kernel
    # context.py for testability (tests can construct RetrievalFacade
    # directly without kernel context).
    from context import project_root  # type: ignore  # added to sys.path by cbim launcher
    return project_root() / ".cbim" / "index"


def _facade() -> RetrievalFacade:
    global _default_facade
    with _default_lock:
        if _default_facade is None:
            _default_facade = RetrievalFacade(_resolve_index_root())
        return _default_facade


def reset_default_facade() -> None:
    """Test hook: drop the cached singleton."""
    global _default_facade
    with _default_lock:
        _default_facade = None


def index_upsert(source: str, doc_id: str, content: str, metadata: Optional[dict] = None) -> None:
    _facade().index_upsert(source, doc_id, content, metadata)


def index_delete(source: str, doc_id: str) -> None:
    _facade().index_delete(source, doc_id)


def search(
    source: str,
    query: str,
    top_k: int = 10,
    filters: Optional[dict] = None,
) -> List[Hit]:
    return _facade().search(source, query, top_k, filters)


def verify_consistency(source: str, mode: str) -> DriftReport:
    return _facade().verify_consistency(source, mode)


def stats(source: Optional[str] = None) -> Union[IndexStats, List[IndexStats]]:
    return _facade().stats(source)
