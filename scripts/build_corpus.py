"""Build restoration and case statistics tables from raw cased text.

The upstream repo only ships a Java n-gram counter (NGramer.java) whose output
is the 2017 corpus; nothing in this repository could rebuild tables from raw
text. This script is the Python replacement. Tokenization mirrors
NGramer.java's so counts stay comparable with the 2017 corpus:

- whitespace-split, punctuation stripped from token edges;
- lowercase fold, then interior disallowed characters DELETED with the
  surviving fragments merged into one key ("kiến-tạo" -> "kiếntạo",
  "abc123" -> "abc"), exactly like NGramer.java's replaceAll -- the bigram
  chain stays intact;
- lines containing both '<' and '>' are skipped (NGramer.java's wiki-markup
  guard);
- empty keys are never emitted.

Divergences from NGramer.java, all deliberate and harmless for the decoder:
NFC normalization first (upstream does none; on NFD text its regex would
strip combining marks and destroy diacritics -- our corpora are normalized);
no "<punct>" placeholder tokens (upstream's tables contain them, but the
restorer in vndiacritics/restore.py can never look a "<punct>" key up: lookup
cores are bounded by alphanumeric characters, so those 174k bigram rows are
dead weight upstream). Punctuation never breaks the bigram chain: adjacency
across a punctuation-only token is preserved, as upstream.

Case statistics (our addition, not in NGramer.java) are classified on the
ORIGINAL cased core, before interior-character merging. A single-letter token
like "V." classifies as ALL-CAPS, never sentence-initial, by construction.

Outputs (into --outdir, sorted keys, deterministic for a given input):
  uni.tsv            key <TAB> count          lowercase syllable counts
  bi.tsv             "a b" <TAB> count        lowercase bigram counts
  case.tsv           key <TAB> lower <TAB> cap <TAB> allcap <TAB> initial
                     cased-type statistics for the truecaser: lowercase
                     appearances, first-letter-capitalized (title case),
                     ALL-CAPS, and title-case-at-sentence-start appearances
  case_bi.tsv        "A b" <TAB> count        bigrams in observed case, counted
                     when the second token is capitalized MID-SENTENCE
                     (proper-noun evidence; a sentence-initial cap carries no
                     information about the token being a proper noun)
  abbreviations.txt  type <TAB> count         ALL-CAPS types, len >= 2

Sentence boundary for "initial": start of line, or after any raw token whose
trailing punctuation ends with . ! ? … (a raw token may carry trailing
quotes/brackets after the period; punctuation-only tokens still update the
boundary). Raw corpora here are line-per-sentence (subtitles, legal text),
so line starts dominate.

Memory guard: when the bigram dict exceeds --prune-at entries, count-1 entries
are dropped. Deterministic for a given input; bounds RAM for web-scale inputs
at the cost of discarding singleton bigrams seen before the prune point.
"""

from __future__ import annotations

import argparse
import unicodedata
from collections import Counter
from pathlib import Path

# ASCII letters plus every Vietnamese lowercase letter (đ included; NFC forms).
_ALLOWED = frozenset(
    "abcdefghijklmnopqrstuvwxyzđàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ"
)
_SENTENCE_END = frozenset(".!?…")
_CLOSERS = "\"')]}>"


class CaseCounts:
    """Mutable per-type case statistics for one corpus build."""

    __slots__ = ("allcap", "cap", "initial", "lower")

    def __init__(self) -> None:
        self.lower = 0
        self.cap = 0
        self.allcap = 0
        self.initial = 0


class CorpusBuilder:
    def __init__(self, prune_at: int = 40_000_000) -> None:
        self.uni: Counter[str] = Counter()
        self.bi: Counter[str] = Counter()
        self.case: dict[str, CaseCounts] = {}
        self.case_bi: Counter[str] = Counter()
        self.abbr: Counter[str] = Counter()
        self._prune_at = prune_at

    def add_line(self, line: str) -> None:
        if "<" in line and ">" in line:
            return
        initial = True
        prev_cased: str | None = None
        prev_key: str | None = None
        for raw in line.split():
            core = unicodedata.normalize("NFC", _core(raw))
            ends = _ends_sentence(raw)
            if not core:
                # Punctuation-only token: it can still close a sentence.
                initial = ends
                continue
            key = fold(core)
            if key is not None:
                self.uni[key] += 1
                self._count_case(key, core, initial)
                if prev_key is not None:
                    self.bi[prev_key + " " + key] += 1
                    if _is_capitalized(core) and not initial:
                        self.case_bi[prev_cased + " " + core] += 1
                prev_cased = core
                prev_key = key
            initial = ends

    def _count_case(self, key: str, core: str, initial: bool) -> None:
        stats = self.case.setdefault(key, CaseCounts())
        if _is_allcap(core):
            stats.allcap += 1
            if len(core) >= 2:
                self.abbr[core] += 1
        elif _is_capitalized(core):
            stats.cap += 1
            if initial:
                stats.initial += 1
        else:
            stats.lower += 1

    def maybe_prune(self) -> None:
        if len(self.bi) > self._prune_at:
            for k in [k for k, v in self.bi.items() if v == 1]:
                del self.bi[k]


