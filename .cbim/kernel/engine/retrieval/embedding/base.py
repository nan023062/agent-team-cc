"""EmbeddingProvider abstract interface.

`is_available()` is the only gating call — facade asks before every
embed-requiring operation and falls back to BM25 when False. This keeps
the "zero-external-deps must work" invariant.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True iff embed/embed_batch can succeed right now."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the fixed vector dimension produced by this provider."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Single-text embed. May raise if is_available() is False."""

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Default impl iterates embed(). Real providers override for batching.

        Per the contract: embed_batch is a performance contract only, semantically
        equivalent to embed() called per-item.
        """
        return [self.embed(t) for t in texts]
