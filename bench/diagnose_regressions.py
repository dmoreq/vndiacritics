"""Root-cause the 4 token regressions caused by the rare-pair skip.

For each failing token, reconstruct the exact column, the candidate set, the
bigram counts that exist, and the score of each path with and without the skip.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def main() -> int:
    model = Model.load()
    r = model._restorer
    uni, bi = r._uni, r._bi
    thr = r._bigram_skip_below

    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    gold_sents = [nfc(s) for s in split_sentences(raw)]

    targets = {"usd", "bệnh", "lượt", "góp"}

    for gs in gold_sents:
        gtoks = gs.split()
        if not any(t in targets for t in gtoks):
            continue
        stripped = strip_accent_keep_case(gs)
        ptoks = stripped.split()
        with_skip = r.restore(stripped).split()
        saved = r._bigram_skip_below
        r._bigram_skip_below = 0
        no_skip = r.restore(stripped).split()
        r._bigram_skip_below = saved

        for i, g in enumerate(gtoks):
            if g not in targets:
                continue
            if g == with_skip[i]:
                continue
            print("=" * 74)
            print(f"GOLD TOKEN : {g!r}   (unigram count {uni.get(g, 0)})")
            print(f"no-skip    : {no_skip[i]!r}")
            print(f"with-skip  : {with_skip[i]!r}")
            lo, hi = max(0, i - 3), min(len(gtoks), i + 4)
            print(f"\ncontext (gold)   : {' '.join(gtoks[lo:hi])}")
            print(f"context (predict): {' '.join(with_skip[lo:hi])}")

            cols, _ = r._columns(ptoks)
            here = cols[i]
            print(f"\ncolumn {i} candidates ({len(here)}): {here}")
            print(f"  counts: " + ", ".join(f"{c}={uni.get(c, 0)}" for c in here))
            print(f"  threshold {thr}: " + ", ".join(
                f"{c}={'LOOKUP' if uni.get(c, 0) >= thr else 'SKIPPED'}" for c in here
            ))

            print("\n  incoming bigrams (prev -> this column):")
            if i > 0:
                for prev in cols[i - 1]:
                    hits = []
                    for cur in here:
                        n2 = bi.get(prev + " " + cur, 0)
                        if n2:
                            hits.append(f"{cur}={n2}")
                    n1 = uni.get(prev, 0)
                    flag = "prev SKIPPED" if n1 < thr else ("prev ok" if n1 else "prev OOV")
                    print(f"    {prev:<12} (uni={n1:<9} {flag}) hits: {', '.join(hits) or 'none'}")
            else:
                print("    (first column, no incoming)")

            print("\n  outgoing bigrams (this column -> next):")
            if i + 1 < len(cols):
                for cur in here:
                    hits = []
                    for nxt in cols[i + 1]:
                        n2 = bi.get(cur + " " + nxt, 0)
                        if n2:
                            hits.append(f"{nxt}={n2}")
                    print(f"    {cur:<12} -> {', '.join(hits) or 'none'}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
