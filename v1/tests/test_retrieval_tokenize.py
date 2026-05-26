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
