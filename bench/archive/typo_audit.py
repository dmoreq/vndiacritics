"""How much of the corpus is genuinely misspelled (typos) vs legitimate rare words?

The distinction matters: removing typos is right on principle, but the previous
measurement showed rare-word errors cost only 2 of 359 tokens. This script sizes
the typo population so the decision is made on numbers, not principle alone.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from vap.model import Model


def nfd_strip(t: str) -> str:
    d = unicodedata.normalize("NFD", t)
    return "".join(c for c in d if not unicodedata.combining(c)).replace("\u0111", "d")


def main() -> int:
    model = Model.load()
    uni = model._restorer._uni

    # Vietnamese syllable inventory is closed-ish. A valid syllable must decompose
    # into (optional onset)(nucleus)(optional coda) from a known alphabet. Rather
    # than build a full grammar, use a proxy: a rare word is a likely typo if it is
    # one edit away from a far more frequent word with the SAME unaccented form.
    # That catches 'tróng' (vs 'trong') precisely, which is the pattern seen.
    rare = {w: c for w, c in uni.items() if c < 100}
    print(f"rare words (count < 100): {len(rare):,} "
          f"({len(rare)/len(uni)*100:.1f}% of vocabulary)")

    # Group rare words by the unaccented form they share with a frequent word.
    by_unaccented: dict[str, list[tuple[str, int]]] = {}
    for w, c in uni.items():
        key = nfd_strip(w).lower()
        by_unaccented.setdefault(key, []).append((w, c))

    typo_candidates = []
    for key, variants in by_unaccented.items():
        if len(variants) < 2:
            continue
        variants.sort(key=lambda vc: -vc[1])
        top_word, top_count = variants[0]
        for w, c in variants[1:]:
            # A typo-shaped rare variant: same letters, different tone mark, and
            # dwarfed by the dominant form.
            if c < 100 and top_count >= 1000 and top_count / max(c, 1) >= 100:
                typo_candidates.append((w, c, top_word, top_count))

    print(f"\nlikely typo variants (rare, same base letters as a >1000x form): "
          f"{len(typo_candidates):,}")
    print(f"  total tokens they account for: {sum(c for _, c, _, _ in typo_candidates):,} "
          f"({sum(c for _, c, _, _ in typo_candidates)/sum(uni.values())*100:.4f}% of corpus)")

    print("\n  Examples (rare form -> dominant correct form):")
    for w, c, tw, tc in sorted(typo_candidates, key=lambda x: x[1])[:15]:
        print(f"    {w:<12} count={c:<4} -> {tw:<12} count={tc:,}")

    # These specific words caused errors
    print("\n  Typo variants that appeared in wrong outputs:")
    for w in ("tróng", "vầ", "xêm"):
        if w in uni:
            key = nfd_strip(w).lower()
            dominant = max(by_unaccented[key], key=lambda vc: vc[1])
            print(f"    {w!r}: count={uni[w]}, dominant twin={dominant[0]!r} "
                  f"count={dominant[1]:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
