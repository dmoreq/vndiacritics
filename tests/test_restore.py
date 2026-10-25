import pytest

from vndiacritics.index import CandidateIndex
from vndiacritics.restore import Restorer


def make_restorer(uni, bi):
    return Restorer(uni, CandidateIndex(uni), bi)


def test_single_word_picks_most_common():
    r = make_restorer({"con": 10, "còn": 99}, {})
    assert r.restore("con") == "còn"


def test_context_overrides_unigram():
    """'còn' is more common alone, but 'công ty' is a far stronger bigram."""
    uni = {"công": 1000, "ty": 500, "con": 10, "còn": 900}
    bi = {"công ty": 8000, "công còn": 1, "công con": 1}
    r = make_restorer(uni, bi)
    assert r.restore("cong con") == "công con"


def test_known_sentence():
    uni = {"tôi": 500, "toi": 1, "yêu": 400, "yeu": 1, "em": 900}
    bi = {"tôi yêu": 300, "yêu em": 250}
    r = make_restorer(uni, bi)
    assert r.restore("toi yeu em") == "tôi yêu em"


def test_case_preserved_positionally():
    uni = {"hà": 500, "nội": 400, "ha": 1, "noi": 1}
    bi = {"hà nội": 900}
    r = make_restorer(uni, bi)
    assert r.restore("Ha Noi") == "Hà Nội"


def test_unknown_token_passes_through():
    r = make_restorer({"con": 10}, {})
    assert r.restore("zzz") == "zzz"


def test_empty_input():
    r = make_restorer({"con": 10}, {})
    assert r.restore("") == ""


def test_token_count_never_changes():
    """A restorer must never add or drop tokens."""
    uni = {"con": 10, "còn": 5, "là": 9}
    r = make_restorer(uni, {"con là": 3})
    src = "con la"
    assert len(r.restore(src).split()) == len(src.split())


def test_punctuation_does_not_block_restoration():
    """Corpus keys are bare syllables; 'đồng.' must still resolve to 'đồng.'."""
    uni = {"đồng": 500, "dong": 1}
    r = make_restorer(uni, {})
    assert r.restore("dong.") == "đồng."
    assert r.restore("(dong)") == "(đồng)"


def test_punctuation_preserved_exactly():
    uni = {"tôi": 500, "toi": 1}
    r = make_restorer(uni, {})
    assert r.restore('toi,"') == 'tôi,"'


def test_leading_capital_preserved_with_punctuation():
    uni = {"đồng": 500, "dong": 1}
    r = make_restorer(uni, {})
    assert r.restore("Dong.") == "Đồng."


def test_punctuation_only_token_is_not_duplicated():
    r = make_restorer({"tôi": 500, "toi": 1, "yêu": 400, "yeu": 1}, {})
    assert r.restore("toi ... yeu") == "tôi ... yêu"
    assert r.restore("toi !!! yeu") == "tôi !!! yêu"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("TOI  YEU", "TÔI  YÊU"),
        ("TOI\tYEU", "TÔI\tYÊU"),
        ("  TOI YEU  ", "  TÔI YÊU  "),
        ("TOI\nYEU", "TÔI\nYÊU"),
    ],
)
def test_preserves_whitespace_and_token_case(source, expected):
    r = make_restorer({"tôi": 500, "toi": 1, "yêu": 400, "yeu": 1}, {})
    assert r.restore(source) == expected


@pytest.mark.parametrize("limit", [0, -1])
def test_rejects_nonpositive_candidate_limit(limit):
    uni = {"tôi": 500, "toi": 1}
    with pytest.raises(ValueError, match="max_candidates must be positive"):
        Restorer(uni, CandidateIndex(uni), {}, max_candidates=limit)


@pytest.mark.parametrize("limit", [1, None])
def test_accepts_positive_or_unlimited_candidate_limit(limit):
    uni = {"tôi": 500, "toi": 1}
    r = Restorer(uni, CandidateIndex(uni), {}, max_candidates=limit)
    assert r.restore("toi") == "tôi"


def test_low_count_candidates_do_not_walk_the_bigram_table():
    """A below-threshold right-hand candidate must not cause a trie lookup.

    Isolates the skip only: `toi` has count 1, so no `toi <something>` key may be
    requested. The chosen form is deliberately not asserted -- the first-column
    decision is governed by the unigram prior, which is out of scope here.
    """
    uni = {"tôi": 50_000, "toi": 1, "yêu": 50_000, "yeu": 1}
    bi = {"tôi yêu": 9_000, "toi yêu": 900_000}
    calls = []

    class CountingBi(dict):
        def get(self, key, default=0):
            calls.append(key)
            return super().get(key, default)

    # Threshold set explicitly: it is scaled from vocabulary size by default, and a
    # 4-word toy table yields 0, which would disable the skip under test.
    r = Restorer(
        uni,
        CandidateIndex(uni),
        CountingBi(bi),
        bigram_size=2,
        bigram_total=909_000,
        bigram_skip_below=20,
    )
    r.restore("toi yeu")
    assert calls, "expected the high-count candidate to still be looked up"
    assert not any(k.startswith("toi ") for k in calls), calls


def test_threshold_zero_disables_the_skip():
    """With the threshold off, every pair is looked up."""

    class CountingBi(dict):
        calls = 0

        def get(self, key, default=0):
            CountingBi.calls += 1
            return super().get(key, default)

    uni = {"tôi": 50_000, "toi": 1}
    bi = CountingBi({"toi toi": 5})
    r = Restorer(
        uni,
        CandidateIndex(uni),
        bi,
        bigram_size=1,
        bigram_total=5,
        bigram_skip_below=0,
    )
    r.restore("toi toi")
    assert CountingBi.calls > 0
