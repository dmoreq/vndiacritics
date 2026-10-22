# Vietnamese diacritic restoration — approach comparison and recommendation

**Date**: 2026-10-22
**Scope**: compare every viable approach on accuracy, storage, latency, and complexity,
then pick the one that balances them.
**Companions**: [plan](2026-10-22-vietnamese-accent-python-reimplementation-plan.md),
[algorithm research](2026-10-22-vietnamese-diacritic-algorithm-research.md)

All accuracy figures marked "measured" were run today on this machine on a single
consistent grader. Figures marked "reported" come from model cards or papers and are
**not** directly comparable across rows.

---

## 0. The measurement that reframes everything

Before comparing approaches, here is what the data actually contains.

| Property (repo `test.txt`, in-domain) | Value |
|---|---|
| Alphabetic tokens | 8,425 |
| Mean candidate forms per token | 11.6 |
| Gold form present in candidates | 99.87% |
| Tokens missing from the 1-gram table | 4.1% |
| **Bigrams present in the 2-gram table** | **19.1%** |
| **Adjacencies falling back to the UNK penalty** | **80.9%** |

**81% of the time the bigram model has no observed context.** It falls back to a constant
UNK penalty — but that penalty is itself highly informative: it strongly penalises
candidate pairs that were never observed together, which is exactly the discrimination a
context-free model cannot make.

Measured cost of removing the 2-gram table entirely:

| Configuration | Accuracy (in-domain) |
|---|---|
| Bigram Viterbi **with** 2-gram table | **91.50%** |
| Same decoder, **without** 2-gram table | 71.57% |
| | **−19.93 points** |

So the sparse table is not dead weight: even when 81% of adjacencies trigger the UNK path,
the model still gains ~20 points over no context at all. The UNK fallback is doing real
discriminative work, because most incorrect candidates are unobserved *pairs* while the
correct candidate usually is observed.

Corollary: adding a higher-order model to this data cannot help much, because the trigram
coverage is even sparser (see §5). The bottleneck is corpus density, not model order — but
do **not** read that as "the bigram table is unnecessary". It is load-bearing.

---

## 1. Accuracy, measured on one grader

In-domain = repo `test.txt` (589 news sentences, 9,085 scored tokens).
Out-domain = `nom-vn` `diacritic_eval_v0` (55 sentences, 4 registers, CC0).

| Approach | In-domain | Out-domain | Notes |
|---|---|---|---|
| Unigram argmax (order-0) | 71.57% | 71.43% | no context at all |
| **Bigram Viterbi (order-1, repo)** | **91.50%** | **90.99%** | the current design |
| Trigram-proxy (order-2, backoff) | 91.14% | 90.60% | **worse**, see §5 |
| Quoted repo number (own grader) | 96.29% | n/a | inflated 4.8 pts by grader math |

Reported by others (different data, do not compare rows):

| Approach | Reported accuracy |
|---|---|
| Phrase-based MT (Moses) | 97.32% |
| Neural MT (OpenNMT, 2017) | 96.15% |
| ViT5-base fine-tune | 89.97 – 99.52% (by register) |
| BARTpho-syllable fine-tune | 89.40 – 97.81% (by register) |
| GPT-4o-mini | 95.37% (business only) |
| Rule-based lookup | 41.06% |

**Accuracy spread across registers exceeds the spread across models.** ViT5-base ranges
9.5 points across registers while the top two models differ by at most 1.7 points on any
single register. Register coverage dominates model choice.

---

## 2. Storage, measured

| Artifact | On disk | In RAM after load |
|---|---|---|
| `news1gram_viwiki.tsv` (779k entries) | 9.0 MB | ~120 MB as Python dict |
| `news2grams_viwiki.tsv` (4.62M entries) | 71 MB | ~500 MB as Python dict |
| Accent table `AccentInfo.tsv` | 426 B | negligible |
| **Total, current design** | **80 MB** | **~660 MB** |
| Candidate index (derived, optional) | — | +112 MB |
| **Same 2-gram table as a marisa-trie (measured)** | **19 MB** | **19 MB, 0.0 s load** |
| ViT5-base weights | 904 MB | ~1.1 GB fp32, ~300 MB int8 |
| BARTpho-syllable (`vn-diacritic-small`) | ~460 MB | ~550 MB fp32 |
| A real trigram table | est. 700 MB – 1.5 GB | est. 4-6 GB |

The marisa-trie row is measured, not estimated: I built it from the same 4,622,847 bigrams,
saved it (19.0 MB), and reloaded it in a fresh process — **19 MB of RAM and a sub-millisecond
load, versus 500 MB and 1.6 s for the Python dict holding identical information.**

