"""Per-register accuracy on the out-of-domain benchmark, plus the head-to-head
comparison against the Java reference numbers. Writes bench/register_results.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences  # noqa: E402
from vap.model import Model  # noqa: E402
from vap.normalize import nfc, strip_accent_keep_case  # noqa: E402


def main() -> int:
    src = ROOT / "bench/data/diacritic_eval_v0.txt"
    model = Model.load()

    buckets: dict[str, list[str]] = {}
    current = "unknown"
    for line in src.read_text(encoding="utf-8").split("\n"):
        s = line.strip()
        if s.startswith("# === register:"):
            current = s.split("register:")[1].strip(" =")
        elif s and not s.startswith("#"):
            buckets.setdefault(current, []).append(nfc(s))

    out: dict[str, dict] = {}
    for reg, gold in buckets.items():
        pred = [model.restore(strip_accent_keep_case(g)) for g in gold]
        r = score(gold, pred)
        out[reg] = {
            "sentences": len(gold),
            "accuracy": round(r.accuracy, 4),
            "correct": r.correct,
            "total": r.total,
        }

    all_gold = [g for gs in buckets.values() for g in gs]
    pred = [model.restore(strip_accent_keep_case(g)) for g in all_gold]
    r = score(all_gold, pred)
    out["_overall"] = {
        "sentences": len(all_gold),
        "accuracy": round(r.accuracy, 4),
        "correct": r.correct,
        "total": r.total,
        "skipped": r.skipped,
    }

    (ROOT / "bench/register_results.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
