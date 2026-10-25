"""Multi-source consensus typo verification.

Principle (user-specified): a word agreed by many independent dictionaries is
correct; a word attested by only one source needs further verification.

Sources are genuinely independent:
  - Viet74K      (duyet, compiled frequency wordlist)
  - syllable     (vietnameselanguage, 6,653 phonologically valid syllables)
  - hunspell     (titoBouzout/hunspell-spellcheck-vi, 6,634 entries)
  - lingskr      (vi_dict.txt, corpus-derived)
  - underthesea  (3 upstream sources WITH per-word provenance:
                  hongocduc, tudientv, wiktionary)

The underthesea file carries its own multi-source evidence, so consensus can be
counted at two levels: across the 5 lists above, and within underthesea's 3
independent upstreams.

Usage:
    python bench/consensus_check.py --verify tróng vầ xêm kong arsenal long
    python bench/consensus_check.py --corpus-typos      # verify all candidates
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICTS = ROOT / ".tmp/dicts"


def strip_tone(word: str) -> str:
    d = unicodedata.normalize("NFD", word)
    kept = [c for c in d if unicodedata.category(c) != "Mn"]
    return unicodedata.normalize("NFC", "".join(kept)).lower()


def load_plain(name: str) -> set[str]:
    p = DICTS / name
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        w = line.strip().lower()
        # hunspell .dic starts with a count line
        if not w or w.isdigit():
            continue
        out.add(w)
    return out


def load_underthesea() -> dict[str, list[str]]:
    """Return word -> list of upstream sources that attest it."""
    p = DICTS / "uts.txt"
    if not p.exists():
        return {}
    out: dict[str, list[str]] = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = str(rec.get("text", "")).strip().lower()
        if text:
            out[text] = list(rec.get("source") or [])
    return out


class Sources:
    def __init__(self) -> None:
        self.lists = {
            "viet74k": load_plain("Viet74K.txt"),
            "syllable": load_plain("syllable_clean.txt"),
            "hunspell": load_plain("vi_VN.dic"),
            "lingskr": load_plain("vi_dict.txt"),
        }
        self.uts = load_underthesea()

    def lookup(self, word: str) -> dict:
        w = word.lower()
        present = {name: (w in lst) for name, lst in self.lists.items()}
        uts_src = self.uts.get(w, [])
        present["underthesea"] = bool(uts_src)
        agree = sum(present.values())
        return {
            "word": word,
            "lists_present": present,
            "agree_count": agree,
            "underthesea_upstreams": uts_src,
            "underthesea_upstream_count": len(uts_src),
        }

    def verdict(self, info: dict) -> str:
        """Classify by consensus, per the user's rule."""
        n = info["agree_count"]
        up = info["underthesea_upstream_count"]
        if n >= 3:
            return "CORRECT (strong consensus)"
        if n == 2:
            return "CORRECT (some consensus)"
        if n == 1:
            if up >= 2:
                return "LIKELY CORRECT (underthesea: 2+ upstreams)"
            return "UNVERIFIED (single source, needs lookup)"
        return "ABSENT (no source attests this)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", nargs="*", default=[], help="words to check")
    ap.add_argument("--corpus-typos", action="store_true", help="check every corpus typo candidate")
    args = ap.parse_args()

    src = Sources()
    total = sum(len(v) for v in src.lists.values())
    print("sources loaded:")
    for name, lst in src.lists.items():
        print(f"  {name:<12} {len(lst):>7,} entries")
    print(
        f"  {'underthesea':<12} {len(src.uts):>7,} entries "
        f"({sum(1 for v in src.uts.values() if len(v) >= 2):,} with 2+ upstreams)"
    )
    print(f"  {'TOTAL':<12} {total:,} (lists overlap; not a union size)")
    print()

    words = list(args.verify)
    if args.corpus_typos:
        from vap.model import Model

        uni = Model.load()._restorer._uni
        by_shape: dict[str, list[tuple[str, int]]] = {}
        for w, c in uni.items():
            by_shape.setdefault(strip_tone(w), []).append((w, c))
        for variants in by_shape.values():
            if len(variants) < 2:
                continue
            variants.sort(key=lambda wc: -wc[1])
            _top_w, top_c = variants[0]
            if top_c < 1000:
                continue
            for w, c in variants[1:]:
                if c < 100 and top_c / max(c, 1) >= 100:
                    words.append(w)

    if not words:
        print("nothing to verify; pass --verify or --corpus-typos")
        return 0

    print(f"{'word':<16}{'agree':>6}  {'sources present':<46}{'verdict'}")
    print("-" * 108)
    counts: dict[str, int] = {}
    for w in words:
        info = src.lookup(w)
        v = src.verdict(info)
        key = v.split(" (")[0]
        counts[key] = counts.get(key, 0) + 1
        present = ",".join(n for n, p in info["lists_present"].items() if p) or "-"
        print(f"{w:<16}{info['agree_count']:>6}  {present:<46}{v}")

    print()
    print("summary by verdict:")
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<34} {n:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
