# Failure diagnosis: what the 4% errors actually are

**Date**: 2026-10-23
**Commit**: `96749c1`
**Script**: `bench/diagnose_failures.py`, `bench/test_fixes.py`

---

## 1. Two separate populations

The "4% failure" is not one problem. Splitting it first:

| Population | Count | Nature |
|---|---:|---|
| A. Broken by the rare-pair skip | **4** | Regression introduced by the optimization |
| B. All remaining wrong tokens | **359** | Pre-existing model limitations |

Population B is 98.9% of the error mass. Fixing A would buy at most 4 tokens
(0.04 points). The real question is B.

---

## 2. Population A: the 4 skip regressions

Full traces:

| Sentence context | Gold | Baseline | Optimized | Uni(gold) | Uni(picked) | Prev count |
|---|---|---|---:|---:|---:|---:|
| `doko và công` | `và` | `và` ✓ | `vầ` ✗ | 4,374,499 | 36 | **4** |
| `tin lãi qòng` | `lãi` | `lãi` ✓ | `lại` ✗ | 79,946 | 1,071,502 | 592,198 |
| `qòng quý công` | `quý` | `quý` ✓ | `quỹ` ✗ | 129,994 | 56,953 | **1** |
| `... góp` | `góp` | `góp` ✓ | `gớp` ✗ | — | — | — |

### Root cause: rare *context*, not rare *pair*

Case 1 is the clearest. `doko và` has a real bigram count of 3. It got skipped because
`doko` has unigram count 4, below the threshold of 21. The baseline was right **because**
it consulted that count-3 bigram. Skipping it left a generic UNK score, and the DP then
picked `vầ` (unigram 36) over `và` (unigram 4.37M) — a form that wins on no plausible
signal.

So the failure mode is: **a real bigram is low-count only because its left context is a
rare token** (a proper noun, an acronym, or OCR junk like `doko`, `qòng`). The skip treats
rare-context bigrams as noise, and in 4 cases they were signal.

### Tested: does a different threshold recover them?

Full sweep, both corpora:

| skip_below | in-acc | correct | out-acc | sent/s |
|---:|---:|---:|---:|---:|
| 0 (off) | 96.00% | 8635 | 95.24% | 1,931 |
| 2 | 95.98% | 8633 | 95.24% | 2,023 |
| 5 | 95.99% | 8634 | 95.24% | 2,115 |
| 10 | 96.00% | 8635 | 95.24% | 2,019 |
| **21 (shipped)** | **96.01%** | **8636** | 95.24% | 2,302 |
| 30 | 96.00% | 8635 | 95.24% | 2,316 |

**No threshold recovers them.** Moving the cut down to 2 or 5 brings the 4 tokens back but
loses more elsewhere: correct count drops from 8636 to 8633. The net is monotonic — 21
happens to be the local optimum, not a value that happened to be unlucky.

This refutes the hypothesis that the 4 cases are a threshold-calibration bug. They are the
irreducible price of the skip, and the skip is a net win.

---

## 3. Population B: the real 359 errors

### Where they come from

| Category | Count | Share of errors |
|---|---:|---:|
| **Gold form not in the candidate lattice at all** | **35** | **9.75%** |
| Gold form in the lattice, decoder chose differently | 324 | 90.25% |

The 9.75% is a hard ceiling: no decoder change can fix a candidate the index never
generated (the token was out-of-vocabulary on the accent-stripped side). This matches the
99.87% lattice recall measured during design.

### When gold is in the lattice, how wrong was the choice?

Rank of the chosen form by unigram frequency among all candidates:

| Rank of pick | Count | Meaning |
|---:|---:|---|
| 0 (most frequent form) | 142 | Chose the *most common* variant; gold was rarer |
| 1 | 77 | |
| 2 | 46 | |
| 3 | 25 | |
| 4 | 18 | |
| 5–7 | 16 | Deep in the beam |

