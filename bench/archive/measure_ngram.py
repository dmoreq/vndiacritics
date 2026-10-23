"""Measure storage + latency of the n-gram approach to fill the comparison table honestly.

Measures, per configuration:
  - on-disk corpus size (raw text)
  - in-process RAM after load
  - load time
  - encode time (accent-stripped key -> candidates index) if applicable
  - per-sentence latency on a fixed 602-sentence workload
"""
import json
import os
import re
import resource
import time
import unicodedata as u
from collections import defaultdict

REPO = "/Users/quy.doan/Workspace/personal/vietnam-accent/Vietnamese-Accent-Prediction/datasets/"


def strip_acc(s):
    s = u.normalize("NFD", s)
    s = "".join(ch for ch in s if not u.combining(ch))
    return s.replace("đ", "d").replace("Đ", "D").lower()


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def parse_tsv(path):
    d = {}
    for line in open(path, encoding="utf-8"):
        k, _, v = line.rstrip("\n").rpartition("\t")
        if k:
            try:
                d[k] = int(v)
            except ValueError:
                pass
    return d


def mb(n):
    return n / 1024 / 1024


def main():
    out = {}
    t = time.time()
    g1 = parse_tsv(REPO + "news1gram_viwiki.tsv")
    load1 = time.time() - t
    t = time.time()
    g2 = parse_tsv(REPO + "news2grams_viwiki.tsv")
    load2 = time.time() - t

    out["files"] = {
        "news1gram_viwiki.tsv": os.path.getsize(REPO + "news1gram_viwiki.tsv"),
        "news2grams_viwiki.tsv": os.path.getsize(REPO + "news2grams_viwiki.tsv"),
        "test.txt": os.path.getsize(REPO + "test.txt"),
    }
    out["1gram"] = {"entries": len(g1), "load_s": round(load1, 2)}
    out["2gram"] = {"entries": len(g2), "load_s": round(load2, 2)}
    out["rss_after_load_mb"] = round(rss_mb(), 0)

    # build the unaccent -> candidates index (the Phase 4 optimisation)
    t = time.time()
    cand = defaultdict(list)
    for w in g1:
        cand[strip_acc(w)].append(w)
    idx_build = time.time() - t
    out["cand_index"] = {
        "keys": len(cand),
        "build_s": round(idx_build, 2),
        "total_forms": sum(len(v) for v in cand.values()),
    }
    out["rss_after_index_mb"] = round(rss_mb(), 0)

    # optional: drop the 2gram table and measure what that frees
    del g2
    import gc

    gc.collect()
    out["rss_after_drop_2gram_mb"] = round(rss_mb(), 0)

    # latency on a fixed workload
    raw = open(REPO + "test.txt", encoding="utf-8").read()
    sents = [s.strip() for s in re.split(r"[\.\!\n\;\?]", raw) if s.strip()][:300]

    def restore_sent(s):
        res = []
        for tok in s.split():
            m = re.match(r"^([^\wÀ-ỹ]*)(.*?)([^\wÀ-ỹ]*)$", tok, re.DOTALL)
            lead, core, trail = m.groups()
            if not core:
                res.append(tok)
                continue
            cs = cand.get(strip_acc(core))
            if not cs:
                res.append(tok)
                continue
            b = max(cs, key=lambda w: g1[w])
            if core[:1].isupper():
                b = b[:1].upper() + b[1:]
            res.append(lead + b + trail)
        return " ".join(res)

    t = time.time()
    n_tok = 0
    for s in sents:
        r = restore_sent(s)
        n_tok += len(s.split())
    el = time.time() - t
    out["unigram_lookup"] = {
        "sents": len(sents),
        "tokens": n_tok,
        "total_s": round(el, 3),
        "ms_per_sent": round(el / len(sents) * 1000, 2),
        "sents_per_s": round(len(sents) / el),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
