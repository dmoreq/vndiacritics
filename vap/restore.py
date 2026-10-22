"""Bigram Viterbi diacritic restoration.

Design notes that must not be "cleaned up":

1. The UNK penalty is applied whenever either the bigram count or the previous
   word's unigram count is zero. It is a strong negative constant. Removing this
   branch costs about 19 accuracy points (measured 91.50 -> 71.57).
2. The unigram prior is added ONLY on the second column (i == 1) and uses the
   PREVIOUS word's count. This mirrors the reference implementation; changing it
   to i == 2, or to the current word, moves accuracy by several points.
3. Case is restored per character positionally against the original input,
   because accent insertion does not change string length for these corpora.
"""

from __future__ import annotations

import math
from typing import Protocol

from vap.index import CandidateIndex

_MIN = float("-inf")


class Counter(Protocol):
    """Anything that can answer `count of key`, returning 0 when absent."""

    def get(self, key: str, default: int = 0) -> int: ...


class Restorer:
    def __init__(
        self,
        unigram: dict[str, int],
        index: CandidateIndex,
        bigram: Counter,
        bigram_size: int | None = None,
        bigram_total: int | None = None,
    ) -> None:
        self._uni = unigram
        self._idx = index
        self._bi = bigram
        self._v1 = len(unigram)
        self._t1 = sum(unigram.values())
        size = bigram_size if bigram_size is not None else getattr(bigram, "size", None)
        total = bigram_total if bigram_total is not None else getattr(bigram, "total", None)
        if size is None:
            size = len(bigram)  # type: ignore[arg-type]
        if total is None:
            total = sum(bigram.values())  # type: ignore[attr-defined]
        self._unk = math.log(1.0 / (2 * (size + total + 1)))

    def _columns(self, tokens: list[str]) -> list[list[str]]:
        cols = []
        for t in tokens:
            forms = self._idx.candidates(t)
            cols.append(forms if forms else [t.lower()])
        return cols

    def _score(self, prev: str, cur: str) -> float:
        n2 = self._bi.get(prev + " " + cur, 0)
        n1 = self._uni.get(prev, 0)
        if n1 > 0 and n2 > 0:
            return math.log((n2 + 1) / (n1 + 1))
        return self._unk

    def restore(self, text: str) -> str:
        if not text.strip():
            return text
        tokens = text.split()
        cols = self._columns(tokens)
        if len(cols) == 1:
            chosen = [max(cols[0], key=lambda w: self._uni.get(w, 0))]
        else:
            chosen = self._viterbi(cols)
        return self._reapply_case(text, " ".join(chosen))

    def _viterbi(self, cols: list[list[str]]) -> list[str]:
        score = [[_MIN] * len(c) for c in cols]
        back = [[0] * len(c) for c in cols]
        for j in range(len(cols[0])):
            score[0][j] = 0.0
        for i in range(1, len(cols)):
            prev_col = cols[i - 1]
            prev_score = score[i - 1]
            for j, cur in enumerate(cols[i]):
                best = _MIN
                arg = 0
                for k, prev in enumerate(prev_col):
                    s = prev_score[k] + self._score(prev, cur)
                    if i == 1:
                        s += math.log((self._uni.get(prev, 0) + 1) / (self._t1 + self._v1))
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
