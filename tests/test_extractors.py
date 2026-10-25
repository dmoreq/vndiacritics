"""Tests for the WS2 extraction scripts (pure functions, imported by path)."""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


opus = _load("extract_opus_vi")
wiki = _load("extract_wiki_text")


def test_opus_keep_filters_credits_and_noise():
    assert opus.keep("Đúng rồi, anh cứ làm như thế đi em nói thật.") is True
    assert opus.keep("Sync by xsubteam") is False  # credit
    assert opus.keep("Phụ đề bởi opensubtitles.org") is False
    assert opus.keep("OK") is False  # too short
    assert opus.keep("abcdefgh ijklmnop qrstuv") is False  # no Vietnamese letter
    assert opus.keep("123456789012345678901234567890") is False  # no letters


def test_opus_keep_allows_allcaps_dialogue():
    # ALL-CAPS Vietnamese dialogue is real subtitle content, not a credit:
    assert opus.keep("TẠI SAO ANH KHÔNG NÓI SỚM VỚI EM?") is True


def test_wiki_clean_text_strips_markup():
    raw = (
        "{{infobox}}\n"
        "== Lịch sử ==\n"
        "<ref>nguồn</ref>\n"
        "Hà Nội [[Thủ đô|là thủ đô]] của Việt Nam từ thế kỷ XI, với [[Văn Miếu]] "
        "xây dựng năm 1070 (https://example.com).\n"
    )
    out = wiki.clean_text(raw)
    assert "infobox" not in out and "Lịch sử" not in out and "ref" not in out
    assert "Hà Nội là thủ đô của Việt Nam" in out and "Văn Miếu" in out
    assert "https://" not in out


def test_wiki_clean_text_drops_short_and_nonprose():
    assert wiki.clean_text("xem thêm\n") == ""
    assert wiki.clean_text("1234 5678 9012 3456 7890 1234\n") == ""


def test_wiki_title_text_skips_redirect_and_ns():
    article = "<page><title>Hà Nội</title><ns>0</ns><text>thủ đô của Việt Nam</text></page>"
    m = wiki._PAGE_RE.search(article)
    assert wiki._title_text(m) == ("Hà Nội", "thủ đô của Việt Nam")
    redirect = '<page><title>X</title><ns>0</ns><redirect title="Y"/><text/></page>'
    assert wiki._title_text(wiki._PAGE_RE.search(redirect)) is None
    talk = "<page><title>Talk:X</title><ns>1</ns><text>thảo luận dài đủ tiêu chuẩn</text></page>"
    assert wiki._title_text(wiki._PAGE_RE.search(talk)) is None
