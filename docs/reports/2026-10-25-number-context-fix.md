# Number-context fix: n1-confidence smoothing (bigram_conf_k)

**Date**: 2026-10-25
**Base**: commit `dc96d37` (v0.1.0 + workflow-hold restructure)
**Script**: `bench/ab_confidence.py`
**Fixes**: docs/USAGE.md §4.1; root cause analysis in
[2026-10-23-number-context-root-cause.md](2026-10-23-number-context-root-cause.md)

## 1. What changed

`Restorer._transition_score` now blends the bigram ratio toward the current
word's unigram probability with Jelinek-Mercer weight `lambda = n1/(n1+K)`:

```text
conf_k > 0:  p = (n2 + K * p_uni(cur)) / (n1 + K)      # pseudo-count form
conf_k = 0:  p = (n2 + 1) / (n1 + 1)                   # legacy reference formula
no evidence: p = UNK (unchanged)
```

The two positive-evidence forms are algebraically identical to
`lambda*(n2/n1) + (1-lambda)*p_uni`. The pseudo-count form was chosen for
speed: `K*p_uni` is a per-column constant hoisted out of the predecessor loop,
so a scored pair costs one add + one div + one log — the same op count as
legacy. Measured throughput returned to the historical band after the hoist.

Default `bigram_conf_k=None` scales K with corpus mass: `K = t1 * 1000 / 400,508,022`,
which reproduces the measured K=1000 on the reference corpus and collapses to
~0 (legacy scoring) on toy tables. Same lesson as `bigram_skip_below`: an
absolute constant drowns real evidence in small vocabularies.

## 2. The sweep

`bench/ab_confidence.py`, both gold corpora, split pipelines:

| K | in-domain | out-domain | `tang 12.5% trong nam 2025` |
|---:|---:|---:|---|
| 0 (legacy) | 96.0089% | 95.2435% | tăng 12.5% **tróng nằm** 2025 |
| 10 | 96.0422% | 95.3567% | tăng 12.5% **tróng nằm** 2025 |
| 100 | 96.0422% | 95.4700% | tăng 12.5% trong năm 2025 |
| **1000** | **96.0534%** | **95.5832%** | tăng 12.5% trong năm 2025 |
| 10000 | 95.9533% | 95.5832% | tăng 12.5% trong năm 2025 |

K=1000 wins on BOTH corpora and fixes the bug. K=10000 over-shrinks and
regresses in-domain below the measured baseline.

## 3. Post-fix measurements

| Metric | Before | After | Delta |
|---|---:|---:|---|
| in-domain accuracy | 96.0089% | 96.0534% | +0.045 |
| out-domain accuracy | 95.2435% | 95.5832% | +0.34 |
| in-domain throughput | 1,841-2,195 sent/s (historical band) | 1,837 (1,817-1,886) | within variance |
| out-domain throughput | 2,879 (under load) | 2,444 | within variance |
| tests | 58 | 60 | +2 blend unit tests |
| pre-commit | 18/18 | 18/18 | — |

## 4. Design decisions recorded

1. **UNK branch untouched.** A missing bigram still scores the constant UNK
   regardless of K. Interpolating the zero-count branch toward p_uni is the
   more principled JM, but the minimal change already flips every measured
   decision the bug needs; the principled version changes far more paths and
   was not measured. If someone pursues it, re-run the sweep first.
2. **Auto-K scales with corpus mass, not |V|.** K is a pseudo-count budget;
   its right scale is a fraction of total tokens, not vocabulary size.
   Measured ratio: 1000 / 400,508,022 = 2.5e-6.
3. **The severed column stays severed.** Transitions out of a zero-candidate
   column (the number itself) still score UNK for every path. The fix works
   through the surviving transition (`tróng nằm` vs `trong năm`); priors lost
   at the severed column are equal for all candidates and cancel. Curing the
   severance itself needs digit-context features (a retuning change, out of
   scope here).
4. **Re-measure K after any corpus change.** The sweep is cheap (one process,
   five configurations, seconds). WS2 (corpus v2) must re-run
   `bench/ab_confidence.py` before adopting v2 as default.

## 5. Tests

- `tests/test_restore.py::test_confidence_blend_prefers_massive_denominator` —
  the bug in miniature: legacy picks the thin-denominator path, K=1000 flips it.
- `tests/test_restore.py::test_confidence_blend_zero_is_legacy` — K=0
  reproduces the reference arithmetic exactly.
- `tests/test_documented_weaknesses.py::test_number_adjacency_fixed` — the
  pinned weakness test, updated per its own instruction now that the bug is
  fixed; docs/USAGE.md §4.1 rewritten in the same change.

## 6. What this does NOT fix

- `chao ban` → `chào bán` (short-utterance prior; unchanged, pinned test passes).
- `so 12` → `số 12` (needs a digit-context feature; unchanged).
- The 73-token OOV ceiling and the residual ambiguity population
  (99.19% decoder ceiling stands; measured aggregate moved +0.045 toward it).