def _core(token: str) -> str:
    """Strip punctuation from token edges; return the alphabetic core."""
    i, j = 0, len(token)
    while i < j and not token[i].isalpha():
        i += 1
    while j > i and not token[j - 1].isalpha():
        j -= 1
    return token[i:j]


def fold(token: str) -> str | None:
    """Lowercase fold a cased core into a corpus key, or None when nothing survives.

    Mirrors NGramer.java's replaceAll semantics: lowercase, DELETE every
    character outside the Vietnamese syllable alphabet (digits, hyphens,
    foreign scripts) and merge the surviving fragments into one key
    ("kiến-tạo" -> "kiếntạo", "abc123" -> "abc"). Divergence: NFC-normalize
    first, which upstream does not (upstream destroys diacritics on NFD text).
    """
    token = unicodedata.normalize("NFC", token).lower()
    token = "".join(ch for ch in token if ch in _ALLOWED)
    return token or None


def _is_capitalized(core: str) -> bool:
    return core[0].isupper()


def _is_allcap(core: str) -> bool:
    return core[0].isupper() and core.isupper()


def _ends_sentence(raw: str) -> bool:
    """Whether a raw whitespace token closes a sentence.

    Trailing closing punctuation (quotes, brackets) may sit after the period,
    so strip closers before checking.
    """
    stripped = raw.rstrip(_CLOSERS)
    return bool(stripped) and stripped[-1] in _SENTENCE_END


def build(sources: list[Path], prune_at: int = 40_000_000) -> CorpusBuilder:
    """Stream every source file, counting all tables in one pass."""
    b = CorpusBuilder(prune_at=prune_at)
    for path in iter_files(sources):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                b.add_line(line)
        b.maybe_prune()
    return b


def iter_files(sources: list[Path]) -> list[Path]:
    """Resolve sources to a deterministic sorted list of .txt files."""
    files: list[Path] = []
    for src in sources:
        if src.is_dir():
            files.extend(p for p in sorted(src.rglob("*.txt")) if p.is_file())
        else:
            files.append(src)
    return sorted(set(files))


def write_outputs(b: CorpusBuilder, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "uni.tsv", "w", encoding="utf-8") as fh:
        fh.writelines(f"{k}\t{b.uni[k]}\n" for k in sorted(b.uni))
    with open(outdir / "bi.tsv", "w", encoding="utf-8") as fh:
        fh.writelines(f"{k}\t{b.bi[k]}\n" for k in sorted(b.bi))
    with open(outdir / "case.tsv", "w", encoding="utf-8") as fh:
        for k in sorted(b.case):
            s = b.case[k]
            fh.write(f"{k}\t{s.lower}\t{s.cap}\t{s.allcap}\t{s.initial}\n")
    with open(outdir / "case_bi.tsv", "w", encoding="utf-8") as fh:
        for k in sorted(b.case_bi):
            fh.write(f"{k}\t{b.case_bi[k]}\n")
    with open(outdir / "abbreviations.txt", "w", encoding="utf-8") as fh:
        for k in sorted(b.abbr):
            fh.write(f"{k}\t{b.abbr[k]}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sources", nargs="+", type=Path, help="raw .txt files or dirs")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument(
        "--prune-at",
        type=int,
        default=40_000_000,
        help="prune count-1 bigrams when the dict exceeds this many entries",
    )
    args = ap.parse_args(argv)
    b = build(args.sources, prune_at=args.prune_at)
    write_outputs(b, args.outdir)
    print(
        f"uni={len(b.uni)} bi={len(b.bi)} case={len(b.case)} "
        f"case_bi={len(b.case_bi)} abbr={len(b.abbr)} -> {args.outdir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