That is a 26× RAM reduction and a ~1,600× faster startup, for the same model, no accuracy
change, one dependency. It is the single best storage/latency decision available and it does
not require touching the algorithm at all.

Note the shape of that last row: a trigram table over this corpus would cost more RAM than
most machines want to give a diacritic restorer, and §0 says it would not even help.

**The 2-gram table is 89% of storage, and it is earning every byte.** It contributes ~20 of
the 91.5 points. An earlier draft of this report claimed it was dead weight on the grounds
that 81% of adjacencies hit the UNK path; measurement disproved that. The storage cost is
real and unavoidable for this accuracy level; the way to shrink it is a better data structure
(see §7), not removing the model.

---

## 3. Latency, measured

Fixed workload, single core, Python 3.13 on Apple M3.

| Approach | ms/sentence | sentences/s | Startup |
|---|---|---|---|
| Unigram argmax | 0.02 | 44,900 | 0.2 s |
| **Bigram Viterbi** | **0.65** | **1,543** | 1.8 s (incl. 71 MB table) |
| Trigram-proxy | 3.40 | 294 | ~1.8 s |

Reported by others:

| Approach | Latency |
|---|---|
| Neural MT (2017, Tesla K80) | 22 sent/s (~45 ms) |
| ViT5-base (model card) | ~102-273 ms/sent |
| BARTpho-small (model card) | ~48-117 ms/sent |
| GPT-4o-mini | network-bound, ~500-2000 ms |

The bigram design is **1.5–7× faster than the fastest neural option and 60–200× faster
than a transformer at worst-case register**, on CPU, with no GPU.

---

## 4. Complexity comparison

| Approach | Implementation effort | Lines of code | New deps | Ops burden | Debuggability |
|---|---|---|---|---|---|
| Rule-based lookup | trivial | ~50 | none | none | trivially obvious |
| Unigram argmax | trivial | ~40 | none | none | trivially obvious |
| **Bigram Viterbi** | moderate | ~250 | none | none | inspectable scores |
| Trigram + KN | high | ~500 | none | none | hard, sparse counts |
| CRF (syllable) | high | ~600 | sklearn-crfsuite | none | learned weights, opaque |
| SVM (syllable features) | high | ~700 | sklearn | none | feature engineering |
| A-TCN / BiLSTM | very high | ~1500 + training | torch | training pipeline | black box |
| ViT5/BARTpho fine-tune | very high | ~2000 + training | transformers, torch | GPU, model registry, drift | black box |
| GPT-4o-mini | low code, high ops | ~100 | API client | network, cost, PII, rate limits | black box + non-deterministic |

The two options that score well *and* stay simple are bigram Viterbi and rule-based lookup.
Everything above the bigram row costs one to two orders of magnitude more engineering for
accuracy it cannot demonstrate on this data (§0).

---

## 5. Why the trigram attempt failed (measured, not assumed)

I implemented an order-2 decoder and ran it. It scored **91.14% in-domain, below the
bigram's 91.50%**, and was 5× slower.

The cause is visible in §0: at 69% of trigram positions, *neither* adjacent bigram exists in
the table. A trigram model has no signal to condition on. The proxy bonus term then adds noise
instead of information, and accuracy drops.

| Trigram coverage on `test.txt` | Share |
|---|---|
| both adjacent bigrams present (trigram has signal) | 6.9% |
| one adjacent bigram present | 24.0% |
| neither present (no signal possible) | 69.0% |

**Conclusion: do not build a trigram model against this corpus.** Revisit only after the
corpus is rebuilt to several times its current density. This overturns the trigram
recommendation I made in the research note.

---

## 6. Decision matrix

Scores 1-5, higher is better, except Effort where higher is worse.

| Approach | Accuracy | Storage | Latency | Simplicity | Ops | **Balance** |
|---|---|---|---|---|---|---|
| Rule-based lookup | 1 | 5 | 5 | 5 | 5 | 21 |
| Unigram argmax | 2 | 4 | 5 | 5 | 5 | 21 |
| **Bigram Viterbi** (dict) | **4** | **3** | **5** | **4** | **5** | **21** |
| **Bigram Viterbi (trie)** | **4** | **5** | **5** | **4** | **5** | **23** |
| Trigram + KN | 3 (measured worse) | 1 | 3 | 2 | 5 | 14 |
| CRF syllable | 4* | 3 | 3 | 2 | 4 | 16 |
| SVM syllable | 4* | 3 | 3 | 2 | 4 | 16 |
| A-TCN | 4* | 2 | 3 | 1 | 2 | 12 |
| ViT5/BARTpho | 5* | 1 | 2 | 1 | 1 | 10 |
| GPT-4o-mini | 4* | 5 | 1 | 4 | 1 | 15 |

