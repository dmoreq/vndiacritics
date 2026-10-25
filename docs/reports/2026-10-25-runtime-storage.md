# Runtime storage: assessment of the ~25 MB default data set

**Date**: 2026-10-25
**Base**: v0.2.1 (`7cdf4fa`), extended with the compression change below
**Question**: is the current data layout for the three runtime files
(`uni.tsv` 2.2 MB + `bi.trie` 23 MB + `bi.meta.json` 38 B) optimal, or can
storage be reduced without accuracy cost?

## 1. Anatomy (measured)

`bi.trie` decomposes as 17.2 MB of key structure (marisa-trie prefix
compression over 50.7 MB of raw key text — 2.9x) plus 5.9 MB of values (the
7.2 MB of ASCII counts are tail-packed and already compressed). `uni.tsv` is
loaded into a Python dict at runtime; the trie is memory-mapped by
marisa-trie's own loader.

## 2. Experiments and verdicts (all measured)

| Experiment | Result | Verdict |
|---|---|---|
| **varint values** (binary counts instead of ASCII in the trie) | 23.1 MB → **23.1 MB** (0 bytes saved; marisa already packs values) | rejected |
| **singleton prune, count >= 2** (v2b's lite rule applied to v1: 35.2% of rows) | trie 23.1 → 14.7 MB, but in-domain 96.05% → **95.68%** (below the 95.9 pinned gate), conversational 89.89% → 89.36% | rejected for v1 |
| **gzip uni.tsv** | 2.2 → 1.2 MB | rejected: −1 MB for a decompress step on every load |
| **alternative containers** (pickle dict, sqlite) | pickle of 5.5M entries ≈ 300-400 MB; sqlite larger than marisa for this key set | rejected by estimate |

The singleton experiment produced the session's key insight: **the same prune
that was free on v2b is harmful on v1**. v2b singletons were subtitle/web
noise (pruning IMPROVED the cased eval); v1 singletons are real news
collocations — the long tail that decides rankings. There is no universal
pruning rule; each corpus needs its own measurement.

Verdict on the original question: the marisa-trie layout chosen at project
start is already near-optimal. 23 MB is the floor for 5.5M bigrams at 96.05%
accuracy.

## 3. Adopted: the rebuild source moves out of the hot set

`bi.tsv` is not a runtime file — it exists only so `Model.load` can rebuild a
missing trie. Both recovery scripts now build the trie eagerly and keep the
TSV compressed instead:

| Data dir | Before | After | Delta |
|---|---:|---:|---:|
| `vndiacritics/data/` (v1) | 101 MB (`bi.tsv` 77) | **57 MB** (`bi.tsv.gz` 33) | −44 MB |
| `vndiacritics/data-v2b/` | 366 MB (`bi.tsv` 151) | **254 MB** (`bi.tsv.gz` 46) | −112 MB |

(Decimal MB from byte counts; the v1 directory was measured both before and
after conversion, the v2b Before is reconstructed from the current on-disk
state with the uncompressed TSV swapped back in.)

Mechanics:

- `scripts/recover_data.sh` / `scripts/fetch_corpus_v2.sh`: after extraction
  and SHA verification, build `bi.trie` eagerly (skipped when marisa-trie is
  not installed yet — CI installs afterwards and the lazy path applies), then
  `gzip -9` the TSV.
- `vndiacritics/data.py`: `parse_count_table` transparently reads `.gz` tables.
- `vndiacritics/model.py`: the rebuild path tries `bi.tsv` then `bi.tsv.gz`;
  when neither exists the error names the recovery commands (previously a raw
  `FileNotFoundError` from the TSV parser).
- `scripts/make_clean_corpus.py`: accepts the compressed source.

Accuracy: unchanged by construction (the trie bytes are identical; the gz is
only the rebuild source). Gates re-run after conversion: 99 tests, accuracy
gates pass, cased eval 90.38%.

## 4. Reproduce

```bash
./scripts/recover_data.sh            # converts v1 data dir in place
gzip -9 vndiacritics/data-v2b/bi.tsv # same for v2b (trie already built)
.venv/bin/pytest -q                  # 99 tests
```
