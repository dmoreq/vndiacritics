"""Write vap/data-clean/{uni,bi}.tsv with verified typos removed.

The source corpus (vap/data/) is never modified. Gold (in_domain.txt) is copied
byte-for-byte so both corpora are graded on exactly the same sentences.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "vap/data"
DST = ROOT / "vap/data-clean"


def main() -> int:
    typo_path = DST / "typos.json"
    if not typo_path.exists():
        print("run bench/build_typo_list.py first", file=sys.stderr)
        return 2
    drop = {r["word"] for r in json.loads(typo_path.read_text(encoding="utf-8"))["safe"]}
    print(f"dropping {len(drop):,} verified typo types")

    DST.mkdir(parents=True, exist_ok=True)

    kept_uni = dropped_uni = 0
    with open(SRC / "uni.tsv", encoding="utf-8", newline="") as src, \
            open(DST / "uni.tsv", "w", encoding="utf-8", newline="") as dst:
        for line in src:
            key, _, _count = line.rstrip("\n").rpartition("\t")
            if key in drop:
                dropped_uni += 1
                continue
            dst.write(line)
            kept_uni += 1

    kept_bi = dropped_bi = 0
    with open(SRC / "bi.tsv", encoding="utf-8", newline="") as src, \
            open(DST / "bi.tsv", "w", encoding="utf-8", newline="") as dst:
        for line in src:
            key, _, _count = line.rstrip("\n").rpartition("\t")
            left, _, right = key.partition(" ")
            if left in drop or right in drop:
                dropped_bi += 1
                continue
            dst.write(line)
            kept_bi += 1

    for name in ("in_domain.txt", "accent_groups.txt"):
        (DST / name).write_bytes((SRC / name).read_bytes())

    print(f"uni: kept {kept_uni:,}  dropped {dropped_uni:,}")
    print(f"bi : kept {kept_bi:,}  dropped {dropped_bi:,}")
    print(f"gold copied unchanged into {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
