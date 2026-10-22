"""Can a miss be predicted without walking the trie?

The DP evaluates 463k pairs; 79.8% are guaranteed misses. If a cheap pre-check on
the two unigrams can rule out most of them, the trie walk is skipped entirely.
This measures whether such a rule is safe (no lost hits) and how much it covers.
"""

from __future__ import annotations

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
    uni = r._uni
    bi = r._bi
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    sents = [strip_accent_keep_case(nfc(s)) for s in split_sentences(raw)]

    pairs = hits = 0
    # Rule A: if prev has count 0, the pair cannot exist (bigram implies unigram).
    rule_a_would_skip = rule_a_wrong = 0
    # Rule B: if the current word is absent from the vocabulary entirely.
    rule_b_would_skip = rule_b_wrong = 0
    both_skip = 0

    for s in sents:
        cols, _ = r._columns(s.split())
        for i in range(1, len(cols)):
            for cur in cols[i]:
                for prev in cols[i - 1]:
                    pairs += 1
                    n1 = uni.get(prev, 0)
                    n2 = bi.get(prev + " " + cur, 0)
                    if n2:
                        hits += 1
                    a = n1 == 0
                    b = uni.get(cur, 0) == 0
                    if a:
                        rule_a_would_skip += 1
                        if n2:
                            rule_a_wrong += 1
                    if b:
                        rule_b_would_skip += 1
                        if n2:
                            rule_b_wrong += 1
                    if a and b:
                        both_skip += 1

    print(f"pairs            : {pairs}")
    print(f"actual hits      : {hits} ({hits/pairs*100:.1f}%)")
    print()
    print("Rule A (prev unigram == 0):")
    print(f"  would skip     : {rule_a_would_skip} ({rule_a_would_skip/pairs*100:.1f}%)")
    print(f"  WRONG to skip  : {rule_a_wrong}   <- must be 0 for safety")
    print()
    print("Rule B (cur unigram == 0):")
    print(f"  would skip     : {rule_b_would_skip} ({rule_b_would_skip/pairs*100:.1f}%)")
    print(f"  WRONG to skip  : {rule_b_wrong}   <- must be 0 for safety")
    print()
    print(f"both rules       : {both_skip} ({both_skip/pairs*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
