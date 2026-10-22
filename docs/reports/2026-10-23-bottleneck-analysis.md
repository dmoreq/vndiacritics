# Bottleneck analysis: `vap` restore path

**Date**: 2026-10-23
**Commit**: `1b85299`
**Machine**: Apple M3, Python 3.13.7, single process
**Scripts**: `bench/profile_bottleneck.py`, `bench/count_dp_work.py`, `bench/probe_miss_rule.py`, `bench/levers.py`

---

## 1. Baseline

| Measure | Value |
|---|---|
| Corpus | 602 sentences, 8,995 tokens |
| Wall-clock throughput | **1,852 sent/s** (median of 3) |
| `restore()` total | 0.299 s |
| RSS | 113 MB |

Note the discrepancy between the 1,739 sent/s in the benchmark report and 1,852 here:
the benchmark includes per-sentence `perf_counter` calls in its timed loop. This
script times the whole corpus in one span. Both are honest; they measure slightly
different things.

---

## 2. Where the time goes

Component timing measured **without** the profiler attached:

| Component | Time | Share |
|---|---:|---:|
| `_viterbi` (dynamic programming) | 0.272 s | **91.2%** |
| `_columns` (candidates + prune) | 0.020 s | 6.6% |
| regex + case + join (rest of `restore`) | 0.007 s | 2.2% |

cProfile attribution inside the DP (614k function calls total):

| Function | Calls | Self time |
|---|---:|---:|
| `store.py:49 get()` — trie lookup | **463,726** | **0.224 s (44%)** |
| `_viterbi` own loop body | 600 | 0.154 s (30%) |
| `dict.get` (unigram) | 573,824 | 0.053 s |
| `sorted` (beam pruning) | 6,388 | 0.011 s |
| `math.log` | 125,468 | 0.007 s |

**Verdict: CPU-bound, concentrated in one hot path.** 91% of wall time is the DP,
and the single largest contributor is 463,726 trie lookups.

---

## 3. The DP work, quantified

| Quantity | Value |
|---|---:|
| Columns (tokens) | 8,995 |
| Candidate cells | 66,437 |
| **Pair evaluations** | **463,726** |
| Mean candidates per column | 7.39 |
| Mean pairs per sentence | 770 |

Pair cost is quadratic in beam width: 7.39 × 7.39 ≈ 54 lookups per token transition.

| Outcome | Count | Share |
|---|---:|---:|
| Bigram hits | 93,624 | **20.2%** |
| UNK fallbacks (guaranteed misses) | 370,102 | **79.8%** |

**The core inefficiency**: four out of five trie walks are known misses. Each still
costs a full `marisa-trie` descent.

---

## 4. Measured primitive costs

| Operation | Cost | 463k calls would cost |
|---|---:|---:|
| `marisa-trie` get | 0.201 µs | 0.093 s |
| `dict` get | 0.016 µs | 0.007 s |
| **Difference** | **12.6x** | **0.086 s saved** |

A plain dict for the bigram table would recover ~0.086 s of the 0.299 s total
(**29%**) — at the cost of ~660 MB RSS versus 22 MB. Rejected on memory grounds;
this is why the trie exists.

---

## 5. Hypotheses tested and rejected

### Rejected: predict misses from unigram counts

Since 79.8% of pairs miss, a cheap pre-check could skip the walk. Tested two rules:

| Rule | Would skip | Wrongly skips |
|---|---:|---:|
| A: `unigram[prev] == 0` | 176 (0.04%) | **19** |
| B: `unigram[cur] == 0` | 194 (0.04%) | 0 |

Coverage is 0.04% — useless. Worse, Rule A is **unsafe**: 19 real bigrams exist
whose left word has unigram count 0 in this corpus, so applying it would lose hits.
Hypothesis refuted by measurement.

The reason: misses are *not* driven by out-of-vocabulary words. Both words are
usually in the vocabulary (4.1% OOV); the specific *pair* was simply never observed.

### Rejected: pair memoisation

| Quantity | Value |
|---|---:|
| Pair evaluations | 463,726 |
| Distinct pairs | 312,473 (67.4%) |
| Repeats | 32.6% |

A cache would replace 151k of 464k trie walks — a 33% reduction on the lookup
component, roughly 0.03 s, while adding an unbounded dict that grows with corpus
diversity. Marginal. Not worth the memory and cache-invalidation complexity.

### Rejected: narrower beam, for speed

Measured post-remediation:

| K | in-domain | out-of-domain | sent/s |
|---:|---:|---:|---:|
| None | 96.00% | 95.24% | 1,852 |
| 12 | 96.19% | 94.79% | 1,209 |
| **8 (current)** | **96.00%** | **95.24%** | **1,934** |
| 6 | 95.56% | 94.79% | 2,773 |
| 5 | 94.73% | 94.68% | 2,978 |

K=6 buys 43% more throughput for 0.44 accuracy points. K=8 remains the best
accuracy-per-second point; the plan scopes out retuning, so this is recorded,
not applied.

Curiously K=12 scores *higher* in-domain than K=8 while being slower — beam
pruning is not monotonic here, because pruning by unigram removes rare accented
forms that the DP would otherwise pick wrongly. Not investigated further; noted
so nobody assumes "wider is always more accurate".

---

## 6. What the ceiling looks like

The DP is O(tokens × K²) with K=8, i.e. ~64 trie/dict lookups per token. At
0.2 µs each, that is 13 µs per token of pure lookup, plus ~15 µs of Python loop
overhead per token (measured: 0.272 s / 8,995 tokens = 30 µs).

Pure Python cannot get much below this. The realistic options, in order:

| Option | Expected | Cost |
|---|---|---|
| Vectorise the DP with numpy (batched column scores) | 1.5–2x | new dependency |
| `mypyc`-compile `restore.py` | 3–5x | build step, same API |
| Rust extension via PyO3 | 10–20x | new toolchain |

None attempted: the plan gates optimisation on measurement, and the finding here
is that Python-level tuning is exhausted. Every remaining win is a *runtime*
change, not an algorithmic one.

---

## 7. Summary

- Bottleneck: **the Viterbi inner loop**, 91% of wall time, dominated by 463k trie
  lookups of which 80% are guaranteed misses.
- The 80% miss rate is **not fixable by a pre-check** — tested, refuted.
- The trie's 12.6x per-lookup penalty is the price of 22 MB instead of 660 MB.
  Already the right trade.
- Remaining speedups require leaving pure Python.
- Accuracy/speed is currently at the K=8 knee; K=6 is the next notch if throughput
  matters more than 0.44 points.
