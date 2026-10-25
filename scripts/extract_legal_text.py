"""Extract statute text from the th1nhng0/vietnamese-legal-documents parquet.

Streams content.parquet with pyarrow, one output line per cleaned document
paragraph. Deterministic. Requires pyarrow (run via uvx --with pyarrow).

Usage:
  uvx --with pyarrow python scripts/extract_legal_text.py content.parquet OUT.txt

Corpus: th1nhng0/vietnamese-legal-documents, CC BY 4.0; see CORPORA.md.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pyarrow.parquet as pq

_ARTICLE = re.compile(r"^Điều \d+\.")
_NOISE = re.compile(
    r"(Nơi nhận|bản sao|kèm theo|theo dấu|Website|Cơ quan thường trực|"
    r"KT\. ?CHỦ TỊCH|THỦ TƯỚNG|CHỦ TỊCH NƯỚC)",
)


def keep(line: str) -> bool:
    if len(line) < 60:  # statutes are long-form prose
        return False
    if _NOISE.search(line):
        return False
    letters = sum(ch.isalpha() for ch in line)
    return letters >= 0.5 * len(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("parquet", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--limit", type=int, default=0, help="stop after N docs (0 = all)")
    args = ap.parse_args(argv)

    pf = pq.ParquetFile(args.parquet)
    total = kept = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for batch in pf.iter_batches(batch_size=256, columns=None):
            col = batch.column(0)
            for i in range(len(col)):
                total += 1
                if args.limit and kept >= args.limit:
                    print(f"docs={total} kept={kept} (limit {args.limit}) -> {args.out}")
                    return 0
                doc = col[i].as_py()
                if not isinstance(doc, str):
                    continue
                for raw in doc.splitlines():
                    line = unicodedata.normalize("NFC", raw).strip()
                    if keep(line):
                        kept += 1
                        out.write(line + "\n")
    print(f"docs={total} kept={kept} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
