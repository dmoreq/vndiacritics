"""Statistical truecaser: decides letter case for restored Vietnamese tokens.

Moses-style (Lita et al., ACL 2003), adapted to Vietnamese: per-type case
frequencies from a cased corpus, sentence-initial handling, capitalized-bigram
continuation evidence, and gazetteer reinforcement. Runs AFTER diacritic
restoration -- the corpus tables live over lowercase syllables with cased
appearance counts (see scripts/build_corpus.py case.tsv / case_bi.tsv).

Decision per token, given its lowercase form and the stats:

- ALL-CAPS attested (`allcap` > lower + cap): the type is an acronym; keep the
  input's own casing untouched.
- Otherwise argmax over case variants weighted by counts:
  mid-sentence  { lower: lower_count, title: cap_count + bigram_bonus,
                  allcap: allcap_count }
  sentence-init { lower: lower_count,
                  title: (initial_count + cap_count + bigram_bonus)
                         * INITIAL_FOLD,
                  allcap: allcap_count }
  The INITIAL_FOLD multiplier sits on the TITLE side and compares RATIOS:
  Vietnamese orthography capitalizes a sentence-initial content word
  ("Bộ", "Tôi") but keeps function words lowercase ("và", "của"). A type
  whose title appearances are a vanishing fraction of its lower appearances
  is a function word; a type with any meaningful capitalized usage is not.
- bigram_bonus: if the PREVIOUS chosen form is title case and
  (prev + " " + TITLE) is observed in case_bi.tsv, the title variant gains
  CONTINUATION_WEIGHT * pair_count. This is what turns "hà nội" into
  "Hà Nội" even when "nội" is usually lowercase.
- No stats for the type (OOV): leave the token as the restorer produced it
  (positional copy). Unknown words must not gain or lose case, with one
  exception: a bare ASCII letter is uppercased (contract labels "Bên A").

Input tokens that are already ALL-CAPS and attested stay ALL-CAPS; ALL-CAPS
input for an unattested-uppercase type (shouting) is decided by the stats
like any other token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Measured on bench/data/cased_eval_v0.txt (2026-10-25, auto-K): 88.89% at 8,
# 90.22% at 32, 90.38% at 64, saturating at 64. Below 64, sentence-initial
# content words whose lowercase usage dominates ("Bên", "Ngày") lose their
# capital. Shipped-config number of record: 90.22% (K=1000 via model.json).
INITIAL_FOLD = 64
CONTINUATION_WEIGHT = 10
_SENTENCE_END = frozenset(".!?…")
_CLOSERS = "\"')]}>"

# The gazetteer files are fetched by scripts/fetch_corpus_v2.sh; absence is
# normal and just disables the gazetteer bonus.
GAZETTEER_FILES = ("names_persons.txt", "names_places.txt")


@dataclass
class CaseStats:
    """Parsed case.tsv / case_bi.tsv tables, keyed by lowercase form."""

    lower: dict[str, int] = field(default_factory=dict)
    cap: dict[str, int] = field(default_factory=dict)
    allcap: dict[str, int] = field(default_factory=dict)
    initial: dict[str, int] = field(default_factory=dict)
    bigrams: dict[str, int] = field(default_factory=dict)
    gazetteer: set[str] = field(default_factory=set)


def _read_count_rows(path: Path, columns: int):
    """Yield (key, counts...) for each well-formed `key<TAB>count...` row."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != columns:
                continue
            try:
                yield parts[0], tuple(int(v) for v in parts[1:])
            except ValueError:
                continue


def _load_gazetteer(directory: Path, stats: CaseStats) -> None:
    for name in GAZETTEER_FILES:
        gz = Path(directory) / name
        if not gz.exists():
            continue
        with open(gz, encoding="utf-8") as fh:
            for line in fh:
                name_form = line.strip()
                if name_form:
                    stats.gazetteer.add(name_form)


def load_case_tables(directory: Path) -> CaseStats:
    """Load truecaser tables from a corpus directory. Raises if case.tsv is absent."""
    path = Path(directory) / "case.tsv"
    if not path.exists():
        raise FileNotFoundError(
            f"case statistics not found at {path}; corpus v2 is required for "
            "case='correct' (build with scripts/fetch_corpus_v2.sh)"
        )
    stats = CaseStats()
    for key, (lo, ca, ac, ini) in _read_count_rows(path, 5):
        stats.lower[key], stats.cap[key], stats.allcap[key], stats.initial[key] = lo, ca, ac, ini
    bi_path = Path(directory) / "case_bi.tsv"
    if bi_path.exists():
        for key, (count,) in _read_count_rows(bi_path, 2):
            stats.bigrams[key] = count
    _load_gazetteer(Path(directory), stats)
    return stats


