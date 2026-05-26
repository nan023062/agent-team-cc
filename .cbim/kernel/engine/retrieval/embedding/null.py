"""NullEmbeddingProvider — always unavailable.

The default for zero-config installs. is_available() returns False which
makes the facade route everything to BM25.
"""
from __future__ import annotations

from typing import List

from engine.retrieval.embedding.base import EmbeddingProvider


class NullEmbeddingProvider(EmbeddingProvider):
    name = "null"

    def is_available(self) -> bool:
        return False

    def dimension(self) -> int:
        return 0

    def embed(self, text: str) -> List[float]:
        raise NotImplementedError("NullEmbeddingProvider has no embeddings; check is_available() first")
