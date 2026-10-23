"""Deep diagnosis of restoration failures.

Two populations are separated because they need different fixes:
  A. The 4 tokens the skip broke (was right, now wrong).
  B. All remaining wrong tokens in-domain (never right).

For each, record what the lattice looked like and why the decoder chose wrongly.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case

IN = ROOT / "vap/data/in_domain.txt"


def load():
    raw = IN.read_text(encoding="utf-8")
    gold = [nfc(s) for s in split_sentences(raw)]
    return gold, [strip_accent_keep_case(s) for s in gold]


def trace(model, sent, gold_sent):
    """Re-run one sentence and report, per token, the chosen form and its score."""
    r = model._restorer
    import re

    matches = list(re.finditer(r"\S+", sent))
    cols, _affixes = r._columns([m.group() for m in matches])
    if len(cols) < 2:
        return None
    chosen = r._viterbi(cols)
    rows = []
    gtok = gold_sent.split()
    for i, (col, pick) in enumerate(zip(cols, chosen)):
        gold_tok = gtok[i] if i < len(gtok) else "?"
        if gold_tok.lower() == pick.lower():
            continue
        ranked = sorted(col, key=lambda w: -r._uni.get(w, 0))
        rows.append(
            {
                "pos": i,
                "gold": gold_tok,
                "picked": pick,
                "gold_in_col": gold_tok.lower() in [c.lower() for c in col],
                "col_size": len(col),
                "col_top5": ranked[:5],
                "picked_rank": (
                    ranked.index(pick) if pick in ranked else -1
                ),
                "uni_gold": r._uni.get(gold_tok.lower(), 0),
                "uni_picked": r._uni.get(pick.lower(), 0),
                "prev": chosen[i - 1] if i else None,
                "next": chosen[i + 1] if i + 1 < len(chosen) else None,
            }
        )
    return rows


def main() -> int:
    model = Model.load()
    r = model._restorer
    gold, stripped = load()

    # Population A: the skip-induced regressions.
    saved = r._bigram_skip_below
    r._bigram_skip_below = 0
    pred_base = [r.restore(s) for s in stripped]
    r._bigram_skip_below = saved
    pred_opt = [r.restore(s) for s in stripped]

    print("=" * 78)
    print("POPULATION A: broken by the skip (was right, now wrong)")
    print("=" * 78)
    a_rows = []
    for g, b, o in zip(gold, pred_base, pred_opt):
        tg = g.split()
        for i, (gb, ob) in enumerate(zip(b.split(), o.split())):
            gt = tg[i] if i < len(tg) else "?"
            if gb.lower() == gt.lower() and ob.lower() != gt.lower():
                a_rows.append((g, i, gt, gb, ob))
    for g, i, gt, gb, ob in a_rows:
        rows = trace(model, strip_accent_keep_case(g), g)
        row = next((x for x in rows if x["pos"] == i), None)
        print(f"\n  sentence: {g[:90]}")
        print(f"  token   : gold={gt!r} baseline={gb!r} optimized={ob!r}")
        if row:
            print(f"  lattice : size={row['col_size']} gold_present={row['gold_in_col']}")
            print(f"  top5    : {row['col_top5']}")
            print(f"  unigram : gold={row['uni_gold']:,} picked={row['uni_picked']:,}")
            print(f"  context : prev={row['prev']!r} next={row['next']!r}")

    print()
    print("=" * 78)
    print("POPULATION B: all remaining wrong tokens (optimized model)")
    print("=" * 78)
    wrong = []
    not_in_col = 0
    total = 0
    rank_counts = Counter()
    for g, o in zip(gold, pred_opt):
        tg, to = g.split(), o.split()
        rows = trace(model, strip_accent_keep_case(g), g) or []
        by_pos = {x["pos"]: x for x in rows}
        for i, (gt, ot) in enumerate(zip(tg, to)):
            total += 1
            if gt.lower() == ot.lower():
                continue
            wrong.append((gt, ot))
            row = by_pos.get(i)
            if row:
                if not row["gold_in_col"]:
                    not_in_col += 1
                else:
                    rk = row["picked_rank"]
                    rank_counts[rk if rk >= 0 else 99] += 1

    print(f"\ntotal tokens          : {total}")
    print(f"wrong tokens          : {len(wrong)} ({len(wrong)/total*100:.2f}%)")
    print(f"  gold NOT in lattice : {not_in_col} ({not_in_col/len(wrong)*100:.2f}% of errors)")
    print(f"  gold in lattice     : {len(wrong)-not_in_col}")
    print("\n  When gold is in the lattice, rank of the chosen form by unigram:")
    for rk, n in sorted(rank_counts.items())[:8]:
        label = f"rank {rk}" if rk != 99 else "not ranked"
        print(f"    {label:>12}: {n}")

    print("\n  Most frequent wrong tokens:")
    for (gt, ot), n in Counter(wrong).most_common(25):
        print(f"    {n:3d}x  gold={gt:<12} got={ot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
