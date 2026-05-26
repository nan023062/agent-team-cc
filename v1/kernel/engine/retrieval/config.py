"""Retrieval configuration loader.

Reads .cbim/index/config.json per contract.md §EmbeddingProvider Configuration.
Missing config -> default to provider="null" (BM25 fallback). Zero-config
install must work.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RetrievalConfig:
    provider: str = "null"
    openai_api_key_env: str = "OPENAI_API_KEY"
    openai_model: str = "text-embedding-3-small"
    local_model_path: str = ""
    hybrid_search: bool = False
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict) -> "RetrievalConfig":
        return cls(
            provider=data.get("provider", "null"),
            openai_api_key_env=data.get("openai_api_key_env", "OPENAI_API_KEY"),
            openai_model=data.get("openai_model", "text-embedding-3-small"),
            local_model_path=data.get("local_model_path", ""),
            hybrid_search=bool(data.get("hybrid_search", False)),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "openai_api_key_env": self.openai_api_key_env,
            "openai_model": self.openai_model,
            "local_model_path": self.local_model_path,
            "hybrid_search": self.hybrid_search,
            "schema_version": self.schema_version,
        }


def load_config(index_root: Path) -> RetrievalConfig:
    """Load .cbim/index/config.json. Missing file -> defaults."""
    path = index_root / "config.json"
    if not path.exists():
        return RetrievalConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Corrupted config: fall back to defaults rather than crash.
        return RetrievalConfig()
    return RetrievalConfig.from_dict(raw)


def save_config(index_root: Path, config: RetrievalConfig) -> None:
    index_root.mkdir(parents=True, exist_ok=True)
    path = index_root / "config.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    import os
    os.replace(tmp, path)
