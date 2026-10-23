"""Bottleneck analysis for vap. Profiler results are for ATTRIBUTION only;
wall-clock shares are re-measured without the profiler (cProfile inflates
call-heavy functions and hides the true cost distribution).
"""

from __future__ import annotations

import cProfile
import io
import pstats
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def load_corpus():
    raw = (ROOT / "vap/data/in_domain.txt").read_text(encoding="utf-8")
    return [strip_accent_keep_case(nfc(s)) for s in split_sentences(raw)]


def wall(sents, model, reps=3):
    best = []
    for _ in range(reps):
        t = time.perf_counter()
        for s in sents:
            model.restore(s)
        best.append(len(sents) / (time.perf_counter() - t))
    return statistics.median(best)


def main() -> int:
    model = Model.load()
    sents = load_corpus()
    print(f"corpus: {len(sents)} sentences, {sum(len(s.split()) for s in sents)} tokens")

    print(f"\nwall-clock throughput (median of 3 runs): {wall(sents, model):.0f} sent/s")

    pr = cProfile.Profile()
    pr.enable()
    for s in sents:
        model.restore(s)
    pr.disable()
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).sort_stats("tottime").print_stats(15)
    text = buf.getvalue()
    head = text.split("ncalls")[0]
    print("\n=== cProfile, top 15 by self time (ATTRIBUTION ONLY) ===")
    print(head)
    for line in text.split("ncalls", 1)[1].split("\n")[:20]:
        print("ncalls" + line if line.startswith("ncalls") else line)

    total = float(text.split("function calls")[1].split(" in ")[1].split(" seconds")[0])
    print(f"\nprofiled total: {total:.3f}s for {len(sents)} sentences "
          f"= {len(sents)/total:.0f} sent/s (slow vs wall-clock; do not quote)")

    # Isolate the pieces without the profiler.
    r = model._restorer
    print("\n=== component timing, no profiler ===")

    t = time.perf_counter()
    toks = [s.split() for s in sents]
    print(f"  tokenize (str.split)        : {time.perf_counter()-t:.4f}s")

    t = time.perf_counter()
    cols = [r._columns(tk) for tk in toks]
    dt = time.perf_counter() - t
    ncols = sum(len(c) for c, _ in cols)
    ncell = sum(len(x) for c, _ in cols for x in c)
    print(f"  _columns (candidates+prune) : {dt:.4f}s  cols={ncols} cells={ncell}")

    t = time.perf_counter()
    for c, _ in cols:
        if len(c) > 1:
            r._viterbi(c)
    dv = time.perf_counter() - t
    print(f"  _viterbi (DP)               : {dv:.4f}s")

    t = time.perf_counter()
    for s in sents:
        r.restore(s)
    dtot = time.perf_counter() - t
    print(f"  restore() total             : {dtot:.4f}s")
    print(f"  => DP share {dv/dtot*100:.1f}%, columns share {dt/dtot*100:.1f}%, "
          f"remainder (regex/case/join) {(dtot-dv-dt)/dtot*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
