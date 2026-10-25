"""Tests for the statistical truecaser (vndiacritics/truecase.py)."""

import pytest

from vndiacritics.truecase import CaseStats, Truecaser, load_case_tables


def make_stats(**overrides) -> CaseStats:
    s = CaseStats()
    # A curated mini-corpus, hand-counted. Sentence-initial title counts live
    # in `initial`; ratio-vs-lowercase decides the initial position.
    s.lower.update(
        {
            "tôi": 100000,
            "ở": 90000,
            "hà": 100,
            "nội": 50000,
            "và": 2000000,
            "đẹp": 100000,
            "thật": 200000,
            "nguyễn": 0,
            "van": 50,
            "dna": 30,
            "bộ": 8000,
            "tài": 4000,
            "chính": 9000,
        }
    )
    s.cap.update(
        {
            "tôi": 800,
            "ở": 50,
            "hà": 900,
            "nội": 100,
            "và": 5,
            "đẹp": 700,
            "thật": 900,
            "nguyễn": 300,
            "van": 2,
            "dna": 10,
            "bộ": 5000,
            "tài": 6000,
            "chính": 2000,
        }
    )
    s.allcap.update({"dna": 5000, "tôi": 2, "hà": 1, "nội": 1})
    s.initial.update({"hà": 300, "nguyễn": 250, "bộ": 4000, "tài": 5000, "tôi": 60000})
    s.bigrams.update({"Hà Nội": 8000, "Bộ Tài": 4500, "Tài chính": 1800})
    s.gazetteer = {"Hà Nội", "Nguyễn Văn An", "Bộ Tài chính"}
    for k, v in overrides.items():
        getattr(s, k).update(v)
    return s


def tc(stats=None):
    return Truecaser(stats or make_stats())


def test_proper_noun_via_bigram_continuation():
    """'nội' is usually lowercase but follows title 'Hà' inside an attested name.

    'Tôi' at line start becomes 'Tôi': Vietnamese orthography capitalizes a
    sentence-initial pronoun (see test_sentence_initial_pronoun_capitalized).
    """
    out = tc().correct(["tôi", "ở", "hà", "nội."], ["tôi", "ở", "hà", "nội"])
    assert out == ["Tôi", "ở", "Hà", "Nội"]


def test_ministry_name_chain():
    out = tc().correct(["bộ", "tài", "chính."], ["bộ", "tài", "chính"])
    assert out == ["Bộ", "Tài", "Chính"]


def test_function_word_stays_lowercase_at_sentence_start():
    out = tc().correct(["và", "tôi."], ["và", "tôi"])
    assert out[0] == "và" and out[1] == "tôi"


def test_sentence_initial_proper_noun_capitalized():
    out = tc().correct(["nguyễn", "van", "an"], ["nguyễn", "van", "an"])
    assert out[0] == "Nguyễn" and out[1] == "van"  # 'van' is a lowercase particle


def test_sentence_initial_pronoun_capitalized():
    """Vietnamese orthography capitalizes 'Tôi' at sentence start."""
    out = tc().correct(["Tôi", "ở", "đây"], ["tôi", "ở", "đây"])
    assert out[0] == "Tôi"


def test_attested_acronym_from_lowercase_input():
    out = tc().correct(["thuộc", "dna"], ["thuộc", "dna"])
    assert out[1] == "DNA"


def test_attested_acronym_input_allcaps_honored():
    out = tc().correct(["thuộc", "DNA"], ["thuộc", "dna"])
    assert out[1] == "DNA"


def test_shouting_is_de_capitalized_by_stats():
    out = tc().correct(["THẬT", "ĐẸP!"], ["thật", "đẹp"])
    assert out[0] == "thật" and out[1] == "đẹp"


def test_oov_token_gets_positional_copy():
    """Unknown words must not gain or lose case: None -> _reapply_case path."""
    t = tc()
    assert t._decide("samsung", "samsung", initial=False, prev_cased=None) is None
    assert t._decide("SAMSUNG", "samsung", initial=True, prev_cased=None) is None


def test_punctuation_only_token_is_none():
    t = tc()
    assert t.correct(["."], [""]) == [None]


def test_load_case_tables_roundtrip(tmp_path):
    d = tmp_path / "corpus"
    d.mkdir()
    (d / "case.tsv").write_text(
        "tôi\t100000\t800\t2\t5000\nhà\t100\t900\t1\t300\n", encoding="utf-8"
    )
    (d / "case_bi.tsv").write_text("Hà Nội\t8000\n", encoding="utf-8")
    (d / "names_places.txt").write_text("Hà Nội\n", encoding="utf-8")
    s = load_case_tables(d)
    assert s.lower["tôi"] == 100000 and s.cap["hà"] == 900
    assert s.bigrams["Hà Nội"] == 8000 and "Hà Nội" in s.gazetteer


def test_load_case_tables_requires_case_tsv(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_case_tables(tmp_path)
