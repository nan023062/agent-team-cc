"""EmbeddingProvider factory — selects the implementation from config.

Single chokepoint so future providers register here, not in the facade.
"""
from __future__ import annotations

from engine.retrieval.config import RetrievalConfig
from engine.retrieval.embedding.base import EmbeddingProvider
from engine.retrieval.embedding.local import LocalEmbeddingProvider
from engine.retrieval.embedding.null import NullEmbeddingProvider
from engine.retrieval.embedding.openai import OpenAIEmbeddingProvider


def build_provider(config: RetrievalConfig) -> EmbeddingProvider:
    p = (config.provider or "null").strip().lower()
    if p == "openai":
        return OpenAIEmbeddingProvider(
            api_key_env=config.openai_api_key_env,
            model=config.openai_model,
        )
    if p == "local":
        return LocalEmbeddingProvider(model_path=config.local_model_path)
    # Unknown provider name -> defensive fallback to Null (BM25 path).
    return NullEmbeddingProvider()
