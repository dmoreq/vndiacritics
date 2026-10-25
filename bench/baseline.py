"""Precise throughput + accuracy baseline for optimization work.

Times the whole corpus in one span (no per-sentence clock calls in the loop) and
reports accuracy on both corpora. Run before and after any change.

Gold defaults to the ORIGINAL vndiacritics/data/in_domain.txt so that two corpora are
graded on identical sentences; only the statistics file changes.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vndiacritics.eval import score, split_sentences
from vndiacritics.model import Model
from vndiacritics.normalize import nfc, strip_accent_keep_case

OUT = ROOT / "bench/data/diacritic_eval_v0.txt"


def gold(path: Path) -> list[str]:
    return [nfc(s) for s in split_sentences(path.read_text(encoding="utf-8"))]


def timed(model, sents, reps=5):
    rates = []
    for _ in range(reps):
        t = time.perf_counter()
        for s in sents:
            model.restore(s)
        rates.append(len(sents) / (time.perf_counter() - t))
    return statistics.median(rates), rates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "vndiacritics/data")
    ap.add_argument("--gold", type=Path, default=ROOT / "vndiacritics/data/in_domain.txt")
    ap.add_argument("--tag", default="", help="suffix for the results file")
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()

    model = Model.load(args.data)
    gi, go = gold(args.gold), gold(OUT)
    si = [strip_accent_keep_case(s) for s in gi]
    so = [strip_accent_keep_case(s) for s in go]

    ri, runs_i = timed(model, si, args.reps)
    ro, runs_o = timed(model, so, args.reps)

    pi = [model.restore(s) for s in si]
    po = [model.restore(s) for s in so]
    ai = score(gi, pi).accuracy
    ao = score(go, po).accuracy

    out = {
        "data": str(args.data),
        "gold": str(args.gold),
        "in_domain": {"accuracy": round(ai, 4), "sent_per_s": round(ri)},
        "out_domain": {"accuracy": round(ao, 4), "sent_per_s": round(ro)},
        "in_domain_runs": [round(r) for r in runs_i],
        "out_domain_runs": [round(r) for r in runs_o],
        "in_domain_range": [round(min(runs_i)), round(max(runs_i))],
    }
    suffix = f"_{args.tag}" if args.tag else ""
    (ROOT / f"bench/baseline_results{suffix}.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out))
    label = args.tag or "default"
    print(
        f"\n[{label}] in-domain {ai * 100:.2f}%  {ri:.0f} sent/s "
        f"(range {min(runs_i):.0f}-{max(runs_i):.0f})"
    )
    print(f"[{label}] out-domain {ao * 100:.2f}%  {ro:.0f} sent/s")
    print(f"GATE in-domain >=95%: {'PASS' if ai >= 0.95 else 'FAIL'} ({ai * 100:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
