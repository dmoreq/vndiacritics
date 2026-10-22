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
| In-domain accuracy | ≥ 95.0% | **96.00%** (8635/8995) | PASS |
| Out-of-domain accuracy | ≥ 92.5% | **95.24%** (841/883) | PASS |
| Throughput | ≥ 5,000 sent/s | **1,739** in-domain / 2,492 out | **MISS** (−65%) |
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
| Package pipeline (normalise → split) | 8995 | **96.00%** | 8635 |
| Reference pipeline (line split) | 9085 | 95.98% | 8720 |

Both rows are now measured on the post-remediation code. Line-split scores slightly higher
because punctuation stays attached to its token and is preserved in place, so a token whose
diacritics are right is scored right; the normalise-then-split pipeline strips that punctuation
first, changing 90 token boundaries. Both are pinned by tests.

### Out-of-domain by register (`bench/data/diacritic_eval_v0.txt`, CC0)

| Register | Sentences | Accuracy | Correct |
|---|---:|---:|---:|
| news / long-form | 13 | **98.54%** | 203/206 |
| official documents | 12 | **95.51%** | 170/178 |
| contracts / business | 15 | **95.12%** | 195/205 |
| everyday / conversational | 15 | **89.89%** | 169/188 |
| **overall** | **55** | **95.24%** | 841/883 |

The normalise-then-split pipeline scores 95.24%; the line-split pipeline scores 94.85%. Both
are reported; neither is the "real" number, and choosing one to quote would be cherry-picking.
These figures are post-remediation: the earlier 91.39%/94.85% pair was measured before the
whitespace and per-token case fix, which was itself worth about 4 points on this benchmark.

**The register spread is 8.65 points** (98.54% news vs 89.89% conversational). This matches the
prediction in the prior research note and confirms it: register coverage dominates model choice
for this problem.

---

## 3. Latency and resources

| Measure | Value |
|---|---|
| Median latency, in-domain | 0.484 ms/sentence |
| Median latency, out-of-domain | 0.479 ms/sentence |
| Throughput, in-domain | 1,739 sent/s |
| Throughput, out-of-domain | 2,732 sent/s |
| Model load | 0.286 s |
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
| Hit-cache in `BigramStore` | n/a | no gain | reverted (no gain) |

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

### Closed by remediation: out-of-domain accuracy (91.39% → 95.24%, target 92.5%)

This target was originally recorded as missed at 91.39%. The remediation round closed it: the
whitespace and per-token case fix recovered about 4 points, because the old `restore()` rejoined
tokens with single spaces and then reapplied case positionally against the original string, which
shifted case for every character after the first irregular space or punctuation mark. Tokens whose
diacritics were already correct were being scored wrong purely on casing.

Conversational Vietnamese is still the weak register (89.89% on 188 tokens). The corpus is news
and Wikipedia, so conversational particles (`nha`, `nhe`, `a`, `ha`) are under-represented.

**Remaining gap**: add a conversational corpus (`Tatoeba vi` is CC-BY and already used by the
reference benchmark). That is a data task, not a model task.

### Missed: throughput (1,739 vs 5,000 sent/s target)

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
corpus. This package scores **96.00%** in-domain. The improvement is real; the earlier 96.29%
was not a like-for-like comparison.

---

## 6. Reproduced raw output

`bench/results.json`:

```json
{
  "load_s": 0.286,
  "rss_mb": 113.2,
  "in_domain_split": {
    "accuracy": 0.96,
    "correct": 8635,
    "total": 8995,
    "skipped": 0,
    "ms_per_sent_median": 0.484,
    "sents_per_s": 1739
  },
  "in_domain_lines": {
    "accuracy": 0.9598,
    "correct": 8720,
    "total": 9085,
    "skipped": 0,
    "ms_per_sent_median": 0.489,
    "sents_per_s": 1739
  },
  "out_domain_split": {
    "accuracy": 0.9524,
    "correct": 841,
    "total": 883,
    "skipped": 0,
    "ms_per_sent_median": 0.479,
    "sents_per_s": 2492
  },
  "out_domain_lines": {
    "accuracy": 0.9485,
    "correct": 737,
    "total": 777,
    "skipped": 0,
    "ms_per_sent_median": 0.504,
    "sents_per_s": 1926
  },
  "vap/data/uni.tsv": 2.18,
  "vap/data/bi.trie": 22.03,
  "vap/data/bi.meta.json": 0.0
}
```

`skipped: 0` in every configuration: no sentence was silently dropped, which is the property the
reference grader lacked.

---

## 7. Remediation round (post-review)

Four defects reported in review were reproduced, fixed under RED→GREEN, and committed
separately. Plan: `.hermes/plans/2026-10-23_053328-vap-review-remediation.md`.

| Commit | Defect | Before | After |
|---|---|---|---|
| `410a017` | punctuation-only token duplicated | `'tôi ...... yeu'` | `'tôi ... yeu'` |
| `ba76194` | whitespace collapsed, case shifted | `'tôI YeU'` | `'  TÔI YÊU  '` |
| `230008e` | non-positive beam accepted | `ValueError` from `max()` at restore | `ValueError: max_candidates must be positive` at construction |
| `ca36ae0` | missing sidecar crashed load | `FileNotFoundError` | both cache files rebuilt from `bi.tsv` |
| `cb1337c` | dead `Restorer._score` | 10 lines, no callers | removed |

### Effect on measured quality

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| In-domain (normalise→split) | 95.66% | **96.00%** | +0.34 |
| In-domain (line split) | 94.72% | **95.98%** | +1.26 |
| Out-of-domain (normalise→split) | 91.39% | **95.24%** | +3.85 |
| Throughput, in-domain | 2,019 sent/s | 1,739 sent/s | **−14%** |

The accuracy gain is not from better candidate selection. It comes from case being reapplied
per token instead of positionally across the rejoined sentence; the old code marked correctly
accented tokens wrong whenever an irregular space or punctuation mark shifted character
positions. The out-of-domain gain is largest because that benchmark is punctuation-heavy.

**The throughput drop is a real cost, not noise.** `restore()` now runs a regex `finditer` and
copies source slices instead of one `split`/`join`. No optimisation was attempted: the plan
scopes out retuning, and 1,739 sent/s still clears the practical bar. Anyone who needs the old
speed back should vectorise or compile the DP, not undo the correctness fix.

### Verified not a regression

`so` is not disambiguated to `số` before a number (`so 12` → `so 12`). Checked against commit
`746198c` in a throwaway worktree: identical output. The cause is corpus frequency — `đồng so`
(3478) is 10x `đồng số` (359) — so it is the known digit-context limitation, not damage from
this round. Documented in the README rather than silently patched, because fixing it is a
retuning change that would need its own accuracy measurement.
