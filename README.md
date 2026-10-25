# vndiacritics — Vietnamese diacritic restoration

[![CI](https://github.com/dmoreq/vndiacritics/actions/workflows/ci.yml/badge.svg)](https://github.com/dmoreq/vndiacritics/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/vndiacritics/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Restores Vietnamese diacritics on text written without them, in pure Python, on CPU.

```python
from vndiacritics import Model

m = Model.load()
m.restore("toi yeu viet nam")  # 'tôi yêu việt nam'
m.restore("Hop dong so 02/HD/2025")  # 'Hợp đồng số 02/HD/2025'
```

The corpus is **not shipped in the wheel** (it is rebuilt from git history). Install the
package, then run `./scripts/recover_data.sh` once, or point `Model.load(directory=...)` at
an existing corpus directory. Calling `Model.load()` without a corpus raises an error
naming that command.

Command line:

```bash
./scripts/recover_data.sh          # once: build vndiacritics/data/ from git history
echo "toi yeu viet nam" | vndiacritics      # 'tôi yêu việt nam'
vndiacritics --accuracy vndiacritics/data/in_domain.txt
```

## Measured

Apple M3, Python 3.13, single process, no GPU.

| Dataset | Tokens | Accuracy | Sentences/s |
|---|---:|---:|---:|
| in-domain news (589 sentences) | 8995 | **96.01%** | 2,182 (median of 8; 1,892-2,294) |
| out-of-domain, all registers (55 sentences) | 883 | **95.24%** | 2,879 |

Throughput was measured on a machine under load, so treat the median as indicative and the
speedup as the reliable figure: 1,841 → 2,195 sent/s (**1.19x**) from the rare-pair skip,
measured A/B within one process. Accuracy is stable at 96.01% across every run.

Per register (out-of-domain):

| Register | Tokens | Accuracy |
|---|---:|---:|
| news | 206 | **98.54%** |
| official documents | 178 | **95.51%** |
| contracts | 205 | **95.12%** |
| conversational | 188 | **89.89%** |

| Resource | Value |
|---|---|
| Load time | 0.29 s |
| Resident memory | 113 MB |
| Bigram table on disk | 22 MB (marisa-trie) |
| Runtime dependencies | `marisa-trie` only |

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

Known limitation: `so` is not disambiguated to `số` when followed by a number
(`so 12` → `so 12`), because `đồng so` is 10x more frequent in the corpus than `đồng số`.
Fixing it needs a digit-context feature, which is a retuning change, not a bug fix.

Three details in `restore.py` are load-bearing and documented inline: the UNK penalty, the
unigram prior's position, and stripping punctuation before lookup.

## Reproduce

```bash
./scripts/recover_data.sh
.venv/bin/pytest -q                     # 58 tests
.venv/bin/python bench/baseline.py      # accuracy + throughput, both corpora
.venv/bin/python bench/register_accuracy.py
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

- Case correction: `Model.restore(text, case="correct")` alongside the default
  `"preserve"` mode (`cong ty co phan` → `Công ty Cổ phần`). The corpus currently
  carries no capitalization signal, so this needs a new corpus pass or a rule layer.

## Data & license

Code: MIT (see [LICENSE](LICENSE)). The diacritic-restoration corpus is **not**
redistributed: it is extracted at setup time from
[tienthanhdhcn/Vietnamese-Accent-Prediction](https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction)
at a pinned commit and verified by SHA-256, because that repository carries no
license. Do not commit anything under `vndiacritics/data/`. The out-of-domain
evaluation set is CC0 ([nom-vn](https://github.com/nom-vn)). Development-only
dictionaries fetched by `scripts/fetch_dicts.sh` carry their own licenses.
