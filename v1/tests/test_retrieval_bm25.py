"""BM25Index unit tests — pure in-memory."""
from __future__ import annotations

from engine.retrieval.index.bm25 import BM25Index


def test_empty_search_returns_empty():
    idx = BM25Index()
    assert idx.search("anything", top_k=5) == []


def test_single_doc_match():
    idx = BM25Index()
    idx.upsert("d1", "the quick brown fox")
    res = idx.search("fox", top_k=5)
    assert len(res) == 1
    assert res[0][0] == "d1"
    assert res[0][1] > 0


def test_term_frequency_ordering():
    idx = BM25Index()
    idx.upsert("d1", "cat dog cat cat")
    idx.upsert("d2", "cat dog")
    res = idx.search("cat", top_k=5)
    assert [r[0] for r in res] == ["d1", "d2"]


def test_idf_rarer_term_wins():
    idx = BM25Index()
    # 'common' appears in all docs; 'rare' only in d3.
    for i in range(5):
        idx.upsert(f"d{i}", "common common common")
    idx.upsert("d_rare", "common rare")
    res = idx.search("rare common", top_k=10)
    assert res[0][0] == "d_rare"


def test_upsert_replaces_postings():
    idx = BM25Index()
    idx.upsert("d1", "alpha beta")
    idx.upsert("d1", "gamma delta")  # replace
    res_alpha = idx.search("alpha", top_k=5)
    res_gamma = idx.search("gamma", top_k=5)
    assert res_alpha == []
    assert res_gamma and res_gamma[0][0] == "d1"


def test_delete_removes_doc():
    idx = BM25Index()
    idx.upsert("d1", "hello world")
    idx.upsert("d2", "hello there")
    idx.delete("d1")
    res = idx.search("hello", top_k=5)
    assert [r[0] for r in res] == ["d2"]


def test_allowed_ids_filter():
    idx = BM25Index()
    idx.upsert("d1", "term term")
    idx.upsert("d2", "term")
    res = idx.search("term", top_k=5, allowed_ids={"d2"})
    assert [r[0] for r in res] == ["d2"]


def test_chinese_query_matches_bigrams():
    idx = BM25Index()
    idx.upsert("d1", "自然语言处理")
    idx.upsert("d2", "图像识别")
    res = idx.search("语言", top_k=5)
    assert [r[0] for r in res] == ["d1"]


def test_roundtrip_serialization():
    idx = BM25Index()
    idx.upsert("d1", "hello world")
    idx.upsert("d2", "中文 测试")
    blob = idx.to_dict()
    restored = BM25Index.from_dict(blob)
    res = restored.search("世界", top_k=5)  # no hit, but no crash
    assert isinstance(res, list)
    res2 = restored.search("hello", top_k=5)
    assert [r[0] for r in res2] == ["d1"]
