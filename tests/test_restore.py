from vap.index import CandidateIndex
from vap.restore import Restorer


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
