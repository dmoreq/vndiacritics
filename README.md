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
m.restore("toi yeu viet nam", case="correct")  # 'Tôi yêu Việt Nam'
```

The corpus is **not shipped in the wheel**. Install the package, then run
`./scripts/fetch_corpus.sh` once (~3 GB of downloads, ~40 minutes, ~9 GB of scratch
space in gitignored `.tmp/`); it builds `vndiacritics/data/` — a register-balanced,
cased corpus (2017 news tables + Wikipedia + OpenSubtitles + legal statutes, see
[CORPORA.md](CORPORA.md)). Calling `Model.load()` without a corpus raises an error
naming that command, as does `case="correct"` before the first build.

Command line:

```bash
./scripts/fetch_corpus.sh                    # once: build vndiacritics/data/
echo "toi yeu viet nam" | vndiacritics       # 'tôi yêu việt nam'
echo "toi yeu viet nam" | vndiacritics --case correct   # 'Tôi yêu Việt Nam'
vndiacritics --accuracy vndiacritics/data/in_domain.txt
```

## Measured

Apple M3, Python 3.13, single process, no GPU.

| Dataset | Tokens | Accuracy | Sentences/s |
|---|---:|---:|---:|
| in-domain news (589 sentences, the 2017 upstream gold) | 8995 | 94.96% | ~1,650 |
| out-of-domain, all registers (55 sentences) | 883 | **96.38%** | ~2,195 |
| cased eval, `case="correct"` | 603 | **90.38%** | — |

History note: through v0.2.x the default corpus was the 2017 news tables alone
(in-domain 96.05%, conversational 89.89%). Since v0.3.0 the one shipped corpus is the
register-balanced mixture: it trades 1.09 points on the 2017 news gold for +2.66
conversational, +0.98 contracts and +0.49 news out-of-domain. The 2017 tables remain
a mixture component fetched at build time. Full history:
[docs/reports/2026-10-25-corpus-v2.md](docs/reports/2026-10-25-corpus-v2.md) and
[2026-10-26-single-corpus.md](docs/reports/2026-10-26-single-corpus.md).

Per register (out-of-domain):

| Register | Tokens | Accuracy |
|---|---:|---:|
| news | 206 | **99.03%** |
| official documents | 178 | 95.51% |
| contracts | 205 | **96.10%** |
| conversational | 188 | **92.55%** |

| Resource | Value |
|---|---|
| Load time | 7.4 s (candidate-index build dominates; case tables lazy) |
| First `case="correct"` call | +8.7 s, one-time |
| Bigram table on disk | 43 MB trie (+44 MB gzipped rebuild source) |
| Resident memory | ~1.1 GB (default) / ~2.1 GB (after case-correct) |
| Runtime dependencies | `marisa-trie` only |

Accuracy is register-dependent by about 6.5 points. Conversational text is the weakest
register; news and official text are strong.

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
./scripts/fetch_corpus.sh
.venv/bin/pytest -q                          # 99 tests
.venv/bin/python bench/baseline.py           # accuracy + throughput, both golds
.venv/bin/python bench/register_accuracy.py  # per-register breakdown
.venv/bin/python bench/cased_eval.py         # case='correct' accuracy
```

## Before you use this

Read **[docs/USAGE.md](docs/USAGE.md)** — it documents accuracy per text type
(news 98.5%, contracts 95.1%, **conversational 89.9%**) and three confirmed bugs that
matter in practice, including a numeric token corrupting its neighbouring words.

## Limitations

- Punctuation is split with a regex tuned to these corpora; exotic separators may pass through.
- Proper nouns and foreign words are left unchanged when absent from the vocabulary, which is
  correct for names but wrong for loanwords that should carry diacritics.
- Conversational text remains the weakest register (6.5 points below news on the
  shipped corpus); the mixture already closed 2.7 of the original 8.65-point gap.

## Roadmap

- ~~Case correction~~ — shipped 2026-10-25 as `case="correct"` (90.38% case-sensitive
  on the cased eval). See
  [docs/reports/2026-10-25-case-correction.md](docs/reports/2026-10-25-case-correction.md).
- ~~Conversational register~~ — largely closed by the mixture (89.89% → 92.55%).
- Persist the candidate index at corpus-build time: index construction is now
  the load bottleneck (6.8s of the 7.4s load); a marisa-backed index
  would cut the default load to well under 2 s.

## Data & license

Code: MIT (see [LICENSE](LICENSE)). The diacritic-restoration corpus is **not**
redistributed: it is extracted at setup time from
[tienthanhdhcn/Vietnamese-Accent-Prediction](https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction)
at a pinned commit and verified by SHA-256, because that repository carries no
license. Do not commit anything under `vndiacritics/data/`. The out-of-domain
evaluation set is CC0 ([nom-vn](https://github.com/nom-vn)).
