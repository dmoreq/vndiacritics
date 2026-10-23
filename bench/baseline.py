"""Precise throughput + accuracy baseline for optimization work.

Times the whole corpus in one span (no per-sentence clock calls in the loop) and
reports accuracy on both corpora. Run before and after any change.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case

IN = ROOT / "vap/data/in_domain.txt"
OUT = ROOT / "bench/data/diacritic_eval_v0.txt"


def gold(path):
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
    model = Model.load()
    gi, go = gold(IN), gold(OUT)
    si = [strip_accent_keep_case(s) for s in gi]
    so = [strip_accent_keep_case(s) for s in go]

    ri, runs_i = timed(model, si)
    ro, runs_o = timed(model, so)

    pi = [model.restore(s) for s in si]
    po = [model.restore(s) for s in so]
    ai = score(gi, pi).accuracy
    ao = score(go, po).accuracy

    out = {
        "in_domain": {"accuracy": round(ai, 4), "sent_per_s": round(ri)},
        "out_domain": {"accuracy": round(ao, 4), "sent_per_s": round(ro)},
        "in_domain_runs": [round(r) for r in runs_i],
        "out_domain_runs": [round(r) for r in runs_o],
    }
    (ROOT / "bench/baseline_results.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out))
    print(f"\nGATE in-domain >=95%: {'PASS' if ai >= 0.95 else 'FAIL'} ({ai*100:.2f}%)")
    print(f"GATE throughput >=2000 sent/s: {'PASS' if ri >= 2000 else 'FAIL'} ({ri:.0f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
