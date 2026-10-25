from vndiacritics.index import CandidateIndex


def test_candidates_for_ambiguous_key():
    idx = CandidateIndex({"con": 10, "còn": 5, "côn": 3, "other": 1})
    # sorted() is codepoint order: ò (U+00F2) sorts before ô (U+00F4).
    assert sorted(idx.candidates("con")) == ["con", "còn", "côn"]


def test_candidates_case_insensitive():
    idx = CandidateIndex({"con": 10, "còn": 5})
    assert sorted(idx.candidates("CON")) == ["con", "còn"]


def test_unknown_returns_empty():
    idx = CandidateIndex({"con": 10})
    assert idx.candidates("zzz") == []
