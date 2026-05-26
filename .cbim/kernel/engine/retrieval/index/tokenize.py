"""Mixed-script tokenizer for BM25.

Decision (zero-dep): we split on the boundaries below and emit:
  - For ASCII alphanumeric runs: the whole run, lowercased (acts like a
    western-style word token).
  - For CJK runs (Han / Hiragana / Katakana): character bigrams plus
    individual characters as fallback. Bigrams give enough locality to
    discriminate phrases without a real segmenter; unigrams keep recall
    when the query is a single character.

This is intentionally minimal — no stopwords, no stemming. The BM25
length normalization handles document-length variation.

Reference: bigram tokenization is a well-known approach for unsegmented
CJK retrieval (see classic IR literature on n-gram indexing); it trades
a larger inverted index for zero dependency on jieba / mecab / kuromoji.
"""
from __future__ import annotations

import re
import unicodedata
from typing import List


# Matches a maximal run of ASCII letters / digits.
_ASCII_WORD = re.compile(r"[A-Za-z0-9]+")


def _is_cjk(ch: str) -> bool:
    """True for Han / Hiragana / Katakana / Hangul characters.

    We use the unicode block name via the high code point ranges — fast,
    no extra table lookups.
    """
    cp = ord(ch)
    return (
        0x3040 <= cp <= 0x30FF   # Hiragana + Katakana
        or 0x3400 <= cp <= 0x9FFF  # CJK Unified Ideographs (incl. ext A)
        or 0xAC00 <= cp <= 0xD7AF  # Hangul Syllables
        or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility Ideographs
        or 0x20000 <= cp <= 0x2FFFF  # CJK Unified Ideographs Ext B+
    )


def tokenize(text: str) -> List[str]:
    """Split `text` into BM25 tokens. Order is preserved for testing,
    but BM25 only needs frequency."""
    if not text:
        return []
    # Normalize unicode (NFKC) so wide-form ASCII collapses to narrow.
    text = unicodedata.normalize("NFKC", text)
    tokens: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if "A" <= ch <= "Z" or "a" <= ch <= "z" or "0" <= ch <= "9":
            m = _ASCII_WORD.match(text, i)
            assert m is not None
            tokens.append(m.group(0).lower())
            i = m.end()
            continue
        if _is_cjk(ch):
            # Find the CJK run.
            j = i
            while j < n and _is_cjk(text[j]):
                j += 1
            run = text[i:j]
            # Emit unigrams + bigrams.
            for c in run:
                tokens.append(c)
            for k in range(len(run) - 1):
                tokens.append(run[k : k + 2])
            i = j
            continue
        # Punctuation / other: skip.
        i += 1
    return tokens
