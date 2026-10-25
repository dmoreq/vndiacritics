"""Tests for scripts/build_corpus.py (imported by path; not a package)."""

import importlib.util
import sys
from pathlib import Path

from vndiacritics.data import parse_count_table

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "build_corpus", _ROOT / "scripts" / "build_corpus.py"
)
bc = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("build_corpus", bc)
_SPEC.loader.exec_module(bc)


def make_builder():
    return bc.CorpusBuilder(prune_at=10)


def test_fold_mirrors_ngramer():
    assert bc.fold("Đồng") == "đồng"
    assert bc.fold("12.5") is None  # digit-only cores dropped, as upstream
    assert bc.fold("machine") == "machine"  # ASCII passes
    assert bc.fold("тхань") is None  # foreign script dropped
    assert bc.fold("to\u0302i") == "tôi"  # NFD "tôi" composes via NFC
    assert bc.fold("to\u0302\u0301i") == "tối"  # NFD "tối" (sắc) composes via NFC
    assert bc.fold("to\u0302\u0309i") == "t\u1ed5i"  # NFD "tổi" (hỏi) composes via NFC


def test_core_strips_edges_only():
    assert bc._core('"kết"') == "kết"
    assert bc._core("(được)") == "được"
    # Digits are not alphabetic: a digit-only token has no core and is dropped
    # at the core stage (upstream's regex drops it at the token stage).
    assert bc._core("12.5%") == ""
    assert bc._core("--") == ""
    assert bc._core('thúc."') == "thúc"


def test_ends_sentence_handles_closers():
    assert bc._ends_sentence("thúc.") is True
    assert bc._ends_sentence('thúc."') is True
    assert bc._ends_sentence("thúc") is False
    assert bc._ends_sentence("12.5%") is False


def test_unigram_and_bigram_tables(tmp_path):
    b = make_builder()
    b.add_line("Tôi yêu Việt Nam\n")
    b.add_line("tôi yêu em\n")
    assert b.uni["tôi"] == 2 and b.uni["yêu"] == 2 and b.uni["việt"] == 1
    assert b.bi["tôi yêu"] == 2 and b.bi["yêu việt"] == 1 and b.bi["yêu em"] == 1


def test_case_statistics():
    b = make_builder()
    b.add_line("Hà Nội đẹp. tôi ở Hà Nội.\n")
    # hà: sentence-initial cap 1 + mid-sentence cap 1 ; nội: mid-sentence cap 2
    s_ha = b.case["hà"]
    assert (s_ha.cap, s_ha.allcap, s_ha.initial) == (2, 0, 1)
    assert b.case["nội"].cap == 2
    assert b.case["tôi"].lower == 1


def test_allcap_goes_to_abbreviations():
    b = make_builder()
    b.add_line("Ngân hàng TMCP DNA Việt Nam\n")
    assert b.case["dna"].allcap == 1
    assert b.abbr["DNA"] == 1
    assert b.case["tmcp"].allcap == 1 and b.abbr["TMCP"] == 1


def test_case_bi_requires_mid_sentence_capitalization():
    b = make_builder()
    b.add_line("Bộ Tài chính báo cáo. tôi ở Hà Nội.\n")
    # 'Tài' mid-sentence cap -> pair counted with observed case:
    assert b.case_bi["Bộ Tài"] == 1
    # 'Nội' mid-sentence cap -> pair counted:
    assert b.case_bi["Hà Nội"] == 1
    # A pair whose second token is sentence-initial carries no proper-noun
    # evidence and must NOT be counted: none exists here beyond the above.


def test_sentence_boundary_after_number_with_period():
    b = make_builder()
    b.add_line("tăng 12.5% trong năm. (Năm 2025)\n")
    s_nam = b.case["năm"]
    # 'năm.' (lowercase, mid-sentence: '%' is not a sentence ender) -> lower 1;
    # '(Năm' follows 'năm.' which closes a sentence -> cap 1, initial 1:
    assert (s_nam.lower, s_nam.cap, s_nam.initial) == (1, 1, 1)


def test_determinism(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("Tôi yêu Việt Nam\nViệt Nam đẹp\n", encoding="utf-8")
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    bc.main([str(src), "--outdir", str(out1)])
    bc.main([str(src), "--outdir", str(out2)])
    for name in ("uni.tsv", "bi.tsv", "case.tsv", "case_bi.tsv", "abbreviations.txt"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()


def test_outputs_load_with_model_loader(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("tôi yêu việt nam\n", encoding="utf-8")
    out = tmp_path / "o"
    bc.main([str(src), "--outdir", str(out)])
    uni = parse_count_table(out / "uni.tsv")
    bi = parse_count_table(out / "bi.tsv")
    assert uni == {"tôi": 1, "yêu": 1, "việt": 1, "nam": 1}
    assert bi == {"tôi yêu": 1, "yêu việt": 1, "việt nam": 1}


def test_prune_drops_singletons_only():
    b = bc.CorpusBuilder(prune_at=3)
    b.add_line("a b c d a b\n")  # 4 bigram types; 'a b' x2, rest singletons
    assert b.uni["a"] == 2
    b.maybe_prune()
    assert "a b" in b.bi and b.bi["a b"] == 2
    assert "b c" not in b.bi and "c d" not in b.bi and "d a" not in b.bi


def test_iter_files_deterministic_order(tmp_path):
    (tmp_path / "b.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("y\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("z\n", encoding="utf-8")
    files = bc.iter_files([sub, tmp_path])
    names = [f.name for f in files]
    assert names == ["a.txt", "b.txt", "c.txt"]
