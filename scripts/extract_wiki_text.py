"""Extract plain text lines from a Wikipedia pages-articles multistream dump.

Streams the .bz2 XML, emits one cleaned text line per <text> block, skipping
redirects, non-article namespaces, and markup-heavy boilerplate. Page order
equals dump order, so --every N sampling is deterministic. Sampling keeps the
n-gram build inside a token budget.

Usage:
  python scripts/extract_wiki_text.py DUMP.xml.bz2 OUT.txt [--every N]

Wikipedia text is CC BY-SA 3.0; see CORPORA.md for attribution.
"""

from __future__ import annotations

import argparse
import bz2
import re
from pathlib import Path

_PAGE_RE = re.compile(r"<page>(.*?)</page>", re.DOTALL)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_NS_RE = re.compile(r"<ns>(\d+)</ns>")
_TEXT_RE = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)
_REDIRECT_RE = re.compile(r"<redirect ")

_HEADING = re.compile(r"^=+.*?=+$\n?", re.MULTILINE)
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_LINK_PIPE = re.compile(r"\[\[[^|\]]*\|([^]]*)\]\]")
_LINK = re.compile(r"\[\[([^]]*)\]\]")
_EXT = re.compile(r"https?://\S+")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FILE_NS = re.compile(r"^(Tập tin|File|Hình|Image|Thể loại|Category):", re.IGNORECASE)


def clean_text(raw: str) -> str:
    """Rough wikitext-to-lines cleanup. Keeps prose lines, drops boilerplate."""
    raw = _COMMENT.sub(" ", raw)
    raw = _REF.sub(" ", raw)
    raw = _TAG.sub(" ", raw)
    lines = []
    for line in raw.splitlines():
        line = _FILE_NS.sub("", line)
        if _HEADING.match(line + "\n"):
            continue
        line = _TEMPLATE.sub(" ", line)
        line = _LINK_PIPE.sub(r"\1", line)
        line = _LINK.sub(r"\1", line)
        line = _EXT.sub(" ", line)
        line = re.sub(r"''+", "", line)
        line = re.sub(r"&nbsp;?", " ", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        # Keep prose-looking lines only: enough length, mostly letters.
        if len(line) < 40:
            continue
        if sum(ch.isalpha() for ch in line) < 0.5 * len(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _title_text(page_match: re.Match) -> tuple[str, str] | None:
    """Return (title, raw text) for a complete article page, else None."""
    block = page_match.group(1)
    if _REDIRECT_RE.search(block[:200]):
        return None
    ns = _NS_RE.search(block)
    if ns and ns.group(1) != "0":
        return None
    text = _TEXT_RE.search(block)
    if not text:
        return None
    title = _TITLE_RE.search(block)
    return (title.group(1) if title else ""), text.group(1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--every", type=int, default=1, help="keep every Nth article")
    args = ap.parse_args(argv)

    count = kept = 0
    buffer = ""
    with (
        bz2.open(args.dump, "rt", encoding="utf-8", errors="replace") as fh,
        open(args.out, "w", encoding="utf-8") as out,
    ):
        eof = False
        while not eof:
            chunk = fh.read(1 << 24)
            if not chunk:
                # EOF: process the trailing complete pages once, then stop.
                matches = list(_PAGE_RE.finditer(buffer))
                eof = True
            else:
                buffer += chunk
                matches = list(_PAGE_RE.finditer(buffer))
                if not matches:
                    continue
                # Keep only complete pages; carry the tail into the next chunk.
                buffer = buffer[matches[-1].end() :]
            for m in matches:
                count += 1
                if count % args.every:
                    continue
                page = _title_text(m)
                if page is None:
                    continue
                kept += 1
                out.write(f"# {page[0]}\n")
                out.write(clean_text(page[1]))
                out.write("\n")
    print(f"pages scanned={count} kept={kept} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
