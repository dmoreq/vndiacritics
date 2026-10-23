# Codebase audit: legacy inventory

**Date**: 2026-10-23
**Commit**: `682fb7a`, clean tree
**Scope**: every tracked file. Focus: what is genuinely needed for the Python module
versus what is legacy, unreachable, or would ship broken.

Every verdict below names the probe that produced it. Where I had a guess that the
probe refuted, the refutation is recorded.

**Status: applied.** Section 5 lists what was changed and how it was verified. Test count
went 59 to 58 because one test covered a deleted method.

---

## 1. Package: what it actually is

| File | LOC | Purpose | Verdict |
|---|---:|---|---|
| `vap/__init__.py` | 0 | **Empty — no facade at all** | **Find** |
| `vap/normalize.py` | 33 | accent stripping, NFC | Keep |
| `vap/data.py` | 45 | corpus loading | Trim (see F4) |
| `vap/index.py` | 33 | candidate lattice | Keep (`best` unused, F5) |
| `vap/store.py` | 51 | marisa-trie bigram store | Keep |
| `vap/eval.py` | 49 | the single grader | Keep |
| `vap/restore.py` | 188 | Viterbi decoder | Keep (2 unused params, F6) |
| `vap/model.py` | 33 | wiring | Keep |
| `vap/cli.py` | 58 | CLI entry point | Keep |

Total package: ~490 LOC across 9 files. That part is lean. **The problems are at the
packaging boundary and in the untested public surface, not inside the algorithms.**

---

## 2. Findings, ordered by impact

### F1 — Critical: the built wheel cannot run

**Location**: `pyproject.toml#L19-L20` (`packages = ["vap"]`), `vap/data/`

**Probe**: built the wheel and imported it from a clean directory.

```
$ .venv/bin/python -m build --wheel --outdir /tmp/vapdist2   # vap-0.1.0-py3-none-any.whl, 57 KB
$ unzip -q vap-0.1.0-py3-none-any.whl -d installed
$ python -c "import sys; sys.path.insert(0,'installed'); from vap.model import Model; Model.load()"
FileNotFoundError: .../installed/vap/data/uni.tsv
```

Wheel contents:

| File | Shipped |
|---|---|
| `vap/*.py` (9 modules) | yes |
| `vap/data/bi.meta.json` | **yes (37 B)** |
| `vap/data/.gitkeep` | **yes (0 B)** |
| `vap/data-clean/typos.json` | **yes (509 KB — 90% of the wheel)** |
| `vap/data/uni.tsv` | **no** |
| `vap/data/bi.tsv`, `bi.trie` | **no** |

Hatchling excludes `*.tsv`/`*.trie` by default but keeps `*.json`. So the package ships a
metadata sidecar and a typology list describing corpora that are absent.

**Correction**: either (a) ship the corpus (`artifacts` / `include` in
`[tool.hatch.build.targets.wheel]`) and accept ~100 MB, or (b) deliberately ship no data
and make `Model.load()` raise a helpful error telling the user to run
`scripts/recover_data.sh`. Option (b) plus `exclude = ["vap/data/**", "vap/data-clean/**"]`
is the honest choice for a 57 KB library.

**Acceptance**: `pip install` the wheel into a clean venv and either `Model.load()` works,
or it raises a message naming the missing file and the command that produces it. Never a
bare `FileNotFoundError` from deep inside `parse_count_table`.

---

### F2 — Critical: `vap/data-clean/typos.json` is shipped development residue

**Location**: `vap/data-clean/typos.json` (509 KB, inside the package tree)

**Probe**: wheel listing above — it is the single largest file in the distribution and
belongs to a data experiment that was explicitly **not adopted** (accuracy gain 0.02,
below the significance bar; corpus gốc remains default).

**Correction**: move it out of the package to `bench/data/typos.json` (already gitignored
territory) or `docs/`, and exclude `vap/data-clean/**` from the wheel.

**Acceptance**: `vap/data-clean` contains no tracked non-script file; wheel size returns
to ~25 KB.

---

### F3 — Important: no public facade; `Model` is the only documented entry point but `__init__` is empty

**Location**: `vap/__init__.py` (0 bytes)

**Probe**: `README.md` documents `from vap.model import Model`; there is no `__all__`
anywhere in the package.

Empty `__init__.py` means every consumer imports a submodule path directly, so **any
internal move is a breaking change**. It also means `import vap; vap.Model` fails, which
is what most users try first.

**Correction**: add a short facade exporting the three names a caller actually needs:

```python
"""Vietnamese diacritic restoration."""
from vap.model import Model
from vap.normalize import strip_accent, strip_accent_keep_case

__all__ = ["Model", "strip_accent", "strip_accent_keep_case"]
```

