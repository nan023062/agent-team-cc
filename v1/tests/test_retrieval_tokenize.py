"""Tokenizer unit tests — char-bigram + ASCII word, zero-dep."""
from __future__ import annotations

from engine.retrieval.index.tokenize import tokenize


def test_ascii_words_lowercased():
    toks = tokenize("Hello World 123")
    assert toks == ["hello", "world", "123"]


def test_empty_and_whitespace():
    assert tokenize("") == []
    assert tokenize("   \t\n  ") == []


def test_cjk_bigrams_and_unigrams():
    # 中文 -> unigrams (中, 文) + bigram (中文)
    toks = tokenize("中文")
    assert "中" in toks and "文" in toks
    assert "中文" in toks


def test_cjk_run_emits_all_adjacent_bigrams():
    toks = tokenize("自然语言")
    # 4 unigrams + 3 bigrams
    assert toks.count("自") == 1
    assert toks.count("然") == 1
    assert "自然" in toks
    assert "然语" in toks
    assert "语言" in toks


def test_mixed_script():
    toks = tokenize("Python 中文 mixed")
    assert "python" in toks
    assert "中" in toks
    assert "中文" in toks
    assert "mixed" in toks


def test_punctuation_dropped():
    toks = tokenize("a, b; c!?")
    assert toks == ["a", "b", "c"]


def test_nfkc_normalization():
    # full-width digits should normalize to ASCII
    toks = tokenize("１２３")
    assert toks == ["123"]


def test_distinct_words_yield_distinct_tokens():
    # Exclusion test: distinct ASCII words must not flatten to the same token set.
    words = ["fox", "dog", "language", "image", "retrieval"]
    token_sets = {w: set(tokenize(w)) for w in words}
    for w, ts in token_sets.items():
        assert ts, f"empty token set for {w!r}"
    for a in words:
        for b in words:
            if a == b:
                continue
            assert token_sets[a] != token_sets[b], (
                f"{a!r} and {b!r} produced identical token sets: {token_sets[a]}"
            )
            assert not token_sets[a].issubset(token_sets[b]), (
                f"{a!r} tokens are a subset of {b!r} tokens"
            )
            assert not token_sets[b].issubset(token_sets[a]), (
                f"{b!r} tokens are a subset of {a!r} tokens"
            )


def test_distinct_cjk_terms_yield_distinct_bigrams():
    # Exclusion test: distinct CJK 2-char terms must each emit a unique bigram,
    # and NFKC must not fold any pair into the same surface form.
    terms = ["语言", "识别", "检索", "排序"]
    bigrams = {}
    for t in terms:
        toks = tokenize(t)
        assert t in toks, f"expected bigram {t!r} in tokens {toks}"
        bigrams[t] = t
    seen = set()
    for t, bg in bigrams.items():
        assert bg not in seen, f"bigram collision on {bg!r}"
        seen.add(bg)
    # And pairwise full token-set distinctness — no two terms collapse to the same set.
    token_sets = {t: set(tokenize(t)) for t in terms}
    for a in terms:
        for b in terms:
            if a == b:
                continue
            assert token_sets[a] != token_sets[b], (
                f"{a!r} and {b!r} produced identical token sets: {token_sets[a]}"
            )
