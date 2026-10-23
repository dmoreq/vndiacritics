"""Count DP work and attribute lookup cost, to size each optimization."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def main() -> int:
    model = Model.load()
    r = model._restorer
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    sents = [strip_accent_keep_case(nfc(s)) for s in split_sentences(raw)]

    pairs = 0
    cells = 0
    cols_total = 0
    unk_pairs = 0
    hit_pairs = 0
    prior_calls = 0
    unigram_hits = 0
    picks = 0

    uni = r._uni
    bi = r._bi

    for s in sents:
        cols, _ = r._columns(s.split())
        cols_total += len(cols)
        for c in cols:
            cells += len(c)
        if len(cols) < 2:
            continue
        for i in range(1, len(cols)):
            for cur in cols[i]:
                for prev in cols[i - 1]:
                    pairs += 1
                    n1 = uni.get(prev, 0)
                    n2 = bi.get(prev + " " + cur, 0)
                    if n1 > 0 and n2 > 0:
                        hit_pairs += 1
                    else:
                        unk_pairs += 1
                    if i == 1:
                        prior_calls += 1
                        if n1 > 0:
                            unigram_hits += 1
        picks += len(cols) - 1

    print(f"sentences            : {len(sents)}")
    print(f"columns (tokens)     : {cols_total}")
    print(f"candidate cells      : {cells}")
    print(f"DP pairs evaluated   : {pairs}")
    print(f"  bigram hits        : {hit_pairs} ({hit_pairs/pairs*100:.1f}%)")
    print(f"  UNK fallbacks      : {unk_pairs} ({unk_pairs/pairs*100:.1f}%)")
    print(f"  unigram prior calls: {prior_calls} ({prior_calls/pairs*100:.1f}% of pairs)")
    print(f"avg pairs per sentence: {pairs/len(sents):.1f}")
    print(f"avg candidates per col: {cells/cols_total:.2f}")

    # Cost of one trie get vs one dict get, measured directly.
    keys = [f"a b{i}" for i in range(200_000)]
    t = time.perf_counter()
    for k in keys:
        bi.get(k)
    trie_us = (time.perf_counter() - t) / len(keys) * 1e6

    d = {}
    t = time.perf_counter()
    for k in keys:
        d.get(k)
    dict_us = (time.perf_counter() - t) / len(keys) * 1e6

    print(f"\ntrie get : {trie_us:.3f} us/call  -> {pairs*trie_us/1e6:.3f}s for this corpus")
    print(f"dict get : {dict_us:.3f} us/call  -> {pairs*dict_us/1e6:.3f}s for this corpus")
    print(f"delta if trie were a dict: {(trie_us-dict_us)*pairs/1e6:.3f}s saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
