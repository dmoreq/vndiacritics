"""Extract statute text from the th1nhng0/vietnamese-legal-documents parquet.

Streams content.parquet with pyarrow. The `content_html` column holds full
HTML documents, so text is pulled with a stdlib HTMLParser that keeps block
text and drops head/style/script. One output line per surviving paragraph.
Deterministic. Requires pyarrow (run via uvx --with pyarrow).

Usage:
  uvx --with pyarrow python scripts/extract_legal_text.py content.parquet OUT.txt

Corpus: th1nhng0/vietnamese-legal-documents, CC BY 4.0; see CORPORA.md.
"""

from __future__ import annotations

import argparse
import re
import typing
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

import pyarrow.parquet as pq

_NOISE = re.compile(
    r"(Nơi nhận|bản sao|kèm theo|theo dấu|Cơ quan thường trực|"
    r"KT\. ?CHỦ TỊCH|THỦ TƯỚNG|CHỦ TỊCH NƯỚC|ltre=\d)",
)


class _BlockText(HTMLParser):
    """Collect text per HTML block element; skip non-content subtrees."""

    SKIP: typing.ClassVar[frozenset[str]] = frozenset({"script", "style", "head", "title"})
    BLOCK: typing.ClassVar[frozenset[str]] = frozenset(
        {"p", "div", "tr", "td", "br", "li", "h1", "h2", "h3", "h4", "table", "body"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._skip_depth = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in self.BLOCK and self._buf:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self._skip_depth:
            self._buf.append(data)

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            self.lines.append(text)
        self._buf = []


def html_to_lines(html: str) -> list[str]:
    parser = _BlockText()
    parser.feed(html)
    parser.close()
    return parser.lines


def keep(line: str) -> bool:
    if len(line) < 60:  # statutes are long-form prose
        return False
    if _NOISE.search(line):
        return False
    letters = sum(ch.isalpha() for ch in line)
    return letters >= 0.5 * len(line)


def _write_doc(doc: str, out) -> int:
    """Write one document's surviving lines; return how many were written."""
    written = 0
    for raw in html_to_lines(doc):
        line = unicodedata.normalize("NFC", raw).strip()
        if keep(line):
            written += 1
            out.write(line + "\n")
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("parquet", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--limit", type=int, default=0, help="stop after N docs (0 = all)")
    args = ap.parse_args(argv)

    pf = pq.ParquetFile(args.parquet)
    total = kept = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for batch in pf.iter_batches(batch_size=256, columns=["content_html"]):
            col = batch.column(0)
            for i in range(len(col)):
                total += 1
                if args.limit and kept >= args.limit:
                    print(f"docs={total} kept={kept} (limit {args.limit}) -> {args.out}")
                    return 0
                doc = col[i].as_py()
                if isinstance(doc, str):
                    kept += _write_doc(doc, out)
    print(f"docs={total} kept={kept} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
