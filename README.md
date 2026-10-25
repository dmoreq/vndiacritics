# vndiacritics — Vietnamese diacritic restoration

[![CI](https://github.com/dmoreq/vndiacritics/actions/workflows/ci.yml/badge.svg)](https://github.com/dmoreq/vndiacritics/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/vndiacritics/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Restores Vietnamese diacritics on text written without them, in pure Python, on CPU.
Optionally restores letter case as well (truecasing).

```python
from vndiacritics import Model

m = Model.load()
m.restore("toi yeu viet nam")  # 'tôi yêu việt nam'
m.restore("Hop dong so 02/HD/2025")  # 'Hợp đồng số 02/HD/2025'
m.restore("toi yeu viet nam", case="correct")  # 'Tôi yêu Việt Nam' (needs corpus v2b)
```

The corpus is **not shipped in the wheel** (it is rebuilt from git history). Install the
package, then run `./scripts/recover_data.sh` once, or point `Model.load(directory=...)` at
an existing corpus directory. Calling `Model.load()` without a corpus raises an error
naming that command. `case="correct"` additionally needs corpus v2b
(`./scripts/fetch_corpus_v2.sh`, then `Model.load("vndiacritics/data-v2b")`).

Command line:

```bash
./scripts/recover_data.sh          # once: build vndiacritics/data/ from git history
echo "toi yeu viet nam" | vndiacritics      # 'tôi yêu việt nam'
echo "toi yeu viet nam" | vndiacritics --data vndiacritics/data-v2b --case correct
vndiacritics --accuracy vndiacritics/data/in_domain.txt
```

## Measured

Apple M3, Python 3.13, single process, no GPU.

| Dataset | Tokens | Accuracy | Sentences/s |
|---|---:|---:|---:|
| in-domain news (589 sentences), default corpus | 8995 | **96.05%** | ~1,850 |
| out-of-domain, all registers (55 sentences), default corpus | 883 | **95.58%** | ~2,450 |
| in-domain with corpus v2b (register-balanced) | 8995 | 95.11% | ~1,180 |
| out-of-domain with corpus v2b | 883 | **96.38%** | ~1,590 |
| cased eval, `case="correct"` (needs v2b) | 603 | **90.22%** | — |

The number-context bug (a numeric token corrupting its neighbours) is fixed as of
2026-10-25; the accuracy column reflects the fix. Corpus v2b trades 0.94 in-domain
points for +2.7 conversational and +0.5 news — see
[docs/reports/2026-10-25-corpus-v2.md](docs/reports/2026-10-25-corpus-v2.md).

Throughput was measured on a machine under load, so treat the median as indicative and the
speedup as the reliable figure: 1,841 → 2,195 sent/s (**1.19x**) from the rare-pair skip,
measured A/B within one process. Accuracy is stable at 96.01% across every run.

Per register (out-of-domain):

| Register | Tokens | Accuracy (v1) | v2b |
|---|---:|---:|---:|
| news | 206 | **98.54%** | 99.03% |
| official documents | 178 | 95.51% | 95.51% |
| contracts | 205 | 95.12% | **96.10%** |
| conversational | 188 | 89.89% | **92.55%** |

| Resource | v1 (default) | v2b (optional) |
|---|---|---|
| Load time | 0.29 s | 8.2 s |
| Bigram table on disk | 22 MB (marisa-trie) | 240 MB |
| Resident memory | 113 MB | ~1 GB |
| Runtime dependencies | `marisa-trie` only | `marisa-trie` only |

Accuracy is register-dependent by about 9 points, which is larger than the gap between
competing models. Conversational text is the weak spot; news and official text are strong.

Whitespace and letter case are preserved exactly as supplied: `restore()` copies the
original spacing and re-applies case per token, so mixed-case and punctuated input
round-trips without being normalised.

## How it works

1. **Candidate generation.** An accent-stripped syllable maps to every accented form seen in
   the corpus (`vndiacritics/index.py`). Gold form is present 99.87% of the time, so this is the recall
   ceiling of the whole approach.
2. **Bigram Viterbi.** Pick the highest-scoring path through the candidate lattice using
   interpolated bigram counts with an UNK penalty (`vndiacritics/restore.py`).
3. **Beam width 8.** Candidates are pruned by unigram count before the DP. Measured: 0.30
   accuracy points for 2.4x throughput.
4. **Rare-pair skip.** A pair where either word's unigram count is below `1e-4 * |V|` scores
   UNK without consulting the table. Avoids ~33% of bigram lookups; measured cost 0.01
   accuracy points. Set `Restorer(..., bigram_skip_below=0)` to disable.
5. **n1-confidence smoothing.** The bigram ratio is interpolated toward the unigram
   (`p = (n2 + K*p_uni)/(n1 + K)`, auto-scaled K) so thin-context pairs cannot outrank
   massive ones. This fixed the number-adjacency bug and gained +0.045 in-domain.
6. **Truecaser (optional).** `case="correct"` runs a statistical case decider
   (`vndiacritics/truecase.py`) over the restored words: per-type case frequencies,
   ratio-based sentence-initial rule, capitalized-bigram continuations, gazetteers.

Known limitation: `so` is not disambiguated to `số` when followed by a number
(`so 12` → `so 12`), because `đồng so` is 10x more frequent in the corpus than `đồng số`.
Fixing it needs a digit-context feature, which is a retuning change, not a bug fix.

Three details in `restore.py` are load-bearing and documented inline: the UNK penalty, the
unigram prior's position, and stripping punctuation before lookup.

## Reproduce

```bash
./scripts/recover_data.sh
.venv/bin/pytest -q                          # 96 tests
.venv/bin/python bench/baseline.py           # accuracy + throughput, both corpora
.venv/bin/python bench/register_accuracy.py  # per-register breakdown
./scripts/fetch_corpus_v2.sh                 # optional: corpus v2b + case stats
.venv/bin/python bench/cased_eval.py --data vndiacritics/data-v2b
```

## Before you use this

Read **[docs/USAGE.md](docs/USAGE.md)** — it documents accuracy per text type
(news 98.5%, contracts 95.1%, **conversational 89.9%**) and three confirmed bugs that
matter in practice, including a numeric token corrupting its neighbouring words.

## Limitations

- Punctuation is split with a regex tuned to these corpora; exotic separators may pass through.
- Proper nouns and foreign words are left unchanged when absent from the vocabulary, which is
  correct for names but wrong for loanwords that should carry diacritics.
- Conversational text scores ~9 points below news text. Adding a conversational corpus would
  narrow that gap more than any model change.

## Roadmap

- ~~Case correction~~ — shipped 2026-10-25 as `case="correct"` (90.22% case-sensitive
  on the cased eval; needs corpus v2b). See
  [docs/reports/2026-10-25-case-correction.md](docs/reports/2026-10-25-case-correction.md).
- Conversational register: largely closed by corpus v2b (89.89% → 92.02%).

## Data & license

Code: MIT (see [LICENSE](LICENSE)). The diacritic-restoration corpus is **not**
redistributed: it is extracted at setup time from
[tienthanhdhcn/Vietnamese-Accent-Prediction](https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction)
at a pinned commit and verified by SHA-256, because that repository carries no
license. Do not commit anything under `vndiacritics/data/`. The out-of-domain
evaluation set is CC0 ([nom-vn](https://github.com/nom-vn)). Development-only
dictionaries fetched by `scripts/fetch_dicts.sh` carry their own licenses.
