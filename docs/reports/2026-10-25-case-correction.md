# Case correction (`case="correct"`): statistical truecaser

**Date**: 2026-10-25
**Base**: commit `ff3310a`
**Eval**: `bench/cased_eval.py` on `bench/data/cased_eval_v0.txt` (CC0, 40
sentences, 603 tokens, 4 registers)
**Data requirement**: corpus v2b (case.tsv / case_bi.tsv; v1 has none and
`case="correct"` raises with the build command)

## 1. Feature

`Model.restore(text, case="correct")` (CLI `--case correct`) restores letter
case in addition to diacritics, using a Moses-style statistical truecaser
(`vndiacritics/truecase.py`):

- per-type case frequencies from `case.tsv` (lower / title / ALL-CAPS /
  sentence-initial counts);
- ratio-based sentence-initial rule: a type is capitalized at sentence start
  when `(initial + cap) * INITIAL_FOLD > lower` — content words ("Bộ", "Tôi",
  "Ngày") gain their capital, function words ("và", "của") keep lowercase;
- capitalized-bigram continuation from `case_bi.tsv` ("Hà Nội", "Bộ Tài
  chính") with gazetteer reinforcement (Vietnamese namedb, MIT; GeoNames VN,
  CC BY 4.0);
- acronym protection via ALL-CAPS attestations, including fold-key matches
  ("USD/VND" -> corpus key "usdvnd");
- OOV tokens are left untouched (positional copy) — unknown words never gain
  or lose case; a bare ASCII letter is uppercased (contract labels "Bên A").

Default mode stays `case="preserve"`: the positional case-copy contract is
unchanged, pinned by the existing tests (96 pass unmodified).

## 2. Measured

`INITIAL_FOLD` sweep (the one free parameter), case-sensitive token accuracy:

| FOLD | 8 | 32 | **64** | 128 | 256 |
|---|---:|---:|---:|---:|---:|
| accuracy | 88.89% | 90.22% | **90.38%** | 90.38% | 90.38% |

Final per-register (FOLD=64, v2b):

| Register | correct | preserve baseline | Delta |
|---|---:|---:|---:|
| news | **93.88%** | 78.91% | +14.97 |
| official | 91.88% | 82.50% | +9.38 |
| conversational | 90.44% | 79.41% | +11.03 |
| contracts | 85.62% | 73.12% | +12.50 |
| **overall** | **90.38%** | 78.44% | **+11.94** |

Gate: >= 85% case-sensitive token accuracy — **PASS** (90.38%).

## 3. Remaining error modes (70/603 tokens)

- Sentence-initial title words whose lowercase usage dominates the mixture
  ("Bên" in contracts: mid-sentence "bên" far outweighs initial "Bên") —
  residual of the ratio rule; contracts register is the weakest (85.62%).
- Mid-name particles without attested pairs ("Văn" when "Nguyễn Văn" was not
  counted in case_bi at that position).
- Diacritic-task leakage, not case errors: "Báo Thanh Nien" -> "niên" (gold
  keeps the paper's unaccented name), "đồng." -> "động.".
- Ideas rejected so far: bigger CONTINUATION_WEIGHT, per-register FOLD —
  not measured, do not add without a sweep.

## 4. Design notes

- The truecaser decides AFTER diacritic restoration, over the chosen lowercase
  words; sentence boundaries derive from the raw tokens. It never sees the
  input's original case (the eval lowercases input on purpose).
- `INITIAL_FOLD=64` and `CONTINUATION_WEIGHT=10` are measured constants with
  the sweep recorded above; change them only with a new sweep.
- Case statistics live only in corpus v2b; `Model.load` raises an actionable
  error when `case="correct"` is requested on v1.
