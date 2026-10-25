"""Accuracy gates. Two tokenisations are pinned because they answer different questions:

- `split_sentences` (normalise then split): the package's own pipeline, 8995 tokens.
- bare line split: the reference measurement's pipeline, 9085 tokens.

Both must clear the threshold; a change that helps one and hurts the other is a bug,
not a gain.
"""

import os
from pathlib import Path

import pytest

# Anchor to the repo root so the gates run no matter where pytest is invoked from.
CORPUS = Path(__file__).resolve().parents[1] / "vap" / "data" / "uni.tsv"

# CI sets VAP_REQUIRE_CORPUS=1 so a missing corpus fails the run instead of
# silently skipping the most valuable tests. Locally, absence just skips.
if os.environ.get("VAP_REQUIRE_CORPUS") == "1" and not CORPUS.exists():

    def test_corpus_recovered() -> None:
        pytest.fail(
            f"VAP_REQUIRE_CORPUS=1 but corpus is missing at {CORPUS}; run ./scripts/recover_data.sh"
        )

else:
    pytestmark = pytest.mark.skipif(not CORPUS.exists(), reason="corpus not recovered")

ROOT = Path(__file__).resolve().parents[1]
IN_DOMAIN = ROOT / "vap" / "data" / "in_domain.txt"
OUT_DOMAIN = ROOT / "bench" / "data" / "diacritic_eval_v0.txt"


@pytest.fixture(scope="module")
def model():
    from vap.model import Model

    return Model.load()


def _grade_split(model, gold_path):
    from vap.eval import score, split_sentences
    from vap.normalize import nfc, strip_accent_keep_case

    gold = [nfc(s) for s in split_sentences(Path(gold_path).read_text(encoding="utf-8"))]
    pred = [model.restore(strip_accent_keep_case(g)) for g in gold]
    return score(gold, pred)


def _grade_lines(model, gold_path):
    """Reference pipeline: split on newlines, no punctuation normalisation."""
    from vap.eval import score
    from vap.normalize import nfc, strip_accent_keep_case

    lines = [
        nfc(s.strip())
        for s in Path(gold_path).read_text(encoding="utf-8").split("\n")
        if s.strip() and not s.strip().startswith("#")
    ]
    pred = [model.restore(strip_accent_keep_case(g)) for g in lines]
    return score(lines, pred)


def test_in_domain_split_pipeline(model):
    r = _grade_split(model, IN_DOMAIN)
    assert r.skipped == 0
    assert r.total == 8995
    assert r.accuracy >= 0.959  # measured 96.01%


def test_in_domain_reference_pipeline(model):
    """Reference corpus, line-split: 95.02% (8633/9085)."""
    r = _grade_lines(model, IN_DOMAIN)
    assert r.skipped == 0
    assert r.total == 9085
    assert r.accuracy >= 0.957  # measured 95.98%


def test_out_of_domain_split_pipeline(model):
    r = _grade_split(model, OUT_DOMAIN)
    assert r.skipped == 0
    assert r.accuracy >= 0.945  # measured 95.24%


def test_out_of_domain_reference_pipeline(model):
    """Line-split keeps punctuation attached, which is the harsher case: 94.34%."""
    r = _grade_lines(model, OUT_DOMAIN)
    assert r.skipped == 0
    assert r.accuracy >= 0.935
