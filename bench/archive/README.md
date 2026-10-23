# Archived analysis scripts

These scripts produced the numbers in `docs/reports/`. They are kept for
re-verification, not for routine use.

**They are historical.** Fifteen of them reach into private `Restorer` members
(`_restorer`, `_viterbi`, `_columns`, `_uni`, `_bi`), and that API has changed twice since
they were written: `Restorer._score` was removed, and `bigram_skip_below` was added.
Expect some to need small edits before they run again. A script that no longer runs does
not make its report wrong — the report records what was measured at that commit.

## Which report each one backs

| Script | Feeds |
|---|---|
| `accuracy_vs_order.py` | `2026-10-22-approach-comparison.md` (n-gram order sweep) |
| `benchmark.py` | `2026-10-22-benchmark-report.md` (superseded by `bench/baseline.py`) |
| `corpus_quality.py` | `2026-10-23-corpus-vs-algorithm.md` |
| `count_dp_work.py` | `2026-10-23-bottleneck-analysis.md` |
| `diagnose_failures.py` | `2026-10-23-failure-diagnosis.md` |
| `error_taxonomy.py` (kept active) | `docs/USAGE.md` section 3 |
| `foreign_guard.py` | `2026-10-23-residual-error-recoverability.md` |
| `levers.py` | `2026-10-23-bottleneck-analysis.md` |
| `measure_ngram.py` | `2026-10-22-approach-comparison.md` (memory/latency) |
| `probe_miss_rule.py` | `2026-10-23-bottleneck-analysis.md` (refuted hypothesis) |
| `profile_bottleneck.py` | `2026-10-23-bottleneck-analysis.md` |
| `recoverable.py` | `2026-10-23-residual-error-recoverability.md` |
| `skip_threshold.py` | `2026-10-23-failure-diagnosis.md` (threshold sweep) |
| `test_fixes.py` | `2026-10-23-failure-diagnosis.md` |
| `typo_audit.py` | `2026-10-23-typo-in-corpus.md` |
| `typo_detect.py` | `2026-10-23-multi-source-consensus-typo.md` |

## Active scripts (not archived)

| Script | Purpose |
|---|---|
| `bench/baseline.py` | accuracy + throughput, supports `--data` / `--gold` / `--tag` |
| `bench/register_accuracy.py` | per-register accuracy table |
| `bench/build_typo_list.py` | verified typo list (multi-source consensus) |
| `bench/consensus_check.py` | five-dictionary consensus check |
| `bench/error_taxonomy.py` | error families behind `docs/USAGE.md` |

## Running an archived script

Some resolve paths relative to their own location. From the repository root:

```bash
env -u PYTHONPATH -u PYTHONHOME .venv/bin/python bench/archive/diagnose_failures.py
```

If a script reports `ROOT` as `bench/archive`, it was written assuming `bench/`. Fix the
`ROOT` computation to go up two levels:

```python
ROOT = Path(__file__).resolve().parent.parent.parent
```
