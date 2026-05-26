"""LocalEmbeddingProvider — stub.

Phase 1 leaves this as an unavailable stub for a future local
(sentence-transformers / llama.cpp / ONNX) backend. Same wiring pattern
as OpenAIEmbeddingProvider.
"""
from __future__ import annotations

from typing import List

from engine.retrieval.embedding.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    name = "local"

    def __init__(self, model_path: str = "") -> None:
        self.model_path = model_path

    def is_available(self) -> bool:
        return False  # never available in Phase 1

    def dimension(self) -> int:
        return 0

    def embed(self, text: str) -> List[float]:
        raise NotImplementedError(
            "LocalEmbeddingProvider is a stub in Phase 1; not yet wired to a model runtime"
        )
