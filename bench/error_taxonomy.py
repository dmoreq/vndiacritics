"""Build a user-facing error taxonomy with real examples.

For every error family, extract actual sentences from the corpus so the report
shows what the user would see, not just counts.
"""

from __future__ import annotations

import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def has_diacritic(t: str) -> bool:
    d = unicodedata.normalize("NFD", t)
    return any(unicodedata.combining(c) for c in d) or "\u0111" in t.lower()


def family(gold_tok: str, got_tok: str, ctx: str) -> str:
    g, o = gold_tok.lower(), got_tok.lower()
    if g == o:
        return "identical"
    # tone-only difference on same base letters?
    gb = "".join(c for c in unicodedata.normalize("NFD", g) if not unicodedata.combining(c))
    ob = "".join(c for c in unicodedata.normalize("NFD", o) if not unicodedata.combining(c))
    if gb == ob:
        if not has_diacritic(g) and has_diacritic(o):
            return "added_diacritic_to_unaccented"
        if has_diacritic(g) and not has_diacritic(o):
            return "dropped_diacritic"
        return "wrong_tone"
    return "wrong_letter"


def main() -> int:
    model = Model.load()
    r = model._restorer
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    gold = [nfc(s) for s in split_sentences(raw)]
    stripped = [strip_accent_keep_case(s) for s in gold]
    pred = [r.restore(s) for s in stripped]

    fam_counts: Counter[str] = Counter()
    fam_examples: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    pair_counts: Counter[tuple[str, str]] = Counter()

    for s, g, p in zip(stripped, gold, pred):
        tg, tp = g.split(), p.split()
        for i, (gt, pt) in enumerate(zip(tg, tp)):
            if gt.lower() == pt.lower():
                continue
            f = family(gt, pt, s)
            fam_counts[f] += 1
            pair_counts[(gt, pt)] += 1
            if len(fam_examples[f]) < 6:
                lo = max(0, i - 3)
                hi = min(len(tg), i + 4)
                ctx = " ".join(tg[lo:hi])
                wrong_ctx = " ".join(tp[lo:hi])
                fam_examples[f].append((gt, pt, ctx, wrong_ctx))

    print("=" * 78)
    print("ERROR FAMILIES")
    print("=" * 78)
    for f, n in fam_counts.most_common():
        print(f"\n{f}: {n} tokens ({n / sum(fam_counts.values()) * 100:.1f}% of errors)")
        for gt, pt, ctx, wctx in fam_examples[f][:4]:
            print(f"  gold={gt!r} got={pt!r}")
            print(f"    correct context: {ctx}")
            print(f"    actual output  : {wctx}")

    # Ambiguity analysis: for the top confusions, how often does each direction occur?
    print()
    print("=" * 78)
    print("BIDIRECTIONAL CONFUSIONS (same two forms, both directions)")
    print("=" * 78)
    by_base: dict[str, Counter] = defaultdict(Counter)
    for gt, pt in pair_counts:
        key = tuple(sorted([gt.lower(), pt.lower()]))
        by_base["|".join(key)][(gt, pt)] += pair_counts[(gt, pt)]
    shown = 0
    for key, ctr in by_base.items():
        a, _, b = key.partition("|")
        forward = sum(n for (g, p), n in ctr.items() if g.lower() == a)
        backward = sum(n for (g, p), n in ctr.items() if g.lower() == b)
        if forward and backward:
            total = forward + backward
            if total >= 3 and shown < 10:
                print(
                    f"\n  {a} <-> {b}: {total} errors total "
                    f"(gold={a}: {forward}, gold={b}: {backward})"
                )
                for (g, p), n in ctr.most_common(4):
                    print(f"    {n:2d}x gold={g!r} got={p!r}")
                shown += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
