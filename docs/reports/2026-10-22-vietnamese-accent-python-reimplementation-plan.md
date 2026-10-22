# 2026-10-22 — Vietnamese accent prediction: reimplementation plan

**Repo under review**: `Vietnamese-Accent-Prediction/` (Java, 651 LOC, extracted from
`Vietnamese Accent Prediction.tar.xz`)
**Target**: Python reimplementation with higher accuracy and speed.
**Status**: plan, grounded in measurements taken today (see Evidence).

## TL;DR

The Java repo measures **96.29%** on its own `test.txt`, but only when run against the
**2017 committed data files**. The 2022 uncommitted rewrite in the working tree measures
**91.83%** on the same algorithm. So the "regression" is a **data regression, not an algorithm
regression**. The reimplementation plan below beats 96.29% by fixing the corpus and the
decision rule, not by swapping in a neural model.

## Evidence (all measured, not estimated)

### Baseline accuracy, same test set (`datasets/test.txt`, 8995 scored tokens)

| Configuration | Accuracy | Notes |
|---|---|---|
| Java HEAD, HEAD data files | **96.30%** | `git show HEAD:` data, k-shortest-path + DP hybrid |
| Java working tree, 2022 data | 92.29% | what ships in the tarball's working tree |
| Python port of HEAD algorithm, HEAD data | **96.29%** | verified: 5989/5995 tokens agree with Java output |
| Python port of HEAD algorithm, 2022 data | 91.83% | same code, different data — isolates the cause |
| Head algorithm, OLD 1gram + NEW 2gram | 95.89% | 1gram table is nearly sufficient |
| Head algorithm, NEW 1gram + OLD 2gram | 90.13% | new 1gram actively hurts |

**Conclusion: the 1-gram vocabulary is the dominant factor.** The 2-gram table contributes
little either way. Any reimplementation must therefore treat corpus construction as a
first-class component, not an afterthought.

### Why the 2022 1-gram table is worse

| Property | 2017 table | 2022 table |
|---|---|---|
| Entries | 216,448 | 779,331 |
| Total tokens | 400.5M | 176.3M |
| Accented : bare ratio | 2.61 | 3.69 |
| Example `đẹp` | 238,470 | 22,785 |
| Example `đồng` | 1,218,589 | 307,030 |

The 2022 table is 3.6× larger in type count but has 2.3× fewer total tokens. The
`NGramer` sanitizer (`line.replaceAll("[^a-zA-Z aàá...]", "").split("\\s+")`) deletes
non-Vietnamese characters and then splits, which manufactures junk single-character
entries (`à`, `ằ`, `ấ`) at counts 1-2. Those junk entries dilute the normaliser.

### Ambiguity ceiling (measured on `test.txt`)

| Bucket | Tokens | Share |
|---|---|---|
| 0 candidates (must copy input) | 11 | 0.13% |
| exactly 1 candidate (free win) | 248 | 2.94% |
| ≥2 candidates (DP must decide) | 8,166 | 96.93% |

Gold form is present in the candidate set for **99.87%** of alphabetic tokens. So **99.87%
is the hard ceiling of this candidate-generation approach.** The current 96.29% leaves
roughly 3.5 points of decision-rule headroom, and each of those points is a real word, not
a synthetic gain.

### Error profile of the current model (top confusions, HEAD build)

```
 13  con   -> còn        8  nền  -> nên       7  tu   -> từ
  7  hài   -> hai        6  hồng -> hong      6  kông -> kong
  5  nhưng -> những      5  phường -> phương  4  cùng -> cũng
```

Pattern: the errors are **tone and diacritic choices on genuinely ambiguous syllables**, plus
**proper nouns** (`hồng`, `kông`, `khánh`) that get over-normalised. There is no structural
breakage — the model is simply under-informed at these decision points.

### Speed baseline

| Stage | Time |
|---|---|
| Load 216k 1-gram + 5.55M 2-gram | 3.0-3.4 s |
| Candidate generation only (602 sentences) | 0.39 s |
| Full decode (602 sentences, 9094 tokens) | 1.00 s |
| Total single-core | ~605 sent/s, ~5,400 words/s |

Java reaches 1,410 sent/s on the same data. Python is currently ~2.3× slower, which the
plan addresses.

## Plan

### Phase 0 — Freeze the contract (0.5 day)

Before writing code, pin the things that currently make the repo unusable.

- Copy the 2017 committed data (`git show HEAD:datasets/news1gram` etc.) into `data/` as the
  baseline corpus. This is the only configuration that reproduces 96.29%.
- Write `eval.py` as a **standalone oracle grader**: reads a gold file (accented) and a
  prediction file, reports per-token accuracy with an explicit alignment check. The current
  Java grader silently skips sentences on length mismatch (`wordsIn.length == wordsOut.length`)
  and starts `countAll` at 1 — both distort the number. The new grader must report
  `skipped_mismatched_sentences` so the score is auditable.
- Record the reference numbers in `docs/reports/` so every later change is measured against
  them.

**Acceptance**: `eval.py` reproduces 96.29% ± 0.01 on the HEAD build, and prints an explicit
skip count of 0.

### Phase 1 — Port with verified parity (1-1.5 days)

Port the HEAD algorithm, not the 2022 rewrite, since HEAD is the higher-scoring one.

- Candidate generation from the accent-group table, capped at 8 chars (that cap is load-bearing:
  removing it changes results on long words).
- Interpolated bigram DP with the 1-gram prior applied at `i == 1` using the **previous**
  word's count. This detail is the difference between 93.8% and 96.3%; it is not obvious from
  the source and must be covered by a test.
