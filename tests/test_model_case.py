"""Integration: Model.load picks up case.tsv and case='correct' works end to end."""

import pytest

from vndiacritics.model import Model


@pytest.fixture()
def cased_corpus_dir(tmp_path):
    d = tmp_path / "corpus"
    d.mkdir()
    # Minimal restoration tables (lowercase, like the real ones).
    (d / "uni.tsv").write_text(
        "tôi\t100000\nở\t90000\nhà\t100\nnội\t50000\nvà\t2000000\nđẹp\t100000\n",
        encoding="utf-8",
    )
    (d / "bi.tsv").write_text(
        "tôi ở\t50000\nở hà\t900\nhà nội\t8000\nvà đẹp\t70000\n",
        encoding="utf-8",
    )
    # Case statistics: 'hà' mostly capitalized, 'nội' mostly lowercase but
    # 'Hà Nội' attested as a capitalized pair, 'và' a function word.
    (d / "case.tsv").write_text(
        "tôi\t100000\t800\t2\t60000\n"
        "ở\t90000\t50\t0\t0\n"
        "hà\t100\t900\t1\t300\n"
        "nội\t50000\t100\t1\t0\n"
        "và\t2000000\t5\t0\t0\n"
        "đẹp\t100000\t700\t0\t300\n",
        encoding="utf-8",
    )
    (d / "case_bi.tsv").write_text("Hà Nội\t8000\n", encoding="utf-8")
    return d


def test_model_load_without_case_tsv_rejects_correct(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "uni.tsv").write_text("tôi\t1\n", encoding="utf-8")
    (d / "bi.tsv").write_text("tôi ở\t1\nở\t1\n", encoding="utf-8")
    m = Model.load(d)
    with pytest.raises(ValueError, match="case statistics"):
        m.restore("toi o", case="correct")


def test_restore_correct_recovers_case(cased_corpus_dir):
    m = Model.load(cased_corpus_dir)
    out = m.restore("toi o ha noi", case="correct")
    assert out == "Tôi ở Hà Nội"


def test_restore_default_is_preserve(cased_corpus_dir):
    m = Model.load(cased_corpus_dir)
    assert m.restore("toi o ha noi") == "tôi ở hà nội"
    assert m.restore("Toi O Ha Noi", case="preserve") == "Tôi Ở Hà Nội"


def test_restore_rejects_unknown_mode(cased_corpus_dir):
    m = Model.load(cased_corpus_dir)
    with pytest.raises(ValueError, match="preserve"):
        m.restore("toi", case="auto")


def test_truecaser_is_lazy_and_cached():
    """case="preserve" never builds the case tables; "correct" builds once."""
    from vndiacritics.index import CandidateIndex
    from vndiacritics.restore import Restorer
    from vndiacritics.truecase import CaseStats, Truecaser

    uni = {"tôi": 100000, "ở": 90000, "hà": 100, "nội": 50000, "và": 2000000}
    bi = {"tôi ở": 50000, "ở hà": 900, "hà nội": 8000}
    builds = []

    def factory() -> Truecaser:
        builds.append(1)
        s = CaseStats()
        s.lower.update({"tôi": 100000, "ở": 90000, "hà": 100, "nội": 50000})
        s.cap.update({"tôi": 800, "ở": 50, "hà": 900, "nội": 100})
        s.initial.update({"tôi": 60000})
        s.bigrams.update({"Hà Nội": 8000})
        return Truecaser(s)

    r = Restorer(uni, CandidateIndex(uni), bi, bigram_conf_k=0, truecaser_factory=factory)
    assert builds == []
    assert r.restore("toi o ha noi") == "tôi ở hà nội"
    assert builds == []
    assert r.restore("toi o ha noi", case="correct") == "Tôi ở Hà Nội"
    assert builds == [1]
    r.restore("toi o ha noi", case="correct")
    assert builds == [1]  # cached: no second build
