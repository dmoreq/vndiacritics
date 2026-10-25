"""Extract the Vietnamese side of an OPUS OpenSubtitles moses-format zip.

Filters subtitle noise so the surviving lines are dialogue: drops credit
lines (sync teams, site ads), very short interjections, and pure-Latin lines.
Dialogue casing is preserved for the truecaser. Deterministic: file order
equals archive order, one output line per surviving subtitle line.

Usage:
  python scripts/extract_opus_vi.py OpenSubtitles.en-vi.txt.zip OUT.txt

Corpus: OPUS OpenSubtitles v2024, ODC-BY; see CORPORA.md.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
import zipfile
from pathlib import Path

_CREDIT = re.compile(
    r"(sync|subtitle|subtitles|corrected|resync|fixes?|encoding|downloaded|"
    r"opensubtitles|subscene|addic7ed|yify|rarbg|www\.|http|\.com|\.net|\.org|"
    r"chú ý|đồng bộ|phụ đề|phim|subteam|nhanh|chất lượng)",
    re.IGNORECASE,
)


def keep(line: str) -> bool:
    if len(line) < 12:
        return False
    if _CREDIT.search(line):
        return False
    letters = sum(ch.isalpha() for ch in line)
    if letters < 0.5 * len(line):
        return False
    # Vietnamese dialogue must contain at least one Vietnamese-range letter.
    return any("\u00c0" <= ch <= "\u1ef9" or ch == "đ" or ch == "Đ" for ch in line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("zip", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args(argv)

    total = kept = 0
    with zipfile.ZipFile(args.zip) as zf:
        vi_name = next(n for n in zf.namelist() if n.endswith(".vi"))
        with zf.open(vi_name) as src, open(args.out, "w", encoding="utf-8") as out:
            for raw in src:
                total += 1
                line = unicodedata.normalize("NFC", raw.decode("utf-8", "replace")).strip()
                if keep(line):
                    kept += 1
                    out.write(line + "\n")
    print(f"lines={total} kept={kept} ({100 * kept / max(total, 1):.1f}%) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
