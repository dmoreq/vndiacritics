"""Build the verified typo list. No deletions happen here; this only writes evidence.

A word is only proposed for removal when BOTH hold:
  1. no dictionary attests it (0 of 5), and
  2. its accent-stripped twin is attested by at least `--min-twin-sources` sources
     while being at least `--min-ratio` times more frequent.

Requirement (1) alone is not enough: foreign names (kong, arsenal) and Vietnamese
proper nouns are absent from every dictionary too.

Run scripts/fetch_dicts.sh first.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DICTS = ROOT / ".tmp/dicts"

# Words proven correct by all five sources. Removing any of them is a measured
# regression -- `tróng` in particular is a real word ("drained, dry") that an
# earlier heuristic wrongly flagged as a typo of `trong`.
MUST_KEEP = {
    "tróng",
    "trong",
    "long",
    "lỏng",
    "khanh",
    "hồng",
    "bệnh",
    "đường",
    "và",
    "xem",
    "người",
    "được",
    "không",
    "những",
    "của",
    "với",
    "thành",
    "tăng",
}


def strip_tone(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word)
    kept = [c for c in decomposed if unicodedata.category(c) != "Mn"]
    return unicodedata.normalize("NFC", "".join(kept)).lower()


def load_plain(name: str) -> set[str]:
    path = DICTS / name
    out: set[str] = set()
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        word = line.strip().lower()
        if word and not word.isdigit():
            out.add(word)
    return out


def load_underthesea() -> dict[str, list[str]]:
    path = DICTS / "uts.txt"
    out: dict[str, list[str]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = str(record.get("text", "")).strip().lower()
        if text:
            out[text] = list(record.get("source") or [])
    return out


def consensus(word: str, lists: dict[str, set[str]], uts: dict[str, list[str]]) -> int:
    return sum(1 for entries in lists.values() if word in entries) + (1 if word in uts else 0)


def assert_protected(safe: list[dict]) -> None:
    clash = MUST_KEEP & {record["word"] for record in safe}
    if clash:
        raise SystemExit(f"protected words in delete list: {sorted(clash)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "vap/data-clean/typos.json")
    ap.add_argument("--min-twin-sources", type=int, default=2)
    ap.add_argument("--min-ratio", type=int, default=100)
    ap.add_argument("--max-rare-count", type=int, default=100)
    args = ap.parse_args()

    from vap.data import load_unigram

    unigram = load_unigram()
    lists = {
        "viet74k": load_plain("Viet74K.txt"),
        "syllable": load_plain("syllable_clean.txt"),
        "hunspell": load_plain("vi_VN.dic"),
        "lingskr": load_plain("vi_dict.txt"),
    }
    uts = load_underthesea()
    if not any(lists.values()):
        print("no dictionaries found; run scripts/fetch_dicts.sh", file=sys.stderr)
        return 2

    by_shape: dict[str, list[tuple[str, int]]] = {}
    for word, count in unigram.items():
        by_shape.setdefault(strip_tone(word), []).append((word, count))

    safe: list[dict] = []
    review: list[dict] = []
    for variants in by_shape.values():
        if len(variants) < 2:
            continue
        variants.sort(key=lambda wc: -wc[1])
        twin, twin_count = variants[0]
        twin_sources = consensus(twin, lists, uts)
        for word, count in variants[1:]:
            if count >= args.max_rare_count:
                continue
            if twin_count / max(count, 1) < args.min_ratio:
                continue
            if consensus(word, lists, uts) != 0:
                continue
            record = {
                "word": word,
                "count": count,
                "twin": twin,
                "twin_count": twin_count,
                "twin_sources": twin_sources,
            }
            if twin_sources >= args.min_twin_sources:
                safe.append(record)
            else:
                review.append(record)

    assert_protected(safe)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"safe": safe, "review": review}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"safe typos  : {len(safe):,}  tokens={sum(r['count'] for r in safe):,}")
    print(f"needs review: {len(review):,}  (NOT removed)")
    print(f"written to  : {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