Low risk, no behaviour change.

---

### F4 — Important: `load_accent_groups()` is dead, and its data file ships useless

**Location**: `vap/data.py#L41-L45`, `vap/data/accent_groups.txt`

**Probe**:
```
$ grep -rn 'load_accent_groups' --include=*.py . | grep -v 'def load_accent'
(no output — 0 callers)
$ grep -rn 'accent_groups' vap/model.py
(no output — the model never reads it)
```

The file is produced by `scripts/recover_data.sh` and copied by
`make_clean_corpus.py`, but **no runtime code reads it**. `CandidateIndex` builds the
accent map empirically from the unigram table (`strip_accent(form)`), which is a different
and better mechanism than the reference project's hand-curated `AccentInfo.tsv`.

**Correction**: delete `load_accent_groups()` and the `accent_groups.txt` copy step. Keep
the file only if a future feature needs it — and note the corpus already gives the same
information empirically.

**Acceptance**: `pytest tests -q` still 59 passed; `grep -r accent_groups vap/` returns
nothing.

---

### F5 — Suggestion: `CandidateIndex.best()` is used only by a test

**Location**: `vap/index.py#L29-L33`

**Probe**: `grep -rn '\.best(' --include=*.py .` → `tests/test_index.py:22` only.

The decoder uses `candidates()` and does its own argmax in the DP. `best()` is a
single-line convenience with one test and no runtime caller.

**Correction**: delete the method and its test, or keep it as documented public API. Since
there is no facade yet (F3), deletion is safe; if F3 lands first, either decision is
fine. **This is a judgement call — I would delete it**, because `CandidateIndex` is an
internal lattice and a "give me the best form" helper encourages callers to bypass the
bigram model entirely, which is measurably worse.

---

### F6 — Suggestion: two `Restorer` parameters exist only for tests

**Location**: `vap/restore.py#L41-L42` (`bigram_size`, `bigram_total`)

**Probe**:
```
$ grep -rn 'bigram_size=' --include=*.py vap bench scripts | wc -l
0
```
Production constructs `Restorer(unigram, CandidateIndex(unigram), store)` — the store
carries `.size`/`.total`, so the explicit overrides are only used by unit tests that pass
a plain `dict`.

**Correction**: keep them (the `Counter` protocol + explicit sizes is what lets tests run
without a trie) but document that they exist for test injection. **Do not delete** — the
fallback path at L73-L78 is what makes `Restorer` testable at all.

---

### F7 — Important: 20 bench scripts, 1,200 LOC, 15 touch private API

**Location**: `bench/*.py`

**Probe**: all 20 parse; all are cited by at least one report; **15 of 20 reach into
private members** (`_restorer`, `_viterbi`, `_columns`, `_uni`, `_bi`).

| Script | Status | Recommendation |
|---|---|---|
| `baseline.py` | Central; used by 4 reports + README | **Keep** |
| `benchmark.py` | Superseded by `baseline.py` (same job, no `--data`) | **Delete** |
| `register_accuracy.py` | Produces the per-register table in README | Keep |
| `build_typo_list.py`, `consensus_check.py` | Reproduce the typo list; wired into `scripts/make_clean_corpus.py` | Keep |
| `error_taxonomy.py` | Produces `docs/USAGE.md` §3 | Keep |
| `diagnose_failures.py`, `count_dp_work.py`, `profile_bottleneck.py`, `levers.py` | One-shot investigations, conclusions already in reports | **Archive or delete** |
| `probe_miss_rule.py`, `recoverable.py`, `foreign_guard.py`, `typo_audit.py`, `typo_detect.py`, `test_fixes.py`, `skip_threshold.py`, `corpus_quality.py` | One-shot; hypotheses already refuted in reports | **Delete** |
| `accuracy_vs_order.py`, `measure_ngram.py` | Already excluded from ruff in `pyproject.toml` — a code smell | **Delete** |

Rationale: a script whose finding is recorded in a committed report has done its job. The
report is the durable artifact; the script is only re-runnable if it still matches the
current private API — and 15 of them do not, because the API has moved twice
(`_score` removed, `bigram_skip_below` added).

**But**: these are also the reproduction evidence for eight reports. Deleting them makes
the reports unverifiable. **This is the one decision I should not make alone** — see Q1.

---

### F8 — Suggestion: three near-duplicate result JSONs

**Location**: `bench/results.json`, `bench/baseline_results.json`,
`bench/baseline_results_orig.json`, `bench/baseline_results_clean.json`

**Probe**: `baseline_results` and `baseline_results_orig` are produced by the same
command at different times; `benchmark.py` writes `results.json` with the same fields.

