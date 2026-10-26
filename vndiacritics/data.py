"""Corpus loading. All counts come from tab-separated `key<TAB>count` files."""

from __future__ import annotations

import gzip
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def _open_text(path: Path):
    """Open a count table for reading; .gz tables are decompressed on the fly."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return open(path, encoding="utf-8", newline="")


def parse_count_table(path: Path) -> dict[str, int]:
    """Parse `key<TAB>count` lines. Keys may contain spaces (2-grams).

    Splits on the LAST tab so multi-word keys survive intact. Rows whose count is
    not an integer, or whose key is empty, are skipped rather than raising: the
    source corpora contain a handful of malformed lines. Plain and gzip-compressed
    tables are both accepted.
    """
    out: dict[str, int] = {}
    with _open_text(path) as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            key, sep, count = line.rpartition("\t")
            if not sep or not key:
                continue
            try:
                out[key] = int(count)
            except ValueError:
                continue
    return out


def load_unigram(path: Path | None = None) -> dict[str, int]:
    return parse_count_table(path or DATA_DIR / "uni.tsv")


def load_bigram(path: Path | None = None) -> dict[str, int]:
    return parse_count_table(path or DATA_DIR / "bi.tsv")
