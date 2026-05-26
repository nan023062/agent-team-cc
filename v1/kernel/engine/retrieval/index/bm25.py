"""BM25 keyword index — pure stdlib.

Implements Okapi BM25 with the canonical parameters k1=1.5, b=0.75
(internal defaults, not exposed per arch-decision-retrieval-internal-defaults).

Score(D, Q) = sum over q in Q of:
    IDF(q) * f(q, D) * (k1 + 1) / (f(q, D) + k1 * (1 - b + b * |D| / avgdl))

IDF(q) = ln((N - df(q) + 0.5) / (df(q) + 0.5) + 1)   # +1 keeps it non-negative

State is JSON-serializable for persistence in bm25.json:
    {
      "schema_version": 1,
      "doc_lengths": {doc_id: int},
      "inverted": {term: {doc_id: int}},   # term frequency per doc
    }
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

from engine.retrieval.index.tokenize import tokenize


K1 = 1.5
B = 0.75


class BM25Index:
    def __init__(self) -> None:
        # doc_id -> doc length (# tokens)
        self.doc_lengths: Dict[str, int] = {}
        # term -> {doc_id: tf}
        self.inverted: Dict[str, Dict[str, int]] = {}

    # ---------------- mutation ----------------

    def upsert(self, doc_id: str, content: str) -> None:
        # If doc already exists, remove its postings first.
        if doc_id in self.doc_lengths:
            self._remove_postings(doc_id)
        tokens = tokenize(content)
        self.doc_lengths[doc_id] = len(tokens)
        if not tokens:
            return
        counts = Counter(tokens)
        for term, tf in counts.items():
            postings = self.inverted.setdefault(term, {})
            postings[doc_id] = tf

    def delete(self, doc_id: str) -> None:
        if doc_id not in self.doc_lengths:
            return
        self._remove_postings(doc_id)
        del self.doc_lengths[doc_id]

    def _remove_postings(self, doc_id: str) -> None:
        empty_terms: List[str] = []
        for term, postings in self.inverted.items():
            if doc_id in postings:
                del postings[doc_id]
                if not postings:
                    empty_terms.append(term)
        for term in empty_terms:
            del self.inverted[term]

    # ---------------- query ----------------

    def search(
        self,
        query: str,
        top_k: int,
        allowed_ids: Optional[set] = None,
    ) -> List[Tuple[str, float]]:
        """Return [(doc_id, score)] sorted desc, top_k, with score > 0."""
        if not self.doc_lengths:
            return []
        terms = tokenize(query)
        if not terms:
            return []
        N = len(self.doc_lengths)
        avgdl = sum(self.doc_lengths.values()) / max(N, 1)
        scores: Dict[str, float] = {}
        # Use term frequencies in query to avoid double-counting at idf level
        # but since BM25 just sums per-occurrence we iterate raw terms.
        query_terms = list(set(terms))  # dedupe — repeated query terms don't add info under classic BM25
        for term in query_terms:
            postings = self.inverted.get(term)
            if not postings:
                continue
            df = len(postings)
            idf = math.log(((N - df + 0.5) / (df + 0.5)) + 1.0)
            for doc_id, tf in postings.items():
                if allowed_ids is not None and doc_id not in allowed_ids:
                    continue
                dl = self.doc_lengths[doc_id]
                denom = tf + K1 * (1.0 - B + B * dl / avgdl) if avgdl > 0 else tf + K1
                score = idf * tf * (K1 + 1.0) / denom
                scores[doc_id] = scores.get(doc_id, 0.0) + score
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]

    # ---------------- persistence ----------------

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "doc_lengths": dict(self.doc_lengths),
            "inverted": {t: dict(postings) for t, postings in self.inverted.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BM25Index":
        obj = cls()
        obj.doc_lengths = {str(k): int(v) for k, v in (data.get("doc_lengths") or {}).items()}
        inv_raw = data.get("inverted") or {}
        obj.inverted = {
            str(term): {str(d): int(tf) for d, tf in postings.items()}
            for term, postings in inv_raw.items()
        }
        return obj
