# Vietnamese diacritic restoration — algorithmic research notes

**Date**: 2026-10-22
**Question**: is there a better, more optimal approach than the current n-gram + Viterbi design?
**Companion**: `2026-10-22-vietnamese-accent-python-reimplementation-plan.md`

All accuracy numbers below are measured where marked "measured", and sourced where marked
"reported". Reported numbers are on different test sets and are not directly comparable.

---

## 1. What the problem actually is

Input: Vietnamese text with all diacritics stripped (`Toi yeu Viet Nam`).
Output: the original diacritized text (`Tôi yêu Việt Nam`).

The task has an important structural property that determines which algorithms work.

### Measured on the repo's own `test.txt` (8,425 alphabetic tokens)

| Bucket | Tokens | Share |
|---|---|---|
| 0 candidate forms in vocabulary | 11 | 0.13% |
| exactly 1 candidate form | 248 | 2.94% |
| 2+ candidate forms (ambiguous) | 8,166 | **96.93%** |

Mean candidate count per token: **11.6**. The gold form is in the candidate set 99.87% of
the time.

**Implication**: this is not a vocabulary-coverage problem, it is a *disambiguation* problem.
Almost every word has ~11 legal spellings and the model must pick one. That is why a
context-free lookup scores ~68% and a sequence model scores ~96%: the entire value is in the
sequence constraint.

### Measured: context is everything

| Decoder | In-domain `test.txt` | Out-of-domain benchmark |
|---|---|---|
| Unigram argmax (no context) | 69.39% | 67.57% |
| Bigram Viterbi, single grader | 91.50% | **91.12%** |
| Bigram Viterbi, repo's own grader | 96.29% | n/a |

Out-of-domain benchmark = `nom-vn` `diacritic_eval_v0` (55 sentences, 4 registers, CC0).

Two conclusions, and the second is uncomfortable:

1. **The decoder is everything.** Context-free lookup: ~68%. Bigram sequence model: ~91%.
   A 23-point gap from nothing but the sequence constraint.
2. **The 96.29% headline is a grader artefact, not a generalisation number.** Under one
   consistent grader the model scores 91.50% in-domain and 91.12% out-of-domain — the data
   distribution barely matters, but the metric does. The repo's grader starts `countAll` at 1
   and silently skips sentences on length mismatch, which inflates the figure by ~4.8 points
   relative to a clean per-token count.

So the honest baseline for any reimplementation is **~91.5%**, not 96.29%. Any plan that
adopts the repo's grader will report a number it cannot reproduce under a fair metric.

---

## 2. Published approaches, ranked by measured accuracy

| Approach | Reported accuracy | Speed | Source |
|---|---|---|---|
| Phrase-based MT (Moses) | 97.32% | 10 sent/s | arXiv 1709.07104 |
| Neural MT (OpenNMT, 2017) | 96.15% | 22 sent/s | arXiv 1709.07104 |
| CRF at syllable level | 93.8% | not reported | cited in 1709.07104 |
| SVM + n-gram features | 94.7% | not reported | cited in 1709.07104 |
| ViT5-base fine-tune | 89.97-99.52% (by register) | ~100-270 ms/sent | nrl-ai model card |
| BARTpho-syllable (+LoRA) | 89.40-97.81% (by register) | ~50-160 ms/sent | nrl-ai model card |
| GPT-4o-mini (cloud) | 95.37% (business only) | network-bound | nrl-ai model card |
| Rule-based only | 41.06% | instant | nrl-ai model card |

### The register effect is larger than the model effect

ViT5-base measured across four registers on the same benchmark:

| Register | ViT5-base | BARTpho-5th |
|---|---|---|
| formal / legal (72 sents) | **99.52%** | 98.14% |
| business / contracts (55) | 96.14% | **97.81%** |
| conversational (300) | **94.16%** | 93.94% |
| classical literary (800) | **89.97%** | 89.40% |

The spread between registers (9.5 points) is **larger than the spread between the two best
models on any register** (at most 1.7 points). Model choice is a second-order decision;
register coverage is first-order.

