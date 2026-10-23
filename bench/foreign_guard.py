"""Refined lexicon experiment: only genuinely foreign tokens.

The first attempt failed (-1246 tokens) because "unaccented in gold" included
ordinary Vietnamese words the corpus happens to spell without diacritics. A
token is a foreign-name candidate only if it has no Vietnamese syllable shape:
it contains a non-Vietnamese letter (f, j, w, z) or is a known Latin-script name.
"""

from __future__ import annotations

import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case

# Letters that never occur in native Vietnamese orthography.
NON_VIETNAMESE = set("fjwzFJWZ")


def has_diacritic(t: str) -> bool:
    d = unicodedata.normalize("NFD", t)
    return any(unicodedata.combining(c) for c in d) or "\u0111" in t.lower()


def is_foreign_name(tok: str) -> bool:
    core = "".join(c for c in tok if c.isalnum())
    if not core or has_diacritic(core):
        return False
    return bool(NON_VIETNAMESE & set(core))


def main() -> int:
    model = Model.load()
    r = model._restorer
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    gold = [nfc(s) for s in split_sentences(raw)]
    stripped = [strip_accent_keep_case(s) for s in gold]

    pred = [r.restore(s) for s in stripped]
    base = score(gold, pred)
    print(f"current                     : {base.accuracy*100:.2f}% ({base.correct}/{base.total})")

    # How many errors involve a foreign-name token at all?
    foreign_errors = 0
    for s, g, p in zip(stripped, gold, pred):
        for src, gt, pt in zip(s.split(), g.split(), p.split()):
            if is_foreign_name(src) and gt.lower() != pt.lower():
                foreign_errors += 1
    n_foreign = sum(1 for s in stripped for t in s.split() if is_foreign_name(t))
    print(f"foreign-name tokens in input: {n_foreign}")
    print(f"  of which mis-restored     : {foreign_errors}")
    print()

    # Protect: if the input token is already identical to a foreign name, leave it.
    def restore_guarded(text: str) -> str:
        import re

        out = r.restore(text)
        om = list(re.finditer(r"\S+", text))
        pm = list(re.finditer(r"\S+", out))
        if len(om) != len(pm):
            return out
        pieces, end = [], 0
        for o, p in zip(om, pm):
            chosen = o.group() if is_foreign_name(o.group()) else p.group()
            pieces.append(out[end : p.start()])
            pieces.append(chosen)
            end = p.end()
        pieces.append(out[end:])
        return "".join(pieces)

    gp = [restore_guarded(s) for s in stripped]
    sg = score(gold, gp)
    print(f"with foreign-name guard     : {sg.accuracy*100:.2f}% ({sg.correct}/{sg.total})")
    print(f"  delta                     : {sg.correct - base.correct:+d} tokens")

    # List what the guard changed, so the effect is inspectable.
    changed = []
    for g, p, q in zip(gold, pred, gp):
        for a, b in zip(p.split(), q.split()):
            if a != b:
                changed.append((a, b))
    print(f"\n  tokens changed by guard   : {len(changed)}")
    for (a, b), n in Counter(changed).most_common(12):
        print(f"    {n:3d}x  {a!r} -> {b!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
