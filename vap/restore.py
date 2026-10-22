"""Bigram Viterbi diacritic restoration.

Design notes that must not be "cleaned up":

1. The UNK penalty is applied whenever either the bigram count or the previous
   word's unigram count is zero. It is a strong negative constant. Removing this
   branch costs about 19 accuracy points (measured).
2. The unigram prior is added ONLY on the second column (i == 1) and uses the
   PREVIOUS word's count. This mirrors the reference implementation; changing it
   to i == 2, or to the current word, moves accuracy by several points.
3. Punctuation is stripped from token edges before lookup and re-attached after.
   Corpus keys are bare syllables, so looking up "đồng." silently fails and the
   token passes through unaccented. This is the single biggest correctness trap.
4. Case is restored per character positionally against the original input, because
   accent insertion does not change string length for these corpora.
"""

from __future__ import annotations

import math
import re
from typing import Protocol

from vap.index import CandidateIndex

_MIN = float("-inf")


class Counter(Protocol):
    """Anything that can answer `count of key`, returning `default` when absent."""

    def get(self, key: str, default: int = 0) -> int: ...


class Restorer:
    def __init__(
        self,
        unigram: dict[str, int],
        index: CandidateIndex,
        bigram: Counter,
        bigram_size: int | None = None,
        bigram_total: int | None = None,
        max_candidates: int | None = 8,
    ) -> None:
        self._uni = unigram
        self._idx = index
        self._bi = bigram
        # Beam width. Measured on the reference corpus: K=8 costs 0.30 accuracy
        # points in-domain and gains 2.4x throughput; K=5 loses 1.6 points.
        self._max_candidates = max_candidates
        self._v1 = len(unigram)
        self._t1 = sum(unigram.values())
        size = bigram_size if bigram_size is not None else getattr(bigram, "size", None)
        total = bigram_total if bigram_total is not None else getattr(bigram, "total", None)
        if size is None:
            size = len(bigram)  # type: ignore[arg-type]
        if total is None:
            total = sum(bigram.values())  # type: ignore[attr-defined]
        self._unk = math.log(1.0 / (2 * (size + total + 1)))

    @staticmethod
    def _split_punct(token: str) -> tuple[str, str, str]:
        """Split a token into (leading punctuation, core, trailing punctuation)."""
        i, j = 0, len(token)
        while i < j and not token[i].isalnum():
            i += 1
        while j > i and not token[j - 1].isalnum():
            j -= 1
        return token[:i], token[i:j], token[j:]

    def _columns(self, tokens: list[str]) -> tuple[list[list[str]], list[tuple[str, str]]]:
        cols: list[list[str]] = []
        affixes: list[tuple[str, str]] = []
        k = self._max_candidates
        uni_get = self._uni.get
        for t in tokens:
            lead, core, trail = self._split_punct(t)
            if core:
                forms = self._idx.candidates(core.lower())
                if not forms:
                    forms = [core.lower()]
                elif k is not None and len(forms) > k:
                    # Keep the highest-unigram forms: the DP can almost never
                    # recover a form whose unigram count is far below the rest.
                    forms = sorted(forms, key=lambda w: -uni_get(w, 0))[:k]
            else:
                # Punctuation-only token: _split_punct returned (t, "", ""), so an
                # empty core plus the whole token as leading affix rebuilds it exactly
                # once. Using [t] here duplicated the token.
                forms = [""]
            cols.append(forms)
            affixes.append((lead, trail))
        return cols, affixes

    def _score(self, prev: str, cur: str) -> float:
        n2 = self._bi.get(prev + " " + cur, 0)
        n1 = self._uni.get(prev, 0)
        if n1 > 0 and n2 > 0:
            return math.log((n2 + 1) / (n1 + 1))
        return self._unk

    def restore(self, text: str) -> str:
        """Restore diacritics without disturbing the input's whitespace layout.

        Whitespace between tokens is copied verbatim from the source rather than
        rejoined with single spaces, and case is reapplied per token. Doing it on the
        whole joined string previously shifted every character after the first extra
        space, which corrupted case in the rest of the sentence.
        """
        if not text.strip():
            return text
        matches = list(re.finditer(r"\S+", text))
        cols, affixes = self._columns([m.group() for m in matches])
        if len(cols) == 1:
            chosen = [max(cols[0], key=lambda w: self._uni.get(w, 0))]
        else:
            chosen = self._viterbi(cols)
        out: list[str] = []
        end = 0
        for m, word, (lead, trail) in zip(matches, chosen, affixes):
            out.append(text[end : m.start()])
            out.append(self._reapply_case(m.group(), lead + word + trail))
            end = m.end()
        out.append(text[end:])
        return "".join(out)

    def _viterbi(self, cols: list[list[str]]) -> list[str]:
        score = [[_MIN] * len(c) for c in cols]
        back = [[0] * len(c) for c in cols]
        for j in range(len(cols[0])):
            score[0][j] = 0.0
        for i in range(1, len(cols)):
            prev_col = cols[i - 1]
            prev_score = score[i - 1]
            add_prior = i == 1
            uni_get = self._uni.get
            bi_get = self._bi.get
            unk = self._unk
            for j, cur in enumerate(cols[i]):
                best = _MIN
                arg = 0
                for k, prev in enumerate(prev_col):
                    n2 = bi_get(prev + " " + cur, 0)
                    n1 = uni_get(prev, 0)
                    if n1 > 0 and n2 > 0:
                        s = prev_score[k] + math.log((n2 + 1) / (n1 + 1))
                    else:
                        s = prev_score[k] + unk
                    if add_prior:
                        s += math.log((n1 + 1) / (self._t1 + self._v1))
                    if s > best:
                        best = s
                        arg = k
                score[i][j] = best
                back[i][j] = arg
        idx = max(range(len(cols[-1])), key=lambda j: score[-1][j])
        out: list[str] = [""] * len(cols)
        out[-1] = cols[-1][idx]
        for i in range(len(cols) - 2, -1, -1):
            idx = back[i + 1][idx]
            out[i] = cols[i][idx]
        return out

    @staticmethod
    def _reapply_case(original: str, restored: str) -> str:
        n = min(len(original), len(restored))
        chars = [
            restored[i].upper() if original[i].isupper() else restored[i] for i in range(n)
        ]
        return "".join(chars) + restored[n:]
