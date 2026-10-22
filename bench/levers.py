"""Size the two remaining levers, measuring accuracy and speed together.

1. Beam width sweep (already partly known; re-measured post-remediation).
2. Bigram pair memoisation: the same (prev, cur, i==1) triple recurs constantly
   across a corpus, so a dict cache can absorb repeat trie walks.
"""

from __future__ import annotations

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


def gold(path):
    raw = path.read_text(encoding="utf-8")
    return [nfc(s) for s in split_sentences(raw)]


def run(model, sents, max_cand=None):
    r = model._restorer
    old = r._max_candidates
    if max_cand is not None:
        r._max_candidates = max_cand
    t = time.perf_counter()
    pred = [r.restore(s) for s in sents]
    dt = time.perf_counter() - t
    r._max_candidates = old
    return pred, len(sents) / dt, dt


def main() -> int:
    model = Model.load()
    gi, go = gold(IN), gold(OUT)
    si = [strip_accent_keep_case(s) for s in gi]
    so = [strip_accent_keep_case(s) for s in go]

    print("=== beam sweep (post-remediation) ===")
    print(f"{'K':>6} {'in-acc':>8} {'out-acc':>8} {'sent/s':>8}")
    for k in (None, 12, 8, 6, 5):
        pi, rate, _ = run(model, si, k)
        po, _, _ = run(model, so, k)
        ai = score(gi, pi).accuracy * 100
        ao = score(go, po).accuracy * 100
        print(f"{k!s:>6} {ai:7.2f}% {ao:7.2f}% {rate:8.0f}")

    print("\n=== pair memoisation sizing ===")
    r = model._restorer
    seen: set[tuple[str, str]] = set()
    total = 0
    for s in si:
        cols, _ = r._columns(s.split())
        for i in range(1, len(cols)):
            for cur in cols[i]:
                for prev in cols[i - 1]:
                    total += 1
                    seen.add((prev, cur))
    print(f"  pair evaluations     : {total}")
    print(f"  distinct pairs       : {len(seen)} ({len(seen)/total*100:.1f}%)")
    print(f"  repeat rate          : {(total-len(seen))/total*100:.1f}%")
    print(f"  => a cache would replace {total-len(seen)} of {total} trie walks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
