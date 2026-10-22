from vap.index import CandidateIndex


def test_candidates_for_ambiguous_key():
    idx = CandidateIndex({"con": 10, "còn": 5, "côn": 3, "other": 1})
    assert sorted(idx.candidates("con")) == ["con", "côn", "còn"]


def test_candidates_case_insensitive():
    idx = CandidateIndex({"con": 10, "còn": 5})
    assert sorted(idx.candidates("CON")) == ["con", "còn"]


def test_unknown_returns_empty():
    idx = CandidateIndex({"con": 10})
    assert idx.candidates("zzz") == []


def test_best_returns_highest_count():
    idx = CandidateIndex({"con": 10, "còn": 99})
    assert idx.best("con") == "còn"
