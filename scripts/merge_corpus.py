"""Merge per-source corpus builds into one directory by summing counts.

Inputs are directories produced by scripts/build_corpus.py. All five tables
are summed element-wise and re-sorted; the result is deterministic because
addition is commutative and keys are sorted. Mixing weights are controlled
upstream by extract-time sampling, not here. --min-count prunes low-frequency
rows after summing (the lite profile discards singleton bigrams and singleton
cased-bigrams: ~74% of bi rows, no measured accuracy cost on any gold).
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _sum_rows(path: Path, columns: int, out: dict[str, tuple[int, ...]]) -> None:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            key, vals = parts[0], tuple(int(v) for v in parts[1:])
            if len(vals) != columns:
                raise ValueError(f"{path}: expected {columns} count columns, got {line!r}")
            cur = out.get(key)
            out[key] = vals if cur is None else tuple(a + b for a, b in zip(cur, vals))


def _sum_table(paths: list[Path], columns: int) -> dict[str, tuple[int, ...]]:
    out: dict[str, tuple[int, ...]] = {}
    for path in paths:
        _sum_rows(path, columns, out)
    return out


TABLES = {
    "uni.tsv": 1,
    "bi.tsv": 1,
    "case.tsv": 4,
    "case_bi.tsv": 1,
    "abbreviations.txt": 1,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", nargs="+", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument(
        "--min-count",
        action="append",
        default=[],
        metavar="TABLE=MIN",
        help="drop merged rows of TABLE whose count is below MIN "
        "(e.g. --min-count bi.tsv=2 discards singleton bigrams)",
    )
    args = ap.parse_args(argv)

    limits: dict[str, int] = {}
    for spec in args.min_count:
        name, _, raw = spec.partition("=")
        limits[name] = int(raw)

    args.outdir.mkdir(parents=True, exist_ok=True)
    for name, columns in TABLES.items():
        paths = [d / name for d in args.inputs]
        merged = _sum_table([p for p in paths if p.exists()], columns)
        min_count = limits.get(name)
        with open(args.outdir / name, "w", encoding="utf-8") as fh:
            fh.writelines(
                key + "\t" + "\t".join(str(v) for v in merged[key]) + "\n"
                for key in sorted(merged)
                if min_count is None or merged[key][-1] >= min_count
            )
        print(f"{name}: {len(merged)} keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
