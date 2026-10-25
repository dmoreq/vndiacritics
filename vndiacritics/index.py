"""Maps an accent-stripped syllable to every accented form seen in the corpus."""

from __future__ import annotations

from collections import defaultdict

from vndiacritics.normalize import strip_accent


class CandidateIndex:
    """Build once at load time; lookups are O(1).

    Regenerating accent variants per token (per-character group expansion) costs a
    large share of decode time. Precomputing the map removes that entirely.
    """

    __slots__ = ("_forms", "_unigram")

    def __init__(self, unigram: dict[str, int]) -> None:
        self._unigram = unigram
        forms: defaultdict[str, list[str]] = defaultdict(list)
        for form in unigram:
            forms[strip_accent(form)].append(form)
        self._forms = dict(forms)

    def candidates(self, token: str) -> list[str]:
        return self._forms.get(strip_accent(token), [])
