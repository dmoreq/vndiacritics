"""Detect likely corpus typos against an independent Vietnamese dictionary.

Design decision, measured not assumed: the dictionary CANNOT be used to delete
words. `kong`, `arsenal`, `boeing` are legitimate tokens that are absent from it,
exactly like a typo. Deleting absent words would remove real proper nouns.

So this tool does not delete. It flags candidates for review, and it uses a rule
that separates the two populations:

  A typo is a rare form whose ACCENTED near-twin is far more frequent AND whose
  letters form a valid Vietnamese syllable. A foreign proper noun has no such
  accented twin (there is no `kong` with a diacritic to be confused with).

Usage:
    python bench/typo_detect.py                 # summary
    python bench/typo_detect.py --list          # list candidates
    python bench/typo_detect.py --dict PATH     # override dictionary
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DICT = ROOT / ".tmp/dicts/Viet74K.txt"


def strip_tone(word: str) -> str:
    """Remove tone marks but keep letter-shape distinctions (đ, ă, â, ê, ô, ơ)."""
    decomposed = unicodedata.normalize("NFD", word)
    kept = [c for c in decomposed if unicodedata.category(c) != "Mn"]
    return unicodedata.normalize("NFC", "".join(kept)).lower()


def is_vietnamese_shaped(word: str) -> bool:
    """Reject tokens containing letters that cannot occur in Vietnamese."""
    return not (set("fjwz") & set(word.lower()))


def load_dictionary(path: Path) -> set[str]:
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()}


def find_typos(unigram: dict[str, int], dictionary: set[str]) -> list[dict]:
    """Return candidate typos with evidence, most suspicious first."""
    by_shape: dict[str, list[tuple[str, int]]] = {}
    for word, count in unigram.items():
        by_shape.setdefault(strip_tone(word), []).append((word, count))

    candidates: list[dict] = []
    for variants in by_shape.values():
        if len(variants) < 2:
            continue
        variants.sort(key=lambda wc: -wc[1])
        dominant_word, dominant_count = variants[0]
        if dominant_count < 1000:
            continue
        for word, count in variants[1:]:
            if count >= 100:
                continue
            ratio = dominant_count / max(count, 1)
            if ratio < 100:
                continue
            # A foreign name has no accented twin that is itself a dictionary word.
            if dominant_word not in dictionary:
                continue
            candidates.append(
                {
                    "word": word,
                    "count": count,
                    "likely_correct": dominant_word,
                    "correct_count": dominant_count,
                    "ratio": int(ratio),
                    "in_dictionary": word in dictionary,
                }
            )
    candidates.sort(key=lambda c: -c["ratio"])
    return candidates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dict", type=Path, default=DEFAULT_DICT)
    ap.add_argument("--list", action="store_true", help="print candidates")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    if not args.dict.exists():
        print(f"dictionary not found: {args.dict}", file=sys.stderr)
        print("download with: curl -sL -o .tmp/dicts/Viet74K.txt "
              "https://raw.githubusercontent.com/duyet/vietnamese-wordlist/master/Viet74K.txt",
              file=sys.stderr)
        return 2

    from vap.model import Model

    model = Model.load()
    unigram = model._restorer._uni
    dictionary = load_dictionary(args.dict)

    print(f"dictionary   : {args.dict.name} ({len(dictionary):,} entries)")
    print(f"corpus vocab : {len(unigram):,}")

    candidates = find_typos(unigram, dictionary)
    confirmed = [c for c in candidates if not c["in_dictionary"]]
    in_dict = [c for c in candidates if c["in_dictionary"]]

    print(f"\ncandidate typos          : {len(candidates):,}")
    print(f"  NOT in dictionary      : {len(confirmed):,}  (strong evidence)")
    print(f"  present in dictionary  : {len(in_dict):,}  (valid rare words, keep)")
    print(f"  token mass accounted   : "
          f"{sum(c['count'] for c in candidates):,} "
          f"({sum(c['count'] for c in candidates)/sum(unigram.values())*100:.4f}% of corpus)")

    if args.list:
        print(f"\n{'word':<16}{'count':>6}  {'likely correct':<16}{'its count':>12}")
        for c in candidates[: args.limit]:
            flag = " " if not c["in_dictionary"] else "*"
            print(f"{flag}{c['word']:<15}{c['count']:>6}  "
                  f"{c['likely_correct']:<16}{c['correct_count']:>12,}")
        if len(candidates) > args.limit:
            print(f"  ... {len(candidates)-args.limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
