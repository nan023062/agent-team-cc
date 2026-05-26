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


def test_different_queries_yield_different_rankings():
    """Regression: different queries must produce different rankings.

    Guards against a class of bug where search() returns the same top-k
    regardless of query (e.g. corpus-stale stats, query-token leakage,
    accidental constant scoring). Builds a small mixed-script corpus and
    asserts:
      (a) at least 3 of the 6 query pairs have distinct top-1 doc_ids;
      (b) each query's top-1 doc actually contains the keyword;
      (c) no two distinct queries share the exact same
          (doc_id-ordering, score-sequence).
    """
    idx = BM25Index()
    docs = {
        "d_fox": "the quick brown fox jumps over the lazy dog",
        "d_rare": "a rare albino tiger was spotted in the forest",
        "d_lang": "自然语言处理是人工智能的核心方向",
        "d_image": "image recognition uses convolutional neural networks",
        "d_weather": "today the weather is sunny and mild across the region",
        "d_vision": "图像识别 与 计算机视觉 紧密 相关",
    }
    for doc_id, text in docs.items():
        idx.upsert(doc_id, text)

    queries = {
        "fox": "d_fox",
        "rare": "d_rare",
        "语言": "d_lang",
        "image": "d_image",
    }
    results = {q: idx.search(q, top_k=5) for q in queries}

    # Every query must return at least one hit.
    for q, res in results.items():
        assert res, f"query {q!r} returned no hits"

    # (b) Each query's top-1 hit must be the doc whose content carries the keyword.
    for q, expected_top in queries.items():
        top_doc = results[q][0][0]
        assert top_doc == expected_top, (
            f"query {q!r} top-1 was {top_doc!r}, expected {expected_top!r}; "
            f"full ranking: {results[q]}"
        )
        # And the keyword must literally appear in that doc (sanity on the corpus itself).
        assert q in docs[expected_top]

    # (a) At least 3 query pairs must have distinct top-1 doc_ids.
    qlist = list(queries.keys())
    distinct_top1_pairs = 0
    for i in range(len(qlist)):
        for j in range(i + 1, len(qlist)):
            if results[qlist[i]][0][0] != results[qlist[j]][0][0]:
                distinct_top1_pairs += 1
    assert distinct_top1_pairs >= 3, (
        f"only {distinct_top1_pairs} query pairs have distinct top-1; "
        f"top-1 by query: { {q: r[0][0] for q, r in results.items()} }"
    )

    # (c) No two distinct queries share the same (doc_id order, score sequence).
    signatures = {q: (tuple(d for d, _ in r), tuple(s for _, s in r)) for q, r in results.items()}
    for i in range(len(qlist)):
        for j in range(i + 1, len(qlist)):
            qa, qb = qlist[i], qlist[j]
            assert signatures[qa] != signatures[qb], (
                f"queries {qa!r} and {qb!r} produced identical ranking+scores: "
                f"{signatures[qa]}"
            )


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
