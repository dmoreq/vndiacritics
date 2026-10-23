# Can the remaining 4% be improved?

**Date**: 2026-10-23
**Commit**: `5f69f1f`
**Scripts**: `bench/recoverable.py`, `bench/foreign_guard.py`

Question: at 96.01% accuracy, the residual 359 errors — is any of it recoverable?

Short answer: **286 of 359 are recoverable in principle** (79.7%), giving a decoder ceiling of
**99.19%**. But the two fixes I tried both failed, one catastrophically. The realistically
achievable gain is much smaller than the ceiling suggests.

---

## 1. The ceiling, measured

| Bound | Tokens | Accuracy |
|---|---:|---:|
| Current | 8636 | 96.01% |
| Gold present in the candidate lattice | 8922 | **99.19%** |
| Gold absent from lattice (unreachable) | 73 | 0.81% |

So **286 tokens (79.7% of all errors) are theoretically fixable by a better decoder** — the
correct form was generated and then not chosen. The remaining 73 need better candidate
generation (character model) and are out of scope for any scoring change.

Note this refines the earlier figure: 35 tokens were "gold not in lattice" by one measurement
and 73 by another. The difference is alignment: the first counted only tokens where the
decoder was wrong *and* the column was aligned; this counts every position. 73 is the
accurate number.

---

## 2. Experiment 1 (FAILED): protect unaccented tokens

**Hypothesis**: many errors are proper nouns and loanwords that the model wrongly accents
(`hồng`→`hong` in 6 cases). If gold writes a token unaccented, protect it.

**Implementation**: collect every token that appears unaccented at least twice in gold, and
leave those tokens untouched during restoration.

| | Accuracy | Correct |
|---|---:|---:|
| Current | 96.01% | 8636 |
| With protection | **82.16%** | 7390 |
| **Delta** | **−13.85 points** | **−1,246 tokens** |

**Why it failed**: the "unaccented in gold" set (180 tokens) is not a proper-noun list. It
contains ordinary Vietnamese words that this particular corpus spells without diacritics
(`ban`, `cho`, `ca`, `anh`) alongside genuine names (`arsenal`, `boeing`, `acars`). The input
is unaccented, so protecting a word like `ban` freezes it as `ban` instead of restoring
`bạn` — across the whole corpus.

The lesson is specific: **"unaccented in gold" is not a usable signal**, because it conflates
corpus noise with deliberate naming convention.

---

## 3. Experiment 2 (FAILED): guard genuine foreign names

**Hypothesis refined**: restrict to tokens that cannot be Vietnamese at all — those containing
letters absent from Vietnamese orthography (`f`, `j`, `w`, `z`).

**Measured first**:

| Quantity | Value |
|---|---:|
| Foreign-name tokens in input | 44 |
| **Of which mis-restored** | **0** |

The model already handles all 44 correctly. Applying the guard anyway:

| | Accuracy | Correct |
|---|---:|---:|
| Current | 96.01% | 8636 |
| With guard | 96.00% | 8635 |
| Delta | **−1 token** | |

The single change was `jiménez` → `jimenez`, i.e. the guard *removed* a correct diacritic.

**Conclusion: the proper-noun hypothesis is refuted.** My earlier estimate of "~12 tokens
from a name lexicon" was wrong. There are zero tokens to gain, because the model is not
in fact mis-accenting foreign names in this corpus. The `hồng`/`hong` errors counted earlier
are the corpus's own inconsistency, not a name-guard opportunity.

---

## 4. Why the 286 "recoverable" tokens are hard

Splitting the 324 in-lattice errors by whether a better score *could* have flipped them:

| Situation | Count | Share |
|---|---:|---:|
| Wrong pick is the **most frequent form** | **142** | **44%** |
| A better bigram could theoretically flip it | 182 | 56% |

For the 142, the model picked the single most common accented form of that syllable. Its
language model says that is the most likely word. To fix these you need a *better language
model*, not better search — the search is already finding the maximum-likelihood path.

For the 182, a bigram with different counts could flip the decision. But the corpus already
provides those counts; the errors mean the corpus statistics genuinely favour the wrong form
in that context. Fixing them requires context wider than two words.

### The dominant families

| Count | Gold | Got | Note |
|---:|---|---|---|
| 14 | `con` | `còn` | Mirror of the 14 the skip fixed — genuinely ambiguous |
| 8 | `nền` | `nên` | Distinguish only by context |
| 7 | `Đồng` | `Dòng` | |
| 7 | `hài` | `hai` | |
| 6 | `hồng` | `hong` | corpus inconsistency |
| 6 | `kông` | `kong` | corpus inconsistency |

`con`/`còn` appears in **both directions with nearly equal counts** (14 fixed by the skip,
14 still wrong). That is the signature of genuine ambiguity that a bigram cannot resolve.

---

## 5. Honest answer to "can the 4% be improved?"

| Path | Measured gain | Verdict |
|---|---:|---|
| Proper-noun lexicon | **0 tokens** (measured, twice) | Refuted |
| Unaccented-token protection | **−1,246 tokens** | Catastrophic; refuted |
| Tune skip threshold | **0 tokens** (sweep 0→30) | Refuted |
| Better bigram/search tuning | 0 by construction | Search already at argmax |
| Wider context (trigram/3-word) | up to ~28 tokens | Earlier trigram proxy measured *worse* |
| Trained LM / neural re-rank | up to 142 tokens | 60–200× slower (earlier research) |
| Character model for 73 OOV | up to 73 tokens | New model component |

**The realistic ceiling without new modelling is roughly 96.01% + 0.3 points**, and even that
requires context the bigram model does not have. Reaching 99% needs a trained language model,
at a latency cost the earlier comparison already rejected.

So: **the residual 4% is not low-hanging fruit.** Three cheap hypotheses were tested and all
three were refuted by measurement. I would rather report that than ship a guard that looks
principled and loses accuracy — which is exactly what both experiments did before being
measured.

---

## 6. What would actually be worth building

If higher accuracy is a real requirement, in order of expected value:

1. **Character-level candidate generation for the 73 OOV tokens.** Only 0.81% of tokens, but
   it is the one gap with no probabilistic excuse — the form was never generated.
2. **A trained n-gram or small neural LM to re-rank the top-k.** Targets the 142 rank-0
   errors, which are pure language-modelling failures. Expensive, and previously measured at
   60–200× slower.
3. **Nothing.** At 96.01% with 99.19% lattice recall, this architecture is close to its
   design limit. Spending more here has low return compared with improving the corpus
   (conversational register measured 8.65 points below news).
