"""A/B the bigram_conf_k Jelinek-Mercer blend against both gold corpora.

Grades the reference pipelines for several K values plus the canonical
number-context bug sentence, so the chosen default comes from measurement.
Output feeds docs/reports/2026-10-25-number-context-fix.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vndiacritics.data import load_unigram
from vndiacritics.eval import score, split_sentences
from vndiacritics.index import CandidateIndex
from vndiacritics.model import Model
from vndiacritics.normalize import nfc, strip_accent_keep_case
from vndiacritics.restore import Restorer
from vndiacritics.store import BigramStore

IN_DOMAIN = ROOT / "vndiacritics/data/in_domain.txt"
OUT_DOMAIN = ROOT / "bench/data/diacritic_eval_v0.txt"
BUG = "tang 12.5% trong nam 2025"
KS = [0, 10, 100, 1000, 10000]


def gold(path: Path) -> list[str]:
    return [nfc(s) for s in split_sentences(path.read_text(encoding="utf-8"))]


def grade(restorer: Restorer, golds: list[str]) -> float:
    preds = [restorer.restore(strip_accent_keep_case(g)) for g in golds]
    return score(golds, preds).accuracy


def main() -> None:
    model = Model.load()
    uni = load_unigram()
    index = CandidateIndex(uni)
    store = BigramStore.load(ROOT / "vndiacritics/data/bi.trie")
    del model
    in_gold = gold(IN_DOMAIN)
    out_gold = gold(OUT_DOMAIN)
    bare = strip_accent_keep_case(BUG)

    print(f"{'K':>6} | {'in-domain':>9} | {'out-domain':>10} | bug sentence")
    print("-" * 72)
    for k in KS:
        r = Restorer(uni, index, store, bigram_conf_k=k)
        ai = grade(r, in_gold)
        ao = grade(r, out_gold)
        print(f"{k:>6} | {ai * 100:>8.4f}% | {ao * 100:>9.4f}% | {r.restore(bare)}")


if __name__ == "__main__":
    main()