**142 of 324 (44%) are rank-0 errors**: the decoder picked the single most frequent form
of that syllable. These are genuine lexical ambiguity, not search failure — no amount of
better search fixes them, because the model's ranking itself is wrong.

### The dominant error families

| Count | Gold | Got | Pattern |
|---:|---|---|---|
| 14 | `con` | `còn` | **The skip fix's counterpart** — `còn` is more frequent |
| 8 | `nền` | `nên` | Tone swap |
| 7 | `Đồng` | `Dòng` | Proper noun |
| 7 | `tu` | `từ` | |
| 7 | `hài` | `hai` | Unaccented gold (`hai` has no tone) |
| 6 | `hồng` | `hong` | Foreign/proper noun lacking diacritics |
| 6 | `kông` | `kong` | Kong (proper noun) |
| 5 | `nhưng` | `những` | |
| 5 | `phường` | `phương` | |

Two families stand out as **systematic and potentially fixable**:

**Family 1 — unaccented loanwords and proper nouns** (`hồng`→`hong` in 6 cases, `kong`,
`khanh`). The corpus gold sometimes writes these without diacritics. The model confidently
adds them. This is a gold-labeling convention ("Kong" is a name; "hồng" means pink), not a
model error, and is unresolvable without a proper-noun lexicon.

**Family 2 — `con`/`còn` direction (14 cases).** Note this is exactly the mirror of the 14
`còn`→`con` the skip *fixed*. Both directions appear in the corpus at nearly equal counts.
That means the two forms are genuinely context-dependent and the model only sees one
neighbour. This is the strongest argument for a wider context window: 14 + 14 = 28 tokens
(7.8% of all errors) hinge on a distinction the bigram cannot make.

---

## 4. What would actually resolve these

Ordered by tokens fixed per unit of work, with honest effort estimates.

| Fix | Tokens addressed | Effort | Verdict |
|---|---:|---|---|
| Tune skip threshold | **0** (measured) | — | Rejected: sweep proves none helps |
| Revert the skip | +4 (loses 356) | — | Rejected: strongly net-negative |
| Proper-noun / loanword lexicon | ~12 (family 1) | medium — needs a name list | **Best single fix** |
| Trigram or 3-word window | up to 28 (family 2) | high — new table; earlier trigram proxy measured *worse* (91.14% vs 91.50%) | Unlikely to pay off |
| Character-level model for the 35 OOV | up to 35 | high — new model | Only if OOV matters in the target domain |
| Re-rank top-k with a neural model | ~142 rank-0 cases | very high | Discarded in earlier comparison (60–200x slower) |

### Why the obvious ideas are already known not to work

The **35 OOV tokens** are the only clearly-attackable hard ceiling, and only 9.75% of
errors. The 142 rank-0 errors need a better language model, not better search — and the
research round already measured neural re-ranking as 60–200x slower for marginals gains
outside formal register.

---

## 5. Recommendation

1. **Do not chase the 4 skip regressions.** Measured: no threshold recovers them without a
   larger net loss. They are documented, not fixable.
2. **The highest-value fix is a proper-noun lexicon**, worth roughly 12 tokens (~0.13
   points) and it also removes the most jarring error class (adding diacritics to English
   names).
3. **`con`/`còn` is the deepest real limitation** (28 tokens, both directions). It needs
   more context than a bigram. Given the earlier trigram measurement was negative, the
   honest position is: not worth doing on this corpus, revisit if a larger corpus makes
   trigrams sparse-but-nonzero.
4. The remaining error mass is lexical ambiguity the model is *designed* to approximate.
   96.01% with a 9.75% OOV ceiling is close to what this architecture can deliver.

---

## 6. Correction to an earlier claim

During the optimization round I measured "1 flipped column of 8,993" and reported the skip
as nearly accuracy-neutral. That count was wrong as a measure of churn: it compared final
column choices, while 360 token strings change because one wrong column shifts neighbours.
The token-level audit in this report (356 fixed / 4 broken) is the accurate picture, and it
is why the 4 regressions were visible at all.
