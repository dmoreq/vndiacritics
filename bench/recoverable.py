"""How much of the 359 residual errors is actually recoverable?

Each experiment below is scored on the same 8,995-token corpus. An upper bound is
computed first (oracle over the existing lattice), then real fixes are attempted,
so the gap between "possible" and "achievable" is explicit.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def load():
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    gold = [nfc(s) for s in split_sentences(raw)]
    return gold, [strip_accent_keep_case(s) for s in gold]


def main() -> int:
    model = Model.load()
    r = model._restorer
    gold, stripped = load()

    pred = [r.restore(s) for s in stripped]
    base = score(gold, pred)
    print(f"current              : {base.accuracy*100:.2f}% ({base.correct}/{base.total})")
    print(f"errors               : {base.total - base.correct}")
    print()

    # ---- UPPER BOUND: oracle over the existing lattice -------------------------
    # If the decoder always picked the gold form when it is present, and nothing
    # else changed, this is the ceiling for decoder-only improvements.
    oracle_ok = 0
    oov = 0
    for s, g in zip(stripped, gold):
        cols, _ = r._columns(s.split())
        tg = g.split()
        for i, col in enumerate(cols):
            if i >= len(tg):
                break
            lowered = [c.lower() for c in col]
            if tg[i].lower() in lowered:
                oracle_ok += 1
            else:
                oov += 1
    print("DECODER CEILING (oracle over lattice)")
    print(f"  tokens with gold in lattice : {oracle_ok} "
          f"({oracle_ok/base.total*100:.2f}%)")
    print(f"  tokens OOV (unreachable)    : {oov} "
          f"({oov/base.total*100:.2f}%)")
    print(f"  => best possible by decoder : {oracle_ok/base.total*100:.2f}%")
    print(f"  => recoverable by decoder   : {oracle_ok - base.correct} tokens")
    print()

    # ---- EXPERIMENT 1: proper-noun / loanword lexicon --------------------------
    # Build a list of tokens that in the gold corpus appear WITHOUT diacritics even
    # though an accented form exists. If a candidate column contains such a token
    # AND the input token is already identical to it, prefer leaving it alone.
    import unicodedata

    def has_diacritic(t: str) -> bool:
        d = unicodedata.normalize("NFD", t)
        return any(unicodedata.combining(c) for c in d) or "đ" in t.lower()

    # tokens that gold writes unaccented while the unigram table knows an accented twin
    unaccented_gold = Counter()
    for g in gold:
        for t in g.split():
            core = "".join(c for c in t if c.isalnum())
            if core and not has_diacritic(core):
                unaccented_gold[core.lower()] += 1
    protected = {
        t for t in unaccented_gold
        if unaccented_gold[t] >= 2 and r._uni.get(t, 0) > 0
    }
    print("EXPERIMENT 1: protect unaccented gold tokens (lexicon proxy)")
    print(f"  protected vocabulary size : {len(protected)}")

    saved = r._bigram_skip_below
    # Apply: after decoding, revert any token whose ORIGINAL form is in protected set
    def restore_protected(text: str) -> str:
        out = r.restore(text)
        import re

        om = list(re.finditer(r"\S+", text))
        pm = list(re.finditer(r"\S+", out))
        if len(om) != len(pm):
            return out
        pieces = []
        end = 0
        for o, p in zip(om, pm):
            core = "".join(c for c in o.group() if c.isalnum()).lower()
            chosen = p.group() if core not in protected else o.group()
            pieces.append(out[end : p.start()])
            pieces.append(chosen)
            end = p.end()
        pieces.append(out[end:])
        return "".join(pieces)

    pred_p = [restore_protected(s) for s in stripped]
    sp = score(gold, pred_p)
    print(f"  with protection           : {sp.accuracy*100:.2f}% ({sp.correct}/{sp.total})")
    print(f"  delta vs current          : {sp.correct - base.correct:+d} tokens")
    print()

    # ---- EXPERIMENT 2: char-level fallback for OOV ----------------------------
    # Cheap test: does the OOV token have a close accented neighbour in the
    # unigram table? If not, no character model could guess it either.
    print("EXPERIMENT 2: are the OOV tokens even recoverable in principle?")
    recovered = 0
    examples = []
    for s, g, p in zip(stripped, gold, pred):
        cols, _ = r._columns(s.split())
        tg = g.split()
        for i, col in enumerate(cols):
            if i >= len(tg):
                break
            if tg[i].lower() in [c.lower() for c in col]:
                continue
            # OOV: can we at least find the accented form elsewhere in the table?
            if r._uni.get(tg[i].lower(), 0) > 0:
                recovered += 1
                if len(examples) < 5:
                    examples.append((s.split()[i], tg[i]))
    print(f"  OOV where gold exists in unigram table : {recovered}")
    print(f"  OOV where gold is absent entirely      : {oov - recovered}")
    if examples:
        print("  examples gold-known-but-not-in-lattice:", examples)
    r._bigram_skip_below = saved
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
