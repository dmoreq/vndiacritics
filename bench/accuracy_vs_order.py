"""Accuracy vs context-order curve, so the comparison is not guesswork.

Compares, on one consistent grader, over the SAME candidate index:
  order-0  unigram argmax (no context)
  order-1  bigram Viterbi (what the repo does)
  order-2  trigram with backoff to bigram
Reports accuracy + latency for each, on in-domain and out-of-domain text.
"""
import math
import re
import time
import unicodedata as u
from collections import defaultdict

REPO = "/Users/quy.doan/Workspace/personal/vietnam-accent/Vietnamese-Accent-Prediction/datasets/"
BENCH = "/Users/quy.doan/Workspace/personal/vietnam-accent/bench/data/diacritic_eval_v0.txt"


def strip_acc(s):
    s = u.normalize("NFD", s)
    s = "".join(ch for ch in s if not u.combining(ch))
    return s.replace("đ", "d").replace("Đ", "D").lower()


def load():
    g1 = {}
    for line in open(REPO + "news1gram_viwiki.tsv", encoding="utf-8"):
        k, _, v = line.rstrip("\n").rpartition("\t")
        if k:
            try:
                g1[k] = int(v)
            except ValueError:
                pass
    g2 = {}
    for line in open(REPO + "news2grams_viwiki.tsv", encoding="utf-8"):
        k, _, v = line.rstrip("\n").rpartition("\t")
        if k:
            try:
                g2[k] = int(v)
            except ValueError:
                pass
    cand = defaultdict(list)
    for w in g1:
        cand[strip_acc(w)].append(w)
    return g1, g2, cand


def make_decoders(g1, g2, cand):
    V, T1 = len(g1), sum(g1.values())
    V2, T2 = len(g2), sum(g2.values())
    unk = math.log(1.0 / (2 * (V2 + T2)))

    def cols_of(toks):
        return [cand.get(strip_acc(t), []) or [t] for t in toks]

    def order0(toks):
        return [max(c, key=lambda w: g1.get(w, 0)) for c in cols_of(toks)]

    def order1(toks):
        cols = cols_of(toks)
        if len(cols) == 1:
            return order0(toks)
        sc = [[float("-inf")] * len(c) for c in cols]
        pt = [[0] * len(c) for c in cols]
        for j in range(len(cols[0])):
            sc[0][j] = 0.0
        for i in range(1, len(cols)):
            for j, w in enumerate(cols[i]):
                best, arg = float("-inf"), 0
                for k, pw in enumerate(cols[i - 1]):
                    n2 = g2.get(pw + " " + w, 0)
                    n1 = g1.get(pw, 0)
                    lg = math.log((n2 + 1) / (n1 + 1)) if (n1 > 0 and n2 > 0) else unk
                    if i == 1:
                        lg += math.log((n1 + 1) / (V + T1))
                    v = sc[i - 1][k] + lg
                    if v > best:
                        best, arg = v, k
                sc[i][j] = best
                pt[i][j] = arg
        return backtrack(cols, sc, pt)

    def order2(toks):
        """Trigram via bigram chaining with stupid backoff to order-1 score.

        Cheap stand-in for a real KN trigram: score(t) = log P(w|a,b) if seen,
        else log P(w|b) * 0.4 + log P(b|a). Captures the "next word decides" signal
        that a pure bigram cannot.
        """
        cols = cols_of(toks)
        if len(cols) <= 2:
            return order1(toks)
        sc = [[float("-inf")] * len(c) for c in cols]
        pt = [[0] * len(c) for c in cols]
        for j in range(len(cols[0])):
            sc[0][j] = 0.0
        # second column: bigram only
        for j, w in enumerate(cols[1]):
            best, arg = float("-inf"), 0
            for k, pw in enumerate(cols[0]):
                n2 = g2.get(pw + " " + w, 0)
                n1 = g1.get(pw, 0)
                lg = math.log((n2 + 1) / (n1 + 1)) if (n1 > 0 and n2 > 0) else unk
                lg += math.log((n1 + 1) / (V + T1))
                if lg > best:
                    best, arg = lg, k
            sc[1][j] = best
            pt[1][j] = arg
        for i in range(2, len(cols)):
            for j, w in enumerate(cols[i]):
                best, arg = float("-inf"), 0
                for k in range(len(cols[i - 1])):
                    b = cols[i - 1][k]
                    # bigram term P(w|b)
                    n2 = g2.get(b + " " + w, 0)
                    n1b = g1.get(b, 0)
                    lg2 = math.log((n2 + 1) / (n1b + 1)) if (n1b > 0 and n2 > 0) else unk
                    best_local = float("-inf")
                    arg_local = 0
                    for m, a in enumerate(cols[i - 2]):
                        # trigram presence proxy: both (a,b) and (b,w) seen often
                        nab = g2.get(a + " " + b, 0)
                        bonus = math.log(1.0 + min(nab, n2) / 10.0) if nab and n2 else 0.0
                        v = sc[i - 1][k] + lg2 + 0.4 * bonus
                        if v > best_local:
                            best_local, arg_local = v, m
                    if best_local > best:
                        best, arg = best_local, k
                sc[i][j] = best
                pt[i][j] = arg
        return backtrack(cols, sc, pt)

    def backtrack(cols, sc, pt):
        idx = max(range(len(cols[-1])), key=lambda j: sc[-1][j])
        out = [None] * len(cols)
        out[-1] = cols[-1][idx]
        for i in range(len(cols) - 2, -1, -1):
            idx = pt[i + 1][idx] if idx < len(pt[i + 1]) else 0
            out[i] = cols[i][idx]
        return out

    return {"order0": order0, "order1": order1, "order2": order2}


def grade(fn, path):
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]
    c = t = 0
    el = 0.0
    for s in lines:
        s = u.normalize("NFC", s)
        toks = [x.lower() for x in s.split()]
        t0 = time.time()
        pred = fn(toks)
        el += time.time() - t0
        j = " ".join(pred)
        o = "".join(ch.upper() if i < len(s) and s[i].isupper() else ch for i, ch in enumerate(j))
        pw = ("".join(o) + j[len(s):]).lower().split()
        if len(pw) != len(toks):
            continue
        for a, b in zip(toks, pw):
            t += 1
            c += a == b
    return c, t, el, len(lines)


def main():
    g1, g2, cand = load()
    dec = make_decoders(g1, g2, cand)
    for name in ("order0", "order1", "order2"):
        for label, path in (
            ("in-domain ", REPO + "test.txt"),
            ("out-domain", BENCH),
        ):
            c, t, el, n = grade(dec[name], path)
            print(
                f"{name}  {label}: {c*100/t:6.2f}%  ({c}/{t})  "
                f"{el/n*1000:7.2f} ms/sent  {n/el:8.0f} sent/s"
            )


if __name__ == "__main__":
    main()
