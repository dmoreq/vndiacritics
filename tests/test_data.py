from pathlib import Path

import pytest

from vap.data import load_unigram, parse_count_table


def test_parse_count_table(tmp_path):
    p = tmp_path / "t.tsv"
    p.write_text("công\t100\nđồng\t50\n", encoding="utf-8")
    assert parse_count_table(p) == {"công": 100, "đồng": 50}


def test_parse_count_table_uses_last_separator(tmp_path):
    """Bigram keys contain a space; split on the LAST separator only."""
    p = tmp_path / "t.tsv"
    p.write_text("công ty\t66763\n", encoding="utf-8")
    assert parse_count_table(p) == {"công ty": 66763}


def test_parse_count_table_skips_bad_rows(tmp_path):
    p = tmp_path / "t.tsv"
    p.write_text("ok\t5\nbad\tnotanint\n\tnull\n", encoding="utf-8")
    assert parse_count_table(p) == {"ok": 5}


def test_parse_count_table_handles_crlf(tmp_path):
    p = tmp_path / "t.tsv"
    p.write_bytes("ơi\t7\r\n".encode())
    assert parse_count_table(p) == {"ơi": 7}


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "vap" / "data" / "uni.tsv").exists(),
    reason="corpus not recovered",
)
def test_load_unigram_real_corpus():
    g = load_unigram()
    # 216448 lines in the file, but the first is "\t587" (empty key) which is
    # correctly rejected, leaving 216447 distinct keys.
    assert len(g) == 216447
    assert g["công"] > 1_000_000