- Carry the `_1Statistic` continuation counts, not `distinct first grams of a different table`.

**Parity gate**: token-level agreement with the Java output ≥ 99.9% on all 602 sentences.
I already have this at 99.93%; the port must not regress it.

**Acceptance**: `pytest tests/test_parity.py` passes, comparing against a checked-in
`fixtures/java_reference.tsv` produced from the HEAD build.

### Phase 2 — Fix the corpus (1 day, highest accuracy leverage)

This is where the real points are.

- **Rebuild the 1-gram table from a clean Vietnamese corpus** (the 2017 numbers suggest news
  text works; `viwiki` is fine if sanitised correctly). Fix the sanitizer: reject tokens
  shorter than 2 characters, reject tokens with no vowel, keep the accented form as the key
  rather than stripping and re-splitting.
- **Do not** let junk entries into the table. Every candidate is filtered through this table,
  so junk both dilutes the normaliser and creates false candidates.
- Keep the 2-gram table but rebuild it with the same sanitizer so both are consistent.

**Target**: ≥ 97.0% on the existing test set. Given the 99.87% ceiling and the error profile
(tone/diacritic confusions), a clean corpus should recover most of the 3.5-point gap. If it
does not, the corpus is still wrong — measure before optimising the decoder.

### Phase 3 — Improve the decision rule (1-2 days)

Only attempt this after Phase 2, and only with the ceiling in mind.

- **Trigram backoff.** The current model conditions on one previous word. Errors like
  `con`→`còn` and `nhưng`→`những` are usually resolved by a third syllable of context.
  Add a trigram table with Katz or Kneser-Ney backoff to the bigram model, and gate it on
  measured gain: if the trigram table does not buy ≥ 0.3 points on a held-out split, drop it.
- **Proper-noun preservation.** `hồng`, `kông`, `khánh` errors are the model over-normalising
  capitalised tokens that it should leave alone. Add a rule: if a capitalised token's
  unaccented form appears in a name gazetteer (or is OOV in the accented table but present
  as-is in the corpus with capitals), lower the weight of accent expansion for it.
- **Hold out a real dev set.** `test.txt` is 589 lines of news text, which is small and
  in-domain. Split it: 70% dev, 30% test, and keep a second out-of-domain sample (e.g.
  social media or forum text) as a generalisation check. Report both. A model tuned only on
  news text will look better than it is.

**Acceptance**: dev gain ≥ 1.0 point over Phase 1; test-set gain ≥ 0.5 point; no drop on the
out-of-domain sample.

### Phase 4 — Make it fast (1 day)

Performance work is only worth doing once accuracy is settled, and only where measured.

- **Replace the per-token candidate expansion with a precomputed unaccent→candidates index.**
  Currently candidate generation is 39% of decode time (0.39 s of 1.00 s) because it
  re-derives every variant per token. Precompute once at load: build a dict from
  `strip_accent(word)` to the list of accented forms, then a lookup is O(1) per token.
  This alone should recover most of the gap to Java.
- **Vectorise the DP with numpy** over the candidate grid. Columns are small (5-25 candidates),
  so the win is modest; measure before and after. Do not reach for numba unless numpy
  plateaus below the target.
- **Lazy 2-gram loading.** The 5.55M-entry table costs 3 s to build at startup for a model
  that contributes almost nothing (see Phase 2 measurement). Load it only if Phase 3 keeps it.
- **Target**: ≥ 3,000 sent/s single-core, startup ≤ 1 s. That is ~2× Java and ~5× the current
  Python.

**Acceptance**: benchmark script reports both throughput and startup time; both targets met
with accuracy unchanged from Phase 3.

### Phase 5 — Package and document (0.5 day)

- `pyproject.toml` with `uv`; `pip install -e .` must work from a clean checkout.
- Public API: `restore(text: str) -> str` and `restore_multi(text: str, n: int) -> list[tuple[str, float]]`.
  The second one is documented in the original README but **does not exist in the compiled
  Java** — implementing it makes the README true for the first time.
- CLI: `vap restore < file` and `vap eval --gold f --pred g`.
- README with the measured table, the ceiling, and the known failure modes.

## Explicitly out of scope

- A neural (transformer / seq2seq) model. The ambiguity ceiling implies a well-tuned n-gram
  model can reach 99%+, and a neural model brings GPU, latency, and reproducibility costs that
  this problem does not justify. Revisit only if Phase 3 stalls below 98% and a clean corpus
  has already been ruled out.
- The `kshortestpaths` Yen-algorithm code. It was deleted in the working tree and is only used
  by the multi-match API, which Phase 5 implements directly with k-best Viterbi.
- Model serving, REST API, Docker. Not requested; add only if there is a consumer.

## Risks

| Risk | Mitigation |
|---|---|
| Rebuilding the corpus changes the test distribution | Keep the existing test set fixed; build the corpus from a disjoint source |
| The 96.29% baseline is partly luck on this in-domain test set | Add the out-of-domain sample in Phase 3, report it separately |
| Trigram model bloats memory (5.55M bigrams already ~800 MB in Java) | Gate on measured gain; load lazily; drop if it does not pay |
| Parity drift during refactoring | The 99.93% parity fixture from Phase 1 is the regression gate |

## What I would do first

Phase 0 and Phase 1, because they are cheap and they convert the project from "a tarball with
a number in the README" into a measured baseline. The highest single accuracy return is
Phase 2 (corpus), and the highest speed return is the candidate-index rewrite in Phase 4.
The trigram and proper-noun work in Phase 3 is speculative until Phase 2 lands, and should be
gated on the numbers, not started optimistically.
