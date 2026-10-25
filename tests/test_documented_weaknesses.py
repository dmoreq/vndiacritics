"""Pins user-visible weaknesses documented in docs/USAGE.md.

These assert CURRENT behaviour, including the parts that are wrong. The purpose is
to make a change visible: if someone fixes the number-adjacency bug, these tests
fail and the docs must be updated. They are not acceptance criteria for perfection.
"""

import os
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[1] / "vndiacritics" / "data" / "uni.tsv"

if os.environ.get("VNDIACRITICS_REQUIRE_CORPUS") == "1" and not CORPUS.exists():

    def test_corpus_recovered() -> None:
        pytest.fail(
            f"VNDIACRITICS_REQUIRE_CORPUS=1 but corpus is missing at {CORPUS}; run ./scripts/recover_data.sh"
        )

else:
    pytestmark = pytest.mark.skipif(not CORPUS.exists(), reason="corpus not recovered")


@pytest.fixture(scope="module")
def model():
    from vndiacritics.model import Model

    return Model.load()


def test_preserves_case_emoji_url_and_numbers(model):
    """Documented strengths: pass-through of anything that is not a Vietnamese word."""
    assert model.restore("CONG TY TNHH MOT THANH VIEN") == "CÔNG TY TNHH MỘT THÀNH VIÊN"
    assert model.restore("chao ban 😀 rat vui") == "chào bán 😀 rất vui"
    assert (
        model.restore("xem tai https://example.com/tin-tuc")
        == "xem tại https://example.com/tin-tuc"
    )


def test_does_not_damage_foreign_names(model):
    """0 of 44 foreign tokens were mis-restored when measured; keep it that way."""
    out = model.restore("Arsenal va Boeing da ky ket")
    assert "Arsenal" in out and "Boeing" in out


def test_number_adjacency_fixed(model):
    """FIXED (docs/reports/2026-10-25-number-context-fix.md): a numeric token no
    longer corrupts its neighbours.

    The '12' column still scores UNK and severs direct context, but the surviving
    transition now carries n1-confidence (bigram_conf_k=1000): the corpus-typo
    pair 'tróng nằm' (2/53) can no longer outrank 'trong năm' (71,291/2.9M).
    If this test starts failing, the blend regressed -- re-run
    bench/ab_confidence.py and update docs/USAGE.md section 4.1.
    """
    out = model.restore("tang 12.5% trong nam 2025")
    assert out == "tăng 12.5% trong năm 2025", (
        "Number-adjacency fix regressed; re-run bench/ab_confidence.py"
    )


def test_short_utterance_pronoun_known_weakness(model):
    """KNOWN BUG (docs/USAGE.md 4.2): 'ban' becomes 'bán' with no context."""
    assert model.restore("chao ban") == "chào bán"
    # The same word is correct once context exists:
    assert model.restore("cam on ban") == "cảm ơn bạn"
