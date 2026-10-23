"""Measure accuracy/throughput trade for skipping low-count bigram lookups.

Idea: a pair where `cur` has a tiny unigram count almost never has a bigram entry.
Skipping the trie walk there trades a small number of real hits for large savings.
This script applies the skip to the live DP so accuracy is measured, not assumed.
"""

from __future__ import annotations

import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case

IN = ROOT / "vap/data/in_domain.txt"
OUT = ROOT / "bench/data/diacritic_eval_v0.txt"


def gold(p):
    return [nfc(s) for s in split_sentences(p.read_text(encoding="utf-8"))]


def viterbi_with_skip(self, cols, skip_below):
    """Copy of _viterbi with a count threshold before the bigram lookup."""
    neg = float("-inf")
    score_m = [[neg] * len(c) for c in cols]
    back = [[0] * len(c) for c in cols]
    for j in range(len(cols[0])):
        score_m[0][j] = 0.0
    uni_get = self._uni.get
    bi_get = self._bi.get
    unk = self._unk
    for i in range(1, len(cols)):
        prev_col = cols[i - 1]
        prev_score = score_m[i - 1]
        add_prior = i == 1
        for j, cur in enumerate(cols[i]):
            best = neg
            arg = 0
            cur_ok = uni_get(cur, 0) >= skip_below
            for k, prev in enumerate(prev_col):
                n1 = uni_get(prev, 0)
                if cur_ok and n1 > 0:
                    n2 = bi_get(prev + " " + cur, 0)
                    if n2 > 0:
                        s = prev_score[k] + math.log((n2 + 1) / (n1 + 1))
                    else:
                        s = prev_score[k] + unk
                else:
                    s = prev_score[k] + unk
                if add_prior:
                    s += math.log((n1 + 1) / (self._t1 + self._v1))
                if s > best:
                    best = s
                    arg = k
            score_m[i][j] = best
            back[i][j] = arg
    idx = max(range(len(cols[-1])), key=lambda j: score_m[-1][j])
    out = [""] * len(cols)
    out[-1] = cols[-1][idx]
    for i in range(len(cols) - 2, -1, -1):
        idx = back[i + 1][idx]
        out[i] = cols[i][idx]
    return out


def evaluate(model, skip_below, reps=3):
    r = model._restorer
    gi, go = gold(IN), gold(OUT)
    si = [strip_accent_keep_case(s) for s in gi]
    so = [strip_accent_keep_case(s) for s in go]

    original = r._viterbi
    r._viterbi = lambda cols: viterbi_with_skip(r, cols, skip_below)
    rates = []
    try:
        for _ in range(reps):
            t = time.perf_counter()
            for s in si:
                r.restore(s)
            rates.append(len(si) / (time.perf_counter() - t))
        pi = [r.restore(s) for s in si]
        po = [r.restore(s) for s in so]
    finally:
        r._viterbi = original

    return (
        score(gi, pi).accuracy,
        score(go, po).accuracy,
        statistics.median(rates),
    )


def main() -> int:
    model = Model.load()
    print(f"{'skip_below':>10} {'in-acc':>8} {'out-acc':>8} {'sent/s':>8}")
    for thr in (0, 2, 5, 10, 20, 50):
        ai, ao, rate = evaluate(model, thr)
        print(f"{thr:>10} {ai*100:7.2f}% {ao*100:7.2f}% {rate:8.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
