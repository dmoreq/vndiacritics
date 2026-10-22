"""The one grader. Any report must come from here.

Deliberately counts sentences where the token count changed (`skipped`) instead of
silently dropping them, because silently dropping mismatches is what inflated the
reference project's published accuracy by about 4.8 points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Score:
    correct: int
    total: int
    skipped: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def score(gold: list[str], pred: list[str]) -> Score:
    correct = total = skipped = 0
    for g, p in zip(gold, pred):
        gw, pw = g.split(), p.split()
        if len(gw) != len(pw):
            skipped += 1
            continue
        for a, b in zip(gw, pw):
            total += 1
            correct += a.lower() == b.lower()
    skipped += abs(len(gold) - len(pred))
    return Score(correct=correct, total=total, skipped=skipped)


def split_sentences(text: str) -> list[str]:
    """Split on sentence punctuation, dropping empties."""
    return [s.strip() for s in re.split(r"[\.\!\n\;\?]", text) if s.strip()]
