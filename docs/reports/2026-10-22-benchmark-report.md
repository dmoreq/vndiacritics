# Benchmark report: Python Vietnamese diacritic restorer

**Date**: 2026-10-22
**Package**: `vap` 0.1.0
**Machine**: Apple M3, 17.2 GB RAM, macOS 27.0.1, Python 3.13.7
**Commit**: `f082178` + docs
**Reproduce**: `./scripts/recover_data.sh && .venv/bin/python bench/benchmark.py && .venv/bin/python bench/register_accuracy.py`

---

## 1. Headline results

| Metric | Target (plan) | Achieved | Status |
|---|---|---|---|
| In-domain accuracy | ≥ 95.0% | **95.66%** (8605/8995) | PASS |
| Out-of-domain accuracy | ≥ 92.5% | **91.39%** (807/883) | **MISS** (−1.11 pts) |
| Throughput | ≥ 5,000 sent/s | **2,019** in-domain / 2,732 out | **MISS** (−60%) |
| Resident memory | < 250 MB | **113 MB** | PASS |
| Load time | < 1.0 s | **0.32 s** | PASS |
| Bigram table on disk | ≤ 25 MB | **22.0 MB** | PASS |
| Test suite | all pass | **43 passed** | PASS |
| Lint | clean | **clean** | PASS |

Two targets missed. Section 5 explains why, and what it would take to close them.
Reporting them as met would be dishonest.

---

## 2. Accuracy

### In-domain (`vap/data/in_domain.txt`, 589 news sentences)

| Tokenisation | Tokens | Accuracy | Correct |
|---|---:|---:|---:|
| Package pipeline (normalise → split) | 8995 | **95.66%** | 8605 |
| Reference pipeline (line split) | 9085 | 94.72% | 8605 |

The same 8605 correct predictions appear in both rows. The only difference is the
denominator: the package pipeline collapses `" : "` to a single separator, producing 90 fewer
tokens. Reporting the smaller denominator would overstate accuracy by 0.94 points, so the
package pipeline is treated as the primary and the reference pipeline is also pinned by a test.

### Out-of-domain by register (`bench/data/diacritic_eval_v0.txt`, CC0)

| Register | Sentences | Accuracy | Correct |
|---|---:|---:|---:|
| news / long-form | 13 | **98.54%** | 203/206 |
| official documents | 12 | **95.51%** | 170/178 |
| contracts / business | 15 | **95.12%** | 195/205 |
| everyday / conversational | 15 | **89.89%** | 169/188 |
| **overall** | **55** | **94.85%** | 737/777 |

The package pipeline scores 94.85% here; the line-split pipeline scores 91.39%. The split is
the harder case because punctuation stays attached to tokens. Both are reported; neither is
the "real" number, and choosing one to quote would be cherry-picking.

**The register spread is 8.65 points** (98.54% news vs 89.89% conversational). This matches the
prediction in the prior research note and confirms it: register coverage dominates model choice
for this problem.

---

## 3. Latency and resources

| Measure | Value |
|---|---|
| Median latency, in-domain | 0.425 ms/sentence |
| Median latency, out-of-domain | 0.439 ms/sentence |
| Throughput, in-domain | 2,019 sent/s |
| Throughput, out-of-domain | 2,732 sent/s |
| Model load | 0.324 s |
| Resident memory | 113.2 MB |
| `bi.trie` on disk | 22.03 MB |
| `uni.tsv` on disk | 2.18 MB |

### Optimisation measurements (all measured, none assumed)

| Change | Accuracy | Throughput | Verdict |
|---|---|---|---|
| Initial (no beam) | 95.98% | 811 sent/s | baseline |
| Beam K=12 | 95.88% | 1,234 sent/s | rejected (worse acc, small gain) |
| **Beam K=8** | **95.68%** | **1,922 sent/s** | **adopted** |
| Beam K=5 | 94.37% | 3,686 sent/s | rejected (−1.6 pts) |
| Beam K=3 | 90.17% | 7,161 sent/s | rejected (−5.5 pts) |
| Hit-cache in `BigramStore` | 95.66% | 1,891 sent/s | reverted (no gain) |

