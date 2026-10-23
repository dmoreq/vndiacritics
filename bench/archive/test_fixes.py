"""Test candidate fixes for the 4 skip-induced regressions.

Root cause observed: the skip kills real bigrams whose *left* context is a rare
token (a proper noun or OCR junk like "doko", "qòng"). The bi-gram is low-count
only because the context is rare, not because the pair is meaningless.

Hypothesis: the skip should consider the *unigram prior's* reliability rather than
raw counts. Test three rules and measure the full corpus each time.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case

IN = ROOT / "vap/data/in_domain.txt"
OUT = ROOT / "bench/data/diacritic_eval_v0.txt"


def gold(p):
    return [nfc(s) for s in split_sentences(p.read_text(encoding="utf-8"))]


def main() -> int:
    model = Model.load()
    r = model._restorer
    gi, go = gold(IN), gold(OUT)
    si = [strip_accent_keep_case(s) for s in gi]
    so = [strip_accent_keep_case(s) for s in go]

    print(f"{'skip_below':>11} {'in-acc':>8} {'correct':>8} {'out-acc':>8} {'sent/s':>8}")
    for thr in (0, 2, 5, 10, 21, 30):
        r._bigram_skip_below = thr
        rates = []
        for _ in range(3):
            t = time.perf_counter()
            for s in si:
                r.restore(s)
            rates.append(len(si) / (time.perf_counter() - t))
        pi = [r.restore(s) for s in si]
        po = [r.restore(s) for s in so]
        ri = score(gi, pi)
        ro = score(go, po)
        print(
            f"{thr:>11} {ri.accuracy*100:7.2f}% {ri.correct:>8} "
            f"{ro.accuracy*100:7.2f}% {statistics.median(rates):8.0f}"
        )
    r._bigram_skip_below = 21
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