This is the most actionable finding in the whole survey: a system tuned to one register will
look excellent there and mediocre elsewhere, and no amount of model architecture fixes it.
The repo's 96.29% is measured on one register (news) only.

---

## 3. Where the current design is leaving accuracy

Measured error profile of the current model (`con`→`còn` 13×, `nền`→`nên` 8×,
`tu`→`từ` 7×, `hài`→`hai` 7×, `nhưng`→`những` 5×).

Three distinct causes, ranked by expected gain:

### 3.1 Corpus quality (largest, fully measured)

The 2017 1-gram table (216k entries, 400.5M tokens) yields 96.28%. The 2022 table
(779k entries, 176.3M tokens) yields 91.83% on the same algorithm. The 2022 table is
*bigger by type count and worse*: the `NGramer` sanitizer deletes non-Vietnamese characters
then splits, manufacturing junk 1-2 count entries that dilute the normaliser.

This is a data bug with a 4.45-point cost, already diagnosed. Fixing it is Phase 2 of the plan.

### 3.2 Context window too short (biggest algorithmic headroom)

Bigram conditions on one previous syllable. Vietnamese tone-assignment ambiguities are
frequently resolved by the *following* syllable, not the preceding one. Look at the actual
errors:

- `nhưng` → `những`: the following classifier/noun decides it (những người, nhưng mà)
- `nền` → `nên`: resolved by whether a noun follows
- `tu` → `từ`: resolved by the following verb/time marker

A bigram LM is structurally blind to this. Trigram (or bigram over *words* rather than
syllables) captures it.

**Proposed experiment**: build a trigram table, apply Kneser-Ney backoff to the existing
bigram, and gate on measured gain. Expected +1 to +2 points. Cheap to test, cheap to run at
inference if the DP stays in the same shape.

### 3.3 Word segmentation, not syllable segmentation (underrated)

Vietnamese is written with syllables separated by spaces, but the lexical unit is the
*word* (`học sinh`, `công ty`, `đồng ý`). The current model treats each syllable
independently with a bigram, which is a weak proxy for word identity.

Published work on Vietnamese diacritics explicitly compares letter-based, syllable-based, and
**word-based** models and finds word features help. A word segmenter (SVM with n-gram
features reaches high F1 on standard benchmarks; `nom-vn` ships one) would let the LM score
whole-word identity instead of syllable pairs.

**Proposed experiment**: segment, then score candidate *word* sequences with a word-level
LM. Higher complexity, real potential. This is the main non-obvious algorithmic idea in this
survey that the plan does not yet include.

### 3.4 Proper-noun preservation (small but cheap)

`hồng`→`hong`, `kông`→`kong`, `khánh`→`khanh` are the model over-normalising names.
A capitalisation-aware prior plus a name gazetteer should fix most of these at near-zero
cost.

---

## 4. What NOT to do

### Neural seq2seq is the wrong trade here

Measured benchmarks put ViT5-base at 89.97-99.52% depending on register, i.e. **not better
than a phrase-based MT system from 2017** (97.32%) on comparable text, and dramatically
slower:

| | Accuracy | Speed |
|---|---|---|
| Bigram Viterbi (current) | 96.29% | 1,410 sent/s (Java), 605 (Python) |
| Neural MT (2017, Tesla K80) | 96.15% | 22 sent/s |
| ViT5-base (2024, model card) | 96.14% business | ~146 ms/sent ≈ 7 sent/s |

A neural model is **60-200× slower** for roughly the same accuracy on business/news text.
It only wins on conversational text (94.16% vs an unknown bigram number) and on literary
text it is worse than the 2017 MT system (89.97% vs 89.40%, basically tied).

**Conclusion**: do not replace the n-gram decoder with a neural one. The accuracy ceiling of
the n-gram approach (99.87%) is above every neural number reported here except the formal
register, and the speed advantage is two orders of magnitude.

### Do not chase the 96.29% → 99% gap with a bigger model

