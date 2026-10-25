"""Build gazetteer files for the truecaser from MIT/CC-BY name sources.

Outputs (title-cased full names, NFC, deduped, sorted):
  names_persons.txt  from duyet/vietnamese-namedb boy.txt + girl.txt (MIT)
  names_places.txt   from GeoNames VN.zip populated/administrative names (CC BY 4.0)

Usage:
  python scripts/build_gazetteer.py PERSONS_DIR/GEO_DIR... --outdir DIR
  # persons: directory containing boy.txt/girl.txt (raw text, one name per line)
  # places:  directory containing VN.txt (GeoNames dump, unzipped)
"""

from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path

# GeoNames feature classes kept: A = administrative, P = populated place.
_KEEP_FEATURE = frozenset({"A", "P"})


def person_names(persons_dir: Path) -> set[str]:
    """Read the two full-name files explicitly; a glob would swallow GeoNames
    VN.txt when both live in the same fetch directory."""
    names: set[str] = set()
    for filename in ("boy.txt", "girl.txt"):
        path = persons_dir / filename
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                name = unicodedata.normalize("NFC", line.strip())
                if len(name.split()) >= 2:
                    names.add(name)
    return names


def place_names(geo_dir: Path) -> set[str]:
    names: set[str] = set()
    vn = geo_dir / "VN.txt"
    if not vn.exists():
        raise FileNotFoundError(f"{vn} not found; unzip GeoNames VN.zip first")
    with open(vn, encoding="utf-8") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 8 or cols[6] not in _KEEP_FEATURE:
                continue
            name = unicodedata.normalize("NFC", cols[1].strip())
            if name and len(name.split()) <= 4:
                names.add(name)
    return names


def write(names: set[str], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(name + "\n" for name in sorted(names))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--persons", type=Path, required=True, help="dir with boy.txt/girl.txt")
    ap.add_argument("--places", type=Path, required=True, help="dir with VN.txt")
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args(argv)

    args.outdir.mkdir(parents=True, exist_ok=True)
    persons = person_names(args.persons)
    places = place_names(args.places)
    write(persons, args.outdir / "names_persons.txt")
    write(places, args.outdir / "names_places.txt")
    print(f"persons={len(persons)} places={len(places)} -> {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
