"""Grade case correction on bench/data/cased_eval_v0.txt.

The cased eval's contract: input is fully lowercased and accent-stripped
(strip_accent), the model must restore BOTH diacritics and letter case, and
scoring is case-sensitive. case="preserve" on the same input is the baseline
to beat: it positional-copies case from the lowercased input, so its score is
exactly the share of gold tokens that should be lowercase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vndiacritics.eval import score
from vndiacritics.model import Model
from vndiacritics.normalize import nfc, strip_accent


def load_gold(path: Path) -> dict[str, list[str]]:
    registers: dict[str, list[str]] = {}
    current = "none"
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"# === register: (.+) ===", line)
        if m:
            current = m.group(1)
            continue
        if not line.startswith("#"):
            registers.setdefault(current, []).append(nfc(line))
    return registers


def grade(model: Model, gold: list[str], case: str, case_sensitive: bool):
    preds = [model.restore(strip_accent(s), case=case) for s in gold]
    return score(gold, preds, case_sensitive=case_sensitive)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--gold", type=Path, default=ROOT / "bench/data/cased_eval_v0.txt")
    ap.add_argument("--json-out", type=Path, default=ROOT / "bench/cased_eval_results.json")
    args = ap.parse_args()

    model = Model.load(args.data)
    registers = load_gold(args.gold)
    results: dict = {}
    for reg, gold in registers.items():
        r = grade(model, gold, case="correct", case_sensitive=True)
        p = grade(model, gold, case="preserve", case_sensitive=True)
        results[reg] = {
            "sentences": len(gold),
            "correct_case": r.accuracy,
            "preserve_baseline": p.accuracy,
            "delta": r.accuracy - p.accuracy,
        }
        print(
            f"{reg:>15}: correct={r.accuracy * 100:6.2f}%  "
            f"preserve={p.accuracy * 100:6.2f}%  delta={100 * (r.accuracy - p.accuracy):+.2f}"
        )
    # Overall: concatenate golds and grade once (token-weighted).
    all_gold = [s for gold in registers.values() for s in gold]
    r = grade(model, all_gold, case="correct", case_sensitive=True)
    p = grade(model, all_gold, case="preserve", case_sensitive=True)
    results["_overall"] = {
        "sentences": len(all_gold),
        "correct_case": r.accuracy,
        "preserve_baseline": p.accuracy,
        "delta": r.accuracy - p.accuracy,
        "skipped_case": r.skipped,
    }
    print(
        f"{'OVERALL':>15}: correct={r.accuracy * 100:6.2f}%  "
        f"preserve={p.accuracy * 100:6.2f}%  skipped={r.skipped}"
    )
    args.json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