def _ends_sentence(raw: str) -> bool:
    stripped = raw.rstrip(_CLOSERS)
    return bool(stripped) and stripped[-1] in _SENTENCE_END


def _is_allcaps(text: str) -> bool:
    return any(ch.isalpha() for ch in text) and text.isupper()


def _title(form: str) -> str:
    return form[:1].upper() + form[1:]


class Truecaser:
    def __init__(self, stats: CaseStats) -> None:
        self._s = stats

    def correct(self, tokens: list[str], words: list[str]) -> list[str]:
        """Decide case for restored `words` given the original raw `tokens`.

        Both lists are aligned. `tokens` are the whitespace tokens of the input
        (punctuation attached); `words` are the chosen lowercase restorations.
        Returns the cased words. Sentence boundaries are derived from `tokens`.
        """
        out: list[str] = []
        initial = True
        prev_cased: str | None = None
        for raw, word in zip(tokens, words):
            core = _strip_edges(raw)
            decided = self._decide(core, word, initial, prev_cased)
            out.append(decided)
            if decided is not None:
                prev_cased = decided
            initial = _ends_sentence(raw)
        return out

    def _continuation_bonus(self, prev_cased: str | None, word: str) -> int:
        """Capitalized-bigram + gazetteer evidence for `word` after `prev_cased`."""
        if prev_cased is None or not prev_cased[:1].isupper():
            return 0
        s = self._s
        # case_bi.tsv stores the pair as OBSERVED: the second word may be
        # written lowercase inside the name ("Tài chính") or capitalized
        # ("Hà Nội"), so look up both forms.
        pair = s.bigrams.get(prev_cased + " " + word, 0) + s.bigrams.get(
            prev_cased + " " + _title(word), 0
        )
        bonus = 0
        if pair:
            bonus += CONTINUATION_WEIGHT * pair
        if _title(word) in s.gazetteer:
            # Fires even without an attested pair: single-token gazetteer names.
            bonus += CONTINUATION_WEIGHT * (pair + 1)
        return bonus

    def _decide(self, core: str, word: str, initial: bool, prev_cased: str | None) -> str | None:
        if not core:
            return None  # punctuation-only token: nothing to decide
        s = self._s
        lower_count = s.lower.get(word, 0)
        cap_count = s.cap.get(word, 0)
        # The builder merges interior non-letter characters ("USD/VND" folds to
        # key "usdvnd"), so check the folded key too for acronym attestations.
        allcap_count = s.allcap.get(word, 0) or s.allcap.get(_folded(word), 0)
        if lower_count + cap_count + allcap_count == 0:
            # A bare ASCII letter (contract labels "Bên A", option lists) is
            # conventionally uppercase; leave other OOV words untouched.
            if len(core) == 1 and core.isascii() and core.isalpha():
                return word.upper()
            return None  # OOV: positional copy, never invent case
        if _is_allcaps(core) and allcap_count > lower_count + cap_count:
            return word.upper()  # attested acronym: honor the input's casing
        bonus = self._continuation_bonus(prev_cased, word)
        title_count = cap_count + (s.initial.get(word, 0) if initial else 0)
        # At sentence start the ratio compares against INITIAL_FOLD (module doc).
        title_score = (title_count + bonus) * (INITIAL_FOLD if initial else 1)
        candidates = {"lower": lower_count, "title": title_score, "allcap": allcap_count}
        best = max(candidates, key=candidates.get)
        if best == "title":
            return _title(word)
        if best == "allcap":
            return word.upper()
        return word


def _strip_edges(token: str) -> str:
    i, j = 0, len(token)
    while i < j and not token[i].isalpha():
        i += 1
    while j > i and not token[j - 1].isalpha():
        j -= 1
    return token[i:j]


def _folded(word: str) -> str:
    """Reproduce build_corpus.fold on a runtime word: keep Vietnamese letters."""
    return "".join(ch for ch in word.lower() if ch.isalpha())
