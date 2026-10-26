"""Write vndiacritics/data-clean/{uni,bi}.tsv with verified typos removed.

The source corpus (vndiacritics/data/) is never modified. Gold (in_domain.txt) is copied
byte-for-byte so both corpora are graded on exactly the same sentences.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "vndiacritics/data"
DST = ROOT / "vndiacritics/data-clean"


def _open_source(path: Path) -> IO[str]:
    """Plain or gzip-compressed count table, as text lines."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return open(path, encoding="utf-8", newline="")


def main() -> int:
    typo_path = DST / "typos.json"
    if not typo_path.exists():
        print("run bench/build_typo_list.py first", file=sys.stderr)
        return 2
    drop = {r["word"] for r in json.loads(typo_path.read_text(encoding="utf-8"))["safe"]}
    print(f"dropping {len(drop):,} verified typo types")

    DST.mkdir(parents=True, exist_ok=True)

    kept_uni = dropped_uni = 0
    with (
        open(SRC / "uni.tsv", encoding="utf-8", newline="") as src,
        open(DST / "uni.tsv", "w", encoding="utf-8", newline="") as dst,
    ):
        for line in src:
            key, _, _count = line.rstrip("\n").rpartition("\t")
            if key in drop:
                dropped_uni += 1
                continue
            dst.write(line)
            kept_uni += 1

    kept_bi = dropped_bi = 0
    bi_source = SRC / "bi.tsv"
    if not bi_source.exists():
        bi_source = SRC / "bi.tsv.gz"  # recovery keeps the large TSV compressed
    with (
        _open_source(bi_source) as src,
        open(DST / "bi.tsv", "w", encoding="utf-8", newline="") as dst,
    ):
        for line in src:
            key, _, _count = line.rstrip("\n").rpartition("\t")
            left, _, right = key.partition(" ")
            if left in drop or right in drop:
                dropped_bi += 1
                continue
            dst.write(line)
            kept_bi += 1

    (DST / "in_domain.txt").write_bytes((SRC / "in_domain.txt").read_bytes())

    print(f"uni: kept {kept_uni:,}  dropped {dropped_uni:,}")
    print(f"bi : kept {kept_bi:,}  dropped {dropped_bi:,}")
    print(f"gold copied unchanged into {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