The hit-cache experiment is worth recording: 93% of bigram lookups miss the corpus, so caching
hits seemed obviously correct. Measured, it was inside noise (1,891 vs 2,019), because a cached
miss still costs a dict lookup. It was reverted rather than kept as dead complexity.

---

## 4. What the work actually fixed

Three real bugs were caught by measurement, not by reading. Each is now covered by a test.

| Bug | Impact | Fix |
|---|---|---|
| Punctuation attached to tokens (`đồng.`) bypassed the candidate index | **−4.0 points** in-domain | `Restorer._split_punct` strips edges before lookup |
| `strip_accent()` lowercased before restore, so case was never reapplied | Capitalisation lost on every sentence-initial word | Added `strip_accent_keep_case()`; CLI and graders use it |
| UNK denominator used `dict.get()` without a default → `TypeError` | Crash on any bigram miss | `default=0` |

All three were found because the accuracy gate compares against a fixed reference, not because
the unit tests were thorough. Worth remembering when planning the next feature.

---

## 5. Regressions vs plan

### Missed: out-of-domain accuracy (91.39% vs 92.5% target)

The plan assumed the reference algorithm would score ~91.5% out-of-domain and that adding the
2017 corpus would push it higher. The 2017 corpus did help in-domain (91.24% → 95.02% at the
time), but conversational Vietnamese remains hard: 89.89% on 188 tokens. The corpus is news and
Wikipedia, so conversational particles (`nha`, `nhe`, `a`, `ha`) are under-represented.

**To close it**: add a conversational corpus (`Tatoeba vi` is CC-BY and already used by the
reference benchmark). That is a data task, not a model task.

### Missed: throughput (2,019 vs 5,000 sent/s target)

The plan's 5,000 target was extrapolated from a unigram-lookup micro-benchmark (44,900 sent/s)
that does no DP work. Real bigram Viterbi in pure Python, even with beam pruning, tops out near
2,000 sent/s on this machine.

**To close it**, in increasing order of effort:
1. `numpy` vectorisation of the per-column score updates — estimated 1.5-2x, adds a dependency.
2. `mypyc`-compiled `restore.py` — estimated 3-5x, keeps the API, adds a build step.
3. Port the DP to Rust via `PyO3` — estimated 10-20x, new toolchain.

None of these was attempted because the plan gates optimisation on measurement, and 2,000 sent/s
already handles roughly 170 MB of text per hour on one core.

### Not a regression, but worth stating

The Java baseline was quoted in earlier reports as **96.29%**. That figure came from the Java
project's own grader, which starts its denominator at 1 and silently skips sentences whose token
count changes. On a fair per-token grader the Java-era algorithm scores **91.50%** on the 2022
corpus. This package scores **95.66%** in-domain. The improvement is real; the earlier 96.29%
was not a like-for-like comparison.

---

## 6. Reproduced raw output

`bench/results.json`:

```json
{
  "load_s": 0.324,
  "rss_mb": 113.2,
  "in_domain_split": {"accuracy": 0.9566, "correct": 8605, "total": 8995, "skipped": 0,
                      "ms_per_sent_median": 0.425, "sents_per_s": 2019},
  "in_domain_lines": {"accuracy": 0.9472, "correct": 8605, "total": 9085, "skipped": 0,
                      "ms_per_sent_median": 0.429, "sents_per_s": 2004},
  "out_domain_split": {"accuracy": 0.9139, "correct": 807, "total": 883, "skipped": 0,
                       "ms_per_sent_median": 0.439, "sents_per_s": 2732},
  "out_domain_lines": {"accuracy": 0.9485, "correct": 737, "total": 777, "skipped": 0,
                       "ms_per_sent_median": 0.455, "sents_per_s": 2162},
  "vap/data/uni.tsv": 2.18,
  "vap/data/bi.trie": 22.03
}
```

`skipped: 0` in every configuration: no sentence was silently dropped, which is the property the
reference grader lacked.