**Correction**: keep `results.json` (cited by the benchmark report) and the
`_clean`/`_orig` pair (the corpus comparison), delete `baseline_results.json` once
`baseline.py`'s default tag no longer writes it, and drop `benchmark.py`.

---

### F9 — Nit: `pyproject.toml` excludes files from lint instead of removing them

**Location**: `pyproject.toml#L31-L33`

```toml
exclude = ["bench/accuracy_vs_order.py", "bench/measure_ngram.py"]
```

A lint exclusion for two files is a standing acknowledgement that they are not worth
maintaining. Covered by F7.

---

### F10 — Nit: `vap/store.py` docstring quotes stale numbers

**Location**: `vap/store.py#L3-L5`

"4.6M bigrams costs roughly 500 MB" — the actual table is **5,553,699** bigrams and the
measured dict RSS was **660 MB**. The comment is directionally right but the numbers no
longer match the shipped corpus, which invites a reader to distrust the measurement.

---

## 3. What is NOT legacy — do not touch

| Item | Why it stays |
|---|---|
| `restore.py` design notes (UNK penalty, prior at `i==1`, punctuation stripping) | Each is annotated with a measured cost of removing it (19 points, several points, 4 points) |
| `eval.py` skip counting | This is the fix for the reference project's inflated metric; removing it reproduces the original bug |
| `Counter` Protocol | Makes `Restorer` testable without a trie |
| Beam width K=8 and `bigram_skip_below` | Both are measured throughput/accuracy trade-offs documented inline |
| `vap/data/bi.meta.json` tracked in git | It is the sidecar that makes a fresh clone loadable without rebuilding the trie |

---

## 4. Verification executed

| Check | Result |
|---|---|
| `pytest tests -q` | 59 passed |
| `ruff check vap tests bench` | All checks passed |
| Wheel build | succeeds, 57 KB, **contents broken (F1)** |
| Clean-dir import of wheel | `FileNotFoundError` |
| All 20 bench scripts parse | 0 syntax errors |

---

## 5. Resolutions applied

All findings were acted on. Decisions: archive the historical scripts, ship code-only,
delete the unused helper.

| Finding | Action | Verification |
|---|---|---|
| F1 wheel cannot run | Excluded `vap/data/**` and `vap/data-clean/**` from the wheel; `Model.load()` now raises `FileNotFoundError` naming `scripts/recover_data.sh` | Wheel is 19.4 KB. Import-without-corpus prints the instruction; `Model.load(<real dir>)` still returns `tôi yêu việt nam` |
| F2 `typos.json` shipped | Excluded with the data tree | Not in the wheel |
| F3 no facade | `vap/__init__.py` exports `Model`, `strip_accent`, `strip_accent_keep_case` | `import vap; vap.__all__` verified from the installed wheel |
| F4 `load_accent_groups` dead | Function deleted; `accent_groups.txt` no longer produced by `recover_data.sh` or copied by `make_clean_corpus.py` | `grep -r accent_groups vap/` returns nothing |
| F5 `CandidateIndex.best` unused | Method and its test deleted | 58 tests pass (was 59) |
| F7 20 bench scripts | 15 moved to `bench/archive/` with a README mapping each to its report; `ROOT` depth corrected in 13 of them | `ruff` clean; active bench is 5 scripts |
| F9 lint exclusion | Now `exclude = ["bench/archive"]` | — |
| F10 stale numbers in `store.py` | Corrected to the measured 5,553,699 bigrams / 660 MB dict / 22 MB trie / 0.3 s | — |

### Not fixed, deliberately

- **F6** (`bigram_size` / `bigram_total`): kept. They are what let unit tests drive
  `Restorer` with a plain dict instead of a trie.
- **F8** (duplicate result JSONs): `bench/baseline_results.json` is still written by the
  default tag. Harmless once `benchmark.py` moved to the archive; not worth churn.
- **Two archived scripts hardcode absolute paths** (`accuracy_vs_order.py`,
  `measure_ngram.py` contain `/Users/quy.doan/...`). They are archive-only, so this is
  recorded rather than fixed — editing them would imply they are re-runnable today.

### Post-cleanup verification

| Check | Result |
|---|---|
| `pytest tests -q` | **58 passed** (one test removed with F5) |
| `ruff check vap tests bench scripts` | All checks passed |
| Wheel build | 19.4 KB, code only |
| In-domain accuracy | **96.01%** (unchanged) |
| Out-of-domain accuracy | 95.24% (unchanged) |

The cleanup changed no measured behaviour: the removed code was unreachable and the
packaging fix only removed files that could not be used.
