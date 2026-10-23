"""Measure accuracy, latency, storage and memory. Writes bench/results.json."""

from __future__ import annotations

import json
import resource
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from vap.eval import score, split_sentences
from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def load_gold(path: Path, mode: str) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    if mode == "split":
        return [nfc(s) for s in split_sentences(raw)]
    return [
        nfc(s.strip())
        for s in raw.split("\n")
        if s.strip() and not s.strip().startswith("#")
    ]


def measure(model: Model, gold: list[str]) -> dict:
    stripped = [strip_accent_keep_case(g) for g in gold]
    times: list[float] = []
    pred: list[str] = []
    for s in stripped:
        t0 = time.perf_counter()
        pred.append(model.restore(s))
        times.append(time.perf_counter() - t0)
    r = score(gold, pred)
    return {
        "accuracy": round(r.accuracy, 4),
        "correct": r.correct,
        "total": r.total,
        "skipped": r.skipped,
        "ms_per_sent_median": round(statistics.median(times) * 1000, 3),
        "sents_per_s": round(len(times) / sum(times)),
    }


def main() -> int:
    t0 = time.perf_counter()
    model = Model.load()
    load_s = time.perf_counter() - t0
    out: dict = {"load_s": round(load_s, 3), "rss_mb": round(rss_mb(), 1)}

    for name, path in (
        ("in_domain", ROOT / "vap/data/in_domain.txt"),
        ("out_domain", ROOT / "bench/data/diacritic_eval_v0.txt"),
    ):
        out[f"{name}_split"] = measure(model, load_gold(path, "split"))
        out[f"{name}_lines"] = measure(model, load_gold(path, "lines"))

    for rel in ("vap/data/uni.tsv", "vap/data/bi.trie", "vap/data/bi.meta.json"):
        p = ROOT / rel
        out[rel] = round(p.stat().st_size / 1024 / 1024, 2) if p.exists() else None

    (ROOT / "bench/results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
