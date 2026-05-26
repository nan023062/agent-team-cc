"""Config + provider factory tests."""
from __future__ import annotations

from engine.retrieval.config import RetrievalConfig, load_config, save_config
from engine.retrieval.embedding.factory import build_provider
from engine.retrieval.embedding.null import NullEmbeddingProvider
from engine.retrieval.embedding.openai import OpenAIEmbeddingProvider


def test_default_config_is_null_provider():
    cfg = RetrievalConfig()
    assert cfg.provider == "null"
    assert cfg.hybrid_search is False
    assert cfg.schema_version == 1


def test_load_missing_returns_defaults(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.provider == "null"


def test_save_and_load_roundtrip(tmp_path):
    cfg = RetrievalConfig(provider="openai", hybrid_search=True)
    save_config(tmp_path, cfg)
    loaded = load_config(tmp_path)
    assert loaded.provider == "openai"
    assert loaded.hybrid_search is True


def test_factory_null_provider():
    p = build_provider(RetrievalConfig(provider="null"))
    assert isinstance(p, NullEmbeddingProvider)
    assert p.is_available() is False


def test_factory_openai_provider_is_stub_unavailable():
    p = build_provider(RetrievalConfig(provider="openai"))
    assert isinstance(p, OpenAIEmbeddingProvider)
    # Stub: always unavailable in Phase 1.
    assert p.is_available() is False


def test_factory_unknown_falls_back_to_null():
    p = build_provider(RetrievalConfig(provider="garbage"))
    assert isinstance(p, NullEmbeddingProvider)


def test_corrupted_config_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.json").write_text("not json!!!", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.provider == "null"