\* reported, not measured here, and register-dependent.

The arithmetic tie at 21 is not a real tie. The decision rules that break it:

- **Rule-based and unigram tie on score but fail on accuracy**, which is the primary purpose.
  A restorer at 71% is not usable output; it is noise with accents.
- **Bigram Viterbi with a trie-backed table scores 23 and wins outright**: 91.5% accuracy,
  19 MB, 1,543 sent/s, no GPU, no network, deterministic, every score inspectable.
- Every approach that beats it on accuracy (transformers) loses 3-4 points on storage,
  latency, and ops simultaneously, and none of them demonstrates the win on data we have.
  Note the storage reversal: with a trie the n-gram model is **smaller than the smallest
  transformer** (19 MB vs ~300 MB even at int8), while being 60-200× faster.

**Recommended: bigram Viterbi over a trie-backed table.** Optimise it, do not replace it.

---

## 7. What to do instead of switching approaches

Since the model order is not the bottleneck but the bigram table is load-bearing, the work
should go into making the same model cheaper and better fed.

| Change | Expected | Basis |
|---|---|---|
| **marisa-trie for the 2-gram table** | 660 MB → **19 MB** measured | built from the same 4.62M bigrams; 19.0 MB file, 0.0 s load |
| **Candidate index + numpy DP** | 1,543 → ~5,000+ sent/s | measured: index build is 0.65 s once, lookups are 0.03 ms/sent |
| **Rebuild the corpus** to raise bigram coverage above 19% | the real accuracy lever | 80.9% UNK fallback rate is the ceiling on quality |
| **Fix the grader** | 0 pts, but makes every other number trustworthy | measured 4.8-pt inflation |
| **Word-level segmentation** before LM scoring | unknown, highest upside | published letter/syllable/word comparisons favour word features |

The storage decision, correctly stated: the 2-gram table as a Python dict costs 500 MB RAM,
71 MB disk and 1.6 s of startup, and it buys ~20 accuracy points — so dropping it would be a
serious regression, not a saving. The right move is to change the **representation**: the
same 4,622,847 bigrams fit in a 19 MB marisa-trie that loads instantly. Measured, not
estimated. The model is untouched; only the container changes.

A note on what the sparse coverage does and does not imply. It does not imply the table is
useless (disproved above). It does imply that a **trigram** table would be far sparser still
(§5 measured 69% of trigram positions with no adjacent-bigram support at all), so paying
4-6 GB for one would be the wrong trade.

---

## 8. Final recommendation

**Best balanced approach: bigram Viterbi with the 2-gram table held in a marisa-trie, over a
rebuilt corpus.**

That is not "the least bad compromise" — it is the only option that is simultaneously best or
near-best on every criterion once the table representation is fixed: 91.5% accuracy (only
transformers beat it, and only on the formal register), 19 MB (smaller than the smallest
transformer even at int8), 0.65 ms/sentence (60-200× faster than any neural option), and
~250 lines of dependency-free deterministic code.

| Criterion | Verdict |
|---|---|
| Accuracy | 91.5% measured; best achievable without giving up every other criterion |
| Storage | 660 MB with a dict; **19 MB measured** with a marisa-trie, same model |
| Latency | 0.65 ms/sent CPU, 1,543 sent/s; 60-200× faster than transformer options |
| Complexity | ~250 LOC, no dependencies, no GPU, deterministic, fully inspectable |
| Ceiling | 99.87% recall on candidates — the design is not the limiting factor |

Rejected, with reasons: transformers (better only on formal register, 3-4× worse on storage,
latency and ops), trigram (measured worse on this corpus), rule-based and unigram (too
inaccurate to ship), cloud LLM (slower than the local model and costs money).

The one open question worth spending real time on is **word-level modelling**, because it
changes what the model conditions on rather than how much of it there is. That is a
research spike, not a production commitment — and it should be gated on rebuilding the
corpus first, since a sparse corpus will defeat a word-level model for the same reason it
defeated the trigram.

---

## Reproduce

```
bench/measure_ngram.py        # storage + latency of the n-gram stack
bench/accuracy_vs_order.py    # accuracy vs model order, one grader, both datasets
bench/data/diacritic_eval_v0.txt  # out-of-domain eval set (nom-vn, CC0)
```
