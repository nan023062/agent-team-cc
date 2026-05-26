"""IndexStore + VectorBlob unit tests."""
from __future__ import annotations

import pytest

from engine.retrieval.store import (
    DocRecord,
    IndexStore,
    StoreError,
    VectorBlob,
    _safe_doc_filename,
    content_sha256,
)


def test_safe_doc_filename_percent_encodes():
    assert _safe_doc_filename("a/b c") == "a%2Fb%20c"
    assert _safe_doc_filename("plain-name.md") == "plain-name.md"
    # Empty and dot edge cases get the underscore prefix to stay non-trivial.
    assert _safe_doc_filename("") == "_"
    assert _safe_doc_filename(".").startswith("_")
    assert _safe_doc_filename("..").startswith("_")


def test_unknown_source_rejected(tmp_path):
    with pytest.raises(StoreError):
        IndexStore(tmp_path, "bogus_source")


def test_meta_roundtrip(tmp_path):
    s = IndexStore(tmp_path, "dna")
    assert s.load_meta() == {}
    rec = DocRecord(
        doc_id="src/foo",
        mtime=12345.0,
        size=42,
        sha256="abc",
        indexed_at="2026-05-26T00:00:00Z",
        metadata={"tag": "v1"},
        source_path="/abs/src/foo",
    )
    s.save_meta({rec.doc_id: rec})
    loaded = s.load_meta()
    assert "src/foo" in loaded
    assert loaded["src/foo"].metadata == {"tag": "v1"}
    assert loaded["src/foo"].source_path == "/abs/src/foo"


def test_doc_read_write_delete(tmp_path):
    s = IndexStore(tmp_path, "memory_medium")
    s.write_doc("a/b", "hello 你好")
    assert s.read_doc("a/b") == "hello 你好"
    s.delete_doc("a/b")
    assert s.read_doc("a/b") is None


def test_vector_blob_roundtrip(tmp_path):
    blob = VectorBlob(dim=3)
    blob.upsert("d1", [1.0, 0.0, 0.0])
    blob.upsert("d2", [0.0, 1.0, 0.0])
    blob.upsert("d1", [0.5, 0.5, 0.0])  # update
    path = tmp_path / "vectors.bin"
    blob.save(path)
    restored = VectorBlob.load(path)
    assert restored.dim == 3
    assert restored.doc_ids == ["d1", "d2"]
    assert restored.get("d1") == [0.5, 0.5, 0.0]


def test_vector_dim_mismatch_raises():
    blob = VectorBlob(dim=3)
    with pytest.raises(StoreError):
        blob.upsert("d1", [1.0, 2.0])


def test_content_sha256_deterministic():
    a = content_sha256("hello")
    b = content_sha256("hello")
    assert a == b
    assert content_sha256("HELLO") != a
