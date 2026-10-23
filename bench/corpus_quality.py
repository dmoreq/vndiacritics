"""Quantify how much of the error budget is caused by corpus quality.

Three questions:
  1. How much of the bigram table is noise (typos / rare junk)?
  2. If noise were removed, how many errors would go away? (upper bound)
  3. Are the gold labels themselves inconsistent (would a better corpus help)?
"""

from __future__ import annotations

import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.data import parse_count_table, DATA_DIR
from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def has_diacritic(t: str) -> bool:
    d = unicodedata.normalize("NFD", t)
    return any(unicodedata.combining(c) for c in d) or "\u0111" in t.lower()


def main() -> int:
    model = Model.load()
    r = model._restorer
    uni = r._uni

    print("=" * 74)
    print("1. CORPUS SIZE AND NOISE PROFILE")
    print("=" * 74)
    total_types = len(uni)
    total_tokens = sum(uni.values())
    print(f"  vocabulary (types)  : {total_types:,}")
    print(f"  total tokens        : {total_tokens:,}")

    buckets = [("1", 0, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-20", 6, 20),
               ("21-100", 21, 100), ("101-1k", 101, 1000), ("1k+", 1001, 10**12)]
    print(f"\n  {'count band':>12} {'types':>10} {'% types':>9} {'tokens':>14} {'% tokens':>9}")
    for label, lo, hi in buckets:
        types = sum(1 for c in uni.values() if lo <= c <= hi)
        toks = sum(c for c in uni.values() if lo <= c <= hi)
        print(f"  {label:>12} {types:>10,} {types/total_types*100:8.2f}% "
              f"{toks:>14,} {toks/total_tokens*100:8.2f}%")

    # Tokens below the skip threshold that still carry count>0
    thr = r._bigram_skip_below
    below = sum(1 for c in uni.values() if 0 < c < thr)
    print(f"\n  types below skip threshold ({thr}): {below:,} "
          f"({below/total_types*100:.2f}% of vocabulary)")

    print()
    print("=" * 74)
    print("2. BIGRAM TABLE NOISE")
    print("=" * 74)
    bi_path = DATA_DIR / "bi.tsv"
    print(f"  bi.tsv size: {bi_path.stat().st_size / 1024 / 1024:.1f} MB")
    # Count hapax bigrams by streaming (5.5M rows - do not build a dict of all)
    n_rows = 0
    n_hapax = 0
    n_le5 = 0
    with open(bi_path, encoding="utf-8", newline="") as fh:
        for line in fh:
            n_rows += 1
            _, _, cnt = line.rstrip("\n").rpartition("\t")
            try:
                c = int(cnt)
            except ValueError:
                continue
            if c == 1:
                n_hapax += 1
            if c <= 5:
                n_le5 += 1
    print(f"  bigram rows          : {n_rows:,}")
    print(f"  hapax (count == 1)   : {n_hapax:,} ({n_hapax/n_rows*100:.1f}%)")
    print(f"  count <= 5           : {n_le5:,} ({n_le5/n_rows*100:.1f}%)")

    print()
    print("=" * 74)
    print("3. GOLD LABEL CONSISTENCY")
    print("=" * 74)
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    gold = [nfc(s) for s in split_sentences(raw)]
    stripped = [strip_accent_keep_case(s) for s in gold]

    # Same unaccented token, different gold spellings => the gold itself is ambiguous.
    surface: dict[str, Counter] = {}
    for s in gold:
        for t in s.split():
            key = strip_accent_keep_case(t).lower()
            surface.setdefault(key, Counter())[t.lower()] += 1

    ambiguous = {k: v for k, v in surface.items() if len(v) > 1}
    print(f"  unaccented forms with >1 gold spelling: {len(ambiguous):,} "
          f"of {len(surface):,}")
    print("\n  Most contested forms (same input, different correct outputs):")
    ranked = sorted(ambiguous.items(), key=lambda kv: -sum(kv[1].values()))[:12]
    for key, variants in ranked:
        tot = sum(variants.values())
        parts = ", ".join(f"{v}={n}" for v, n in variants.most_common(4))
        print(f"    {key:<12} total={tot:<4} {parts}")

    print()
    print("=" * 74)
    print("4. UPPER BOUND: if the corpus had no rare-junk words")
    print("=" * 74)
    pred = [r.restore(s) for s in stripped]
    base = score(gold, pred)
    print(f"  current accuracy: {base.accuracy*100:.2f}% ({base.correct}/{base.total})")
    print("\n  Errors whose WRONG output is a rare corpus word (count < 100):")
    rare_wrong = 0
    samples = []
    for g, p in zip(gold, pred):
        for gt, pt in zip(g.split(), p.split()):
            if gt.lower() == pt.lower():
                continue
            if uni.get(pt.lower(), 0) < 100:
                rare_wrong += 1
                if len(samples) < 8:
                    samples.append((gt, pt, uni.get(pt.lower(), 0)))
    print(f"    {rare_wrong} tokens ({rare_wrong/base.total*100:.2f}% of corpus)")
    for gt, pt, c in samples:
        print(f"      gold={gt:<10} got={pt:<10} (corpus count {c})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
