"""OpenAIEmbeddingProvider — stub.

Phase 1 leaves this as an unavailable stub. The hook is here so a future
phase can plug in the SDK without touching the facade. is_available()
reports False unconditionally for now so the facade falls back to BM25.

To enable in a future phase:
  - Add `openai` to install_requires (decision still pending).
  - Replace _NOT_WIRED with a real client construction guarded by
    env-var presence + a lightweight ping.
  - Implement embed/embed_batch using client.embeddings.create.
"""
from __future__ import annotations

import os
from typing import List

from engine.retrieval.embedding.base import EmbeddingProvider


_NOT_WIRED = True


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(
        self,
        api_key_env: str = "OPENAI_API_KEY",
        model: str = "text-embedding-3-small",
    ) -> None:
        self.api_key_env = api_key_env
        self.model = model

    def is_available(self) -> bool:
        if _NOT_WIRED:
            return False
        return bool(os.environ.get(self.api_key_env))

    def dimension(self) -> int:
        # text-embedding-3-small native dim. Kept here for future phases.
        return 1536

    def embed(self, text: str) -> List[float]:
        raise NotImplementedError(
            "OpenAIEmbeddingProvider is a stub in Phase 1; not yet wired to the SDK"
        )
