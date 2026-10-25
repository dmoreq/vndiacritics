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

from vndiacritics.index import CandidateIndex

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
        bigram_skip_below: int | None = None,
        bigram_conf_k: int | None = None,
    ) -> None:
        self._uni = unigram
        self._idx = index
        self._bi = bigram
        # Beam width. Measured on the reference corpus: K=8 costs 0.30 accuracy
        # points in-domain and gains 2.4x throughput; K=5 loses 1.6 points.
        if max_candidates is not None and max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        self._max_candidates = max_candidates
        # Skip the bigram lookup when the right-hand candidate's unigram count is
        # below this. A skipped pair scores UNK, which is exactly what a genuine
        # miss scores, so the only possible harm is losing a real hit that would
        # have flipped the argmax. Measured on the reference corpus: 33% of trie
        # walks avoided, 1 flipped column in 8,993 (0.011%), 0.01 accuracy points.
        #
        # Default scales with table size instead of being an absolute count. An
        # absolute default of 20 silently broke small vocabularies: with a toy
        # table where a real word had count 10, it was skipped and the wrong form
        # won. 1e-4 * total puts the cut far below any word a real corpus values.
        # 0 disables the skip entirely.
        self._v1 = len(unigram)
        self._t1 = sum(unigram.values())
        if bigram_skip_below is None:
            # Scale with vocabulary size, not total token count: a count of 20 is
            # negligible in a 216k-word corpus but may be a common word in a toy
            # table. 1e-4 * |V| gives 21 here and 0 for small tables.
            bigram_skip_below = int(self._v1 * 1e-4)
        self._bigram_skip_below = bigram_skip_below
        size = bigram_size if bigram_size is not None else getattr(bigram, "size", None)
        total = bigram_total if bigram_total is not None else getattr(bigram, "total", None)
        if size is None:
            size = len(bigram)  # type: ignore[arg-type]
        if total is None:
            total = sum(bigram.values())  # type: ignore[attr-defined]
        self._unk = math.log(1.0 / (2 * (size + total + 1)))
        # Jelinek-Mercer confidence for the bigram score. The raw ratio
        # log((n2+1)/(n1+1)) lets a pair observed twice over a tiny denominator
        # (2/53) outrank a massive one (71,291/2.9M): the ratio carries no sense
        # of how much the denominator can be trusted. bigram_conf_k blends the
        # bigram ratio toward the current word's unigram probability with
        # lambda = n1/(n1+K), so evidence from a thin context shrinks toward the
        # unigram prior. Measured sweep on the reference corpus
        # (bench/ab_confidence.py): K=1000 is best on BOTH golds (in-domain
        # 96.05% vs 96.01% legacy, out-domain 95.58% vs 95.24%) and fixes the
        # number-context bug; K=10000 regresses in-domain.
        #
        # Default scales with corpus mass, same lesson as bigram_skip_below: an
        # absolute K=1000 is 2.5e-6 of the reference corpus (400.5M tokens) but
        # 41% of a toy table, where it drowns real bigram evidence. Auto mode
        # keeps the measured K on the reference corpus and ~0 (legacy scoring)
        # on small tables. Pass 0 to disable, or an explicit int to force one.
        # Re-measure K after any corpus change (see WS2 in
        # docs/reports/2026-10-25-number-context-fix.md).
        if bigram_conf_k is None:
            bigram_conf_k = int(self._t1 * 1000 / 400_508_022)
        self._conf_k = bigram_conf_k
        self._uni_denom = self._t1 + self._v1

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

    def _transition_score(self, n1: int, n2: int, kp_uni: float) -> float:
        """Score one (prev, cur) pair from bigram evidence. Load-bearing arithmetic.

        conf_k > 0: Jelinek-Mercer pseudo-count form p = (n2 + K*p_uni)/(n1 + K).
        conf_k = 0: the reference formula log((n2+1)/(n1+1)), unchanged. Zero
        bigram evidence scores UNK either way. See the __init__ note.
        """
        if n1 > 0 and n2 > 0:
            if self._conf_k > 0:
                return math.log((n2 + kp_uni) / (n1 + self._conf_k))
            return math.log((n2 + 1) / (n1 + 1))
        return self._unk

    def _best_transition(
        self,
        prev_col: list[str],
        prev_score: list[float],
        cur: str,
        add_prior: bool,
    ) -> tuple[float, int]:
        """Score `cur` against every predecessor; return (best score, argmax index).

        Extracted from `_viterbi` only to bound cognitive complexity. The scoring
        arithmetic (skip rule, UNK fallback, prior on the second column) is the
        load-bearing logic documented in the module docstring -- keep it identical.
        """
        uni_get = self._uni.get
        bi_get = self._bi.get
        skip_below = self._bigram_skip_below
        conf_k = self._conf_k
        uni_denom = self._uni_denom
        # K * p_uni(cur) is a per-COLUMN constant: hoisted here it turns the
        # Jelinek-Mercer blend into one add + one div + one log per pair --
        # the same op count as the legacy formula, so the fix costs no
        # throughput. p = (n2 + K*p_uni) / (n1 + K) == lam*(n2/n1) + (1-lam)*p_uni.
        kp_uni = conf_k * (uni_get(cur, 0) + 1) / uni_denom if conf_k > 0 else 0.0
        best = _MIN
        arg = 0
        cur_ok = skip_below <= 0 or uni_get(cur, 0) >= skip_below
        for k, prev in enumerate(prev_col):
            n1 = uni_get(prev, 0)
            if cur_ok and n1 >= skip_below:
                n2 = bi_get(prev + " " + cur, 0)
            else:
                n2 = 0
            s = prev_score[k] + self._transition_score(n1, n2, kp_uni)
            if add_prior:
                s += math.log((n1 + 1) / uni_denom)
            if s > best:
                best = s
                arg = k
        return best, arg

    def _viterbi(self, cols: list[list[str]]) -> list[str]:
        score = [[_MIN] * len(c) for c in cols]
        back = [[0] * len(c) for c in cols]
        for j in range(len(cols[0])):
            score[0][j] = 0.0
        for i in range(1, len(cols)):
            add_prior = i == 1
            for j, cur in enumerate(cols[i]):
                score[i][j], back[i][j] = self._best_transition(
                    cols[i - 1], score[i - 1], cur, add_prior
                )
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
        chars = [restored[i].upper() if original[i].isupper() else restored[i] for i in range(n)]
        return "".join(chars) + restored[n:]