The remaining ~3.5 points are concentrated in genuinely ambiguous syllables. To close them
you need more context (trigram/word-level) and better corpus coverage, not more parameters.

### GPT-4o-mini at 95.37% is not a shortcut

It is below the existing system, network-bound, non-deterministic, and costs money per token.

---

## 5. Recommended experiment order

Each step is gated on a measurement, and each is cheaper than the next.

| # | Experiment | Expected gain | Cost | Gate |
|---|---|---|---|---|
| 1 | Fix the grader (fair per-token metric) | 0 (reveals −4.8 illusion) | 0.5 day | numbers reproducible by hand |
| 2 | Add the out-of-domain benchmark to CI | 0 (prevents self-deception) | 0.5 day | report both registers |
| 3 | Fix the corpus (Phase 2 of plan) | +4.4 (measured) | 1 day | ≥+3 on both graders |
| 4 | Trigram + KN backoff | +1 to +2 | 1 day | ≥+0.3 measured, else drop |
| 5 | Proper-noun + capitalisation prior | +0.3 to +0.8 | 0.5 day | no regression on news |
| 6 | Word-segmentation + word-level LM | unknown, potentially large | 3-5 days | beat trigram result |
| 7 | Hybrid: n-gram first pass + neural re-rank of top-k | unknown | 2 days | beat n-gram alone, <50 ms/sent |

Steps 1 and 2 matter more than they look. The 96.29% headline is inflated by the repo's own
grader arithmetic, and every published number in section 2 is register-dependent. Without a
fair, two-register measurement, a change that "gains 2 points" may only be moving the metric.

Step 7 is the only place a neural model is worth considering: as a **re-ranker over the
n-gram's top-k candidates**, not as a replacement decoder. That preserves the 99.87%
recall of the candidate generator and the speed, and only spends neural compute on the
~11-way ambiguity that actually needs it.

---

## 6. Direct answer

Yes, there is a better design, and it is not a different model family:

1. **Keep** syllable-candidate generation + Viterbi. It is the right shape for this problem,
   it has a measured 99.87% recall ceiling, and it runs at ~1,400 sent/s.
2. **Fix the metric first** — measured 4.8-point inflation from the repo's own grader. Every
   decision below depends on having a trustworthy number.
3. **Fix the corpus** — measured 4.45-point loss from the 2022 data rebuild.
4. **Lengthen the context** — trigram or word-level, because the observed errors are
   structurally beyond a bigram's reach.
5. **Segment into words, not syllables** — the largest unexplored idea, and the one the
   published letter-vs-syllable-vs-word comparison points at.
6. **Do not replace the decoder with seq2seq** — 60-200× slower for equal or worse accuracy
   outside the formal register.

Ranked by expected value: the **metric fix** (#2) is highest and costs half a day, because
without it every other measurement is suspect. The corpus fix (#3) is the largest accuracy
lever. The highest-value *algorithmic* change is #5 (word-level modelling), which neither the
original repo nor the current plan includes.

---

## Sources

- Pham et al., *On the Use of Machine Translation-Based Approaches for Vietnamese Diacritic
  Restoration*, arXiv:1709.07104 (IALP 2017) — phrase-based 97.32%, neural 96.15%, speeds.
- `nrl-ai/vn-diacritic-vit5-base` and `nrl-ai/vn-diacritic-small` model cards — 4-register
  accuracy matrix, cross-model comparison table, ms/sentence.
- `nrl-ai/vn-diacritic-eval` dataset (CC0) — reproducible 4-register eval set, 55/72/300/800
  sentences.
- `nrl-ai/nom-vn` repository — open benchmark harness, eval data, segmenters.
- *Vietnamese Diacritics Restoration as Sequential Tagging*, IEEE RIVF 2012.
- *Diacritics Restoration in Vietnamese: Letter Based vs. Syllable Based Model*, Springer.
- *Vietnamese Word Segmentation with SVM*, arXiv:2006.07804.
- Internal measurements: `head_port.py` port verified at 99.93% token parity with the Java
  build; corpus ablation and decoder ablation tables above.
