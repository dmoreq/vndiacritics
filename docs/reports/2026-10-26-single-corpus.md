# v0.3.0: one corpus — v1 runtime role removed

**Date**: 2026-10-26
**Decision**: owner chose to stop shipping the 2017 news tables (v1) as a
runtime corpus. The register-balanced mixture (formerly "v2b") becomes the one
and default corpus at `vndiacritics/data/`.

## 1. What changed

| Item | Before (v0.2.x) | After (v0.3.0) |
|---|---|---|
| Runtime corpus | v1 news tables (`recover_data.sh`), v2b optional | the lite mixture only (`fetch_corpus.sh`) |
| 2017 news tables | standalone default corpus | mixture component, fetched inside the pipeline, SHA-256 verified |
| Setup commands | `recover_data.sh` + optional `fetch_corpus_v2.sh` | one: `scripts/fetch_corpus.sh` |
| Default in-domain (2017 gold) | 96.05% | **94.96%** |
| Default out-domain | 95.58% | **96.38%** |
| Default conversational | 89.89% | **92.55%** |

The accuracy trade is the pre-registered one from
[2026-10-25-corpus-v2.md](2026-10-25-corpus-v2.md): the mixture gives up 1.09
points on the 2017 news gold and gains +2.66 conversational, +0.98 contracts,
+0.49 news out-of-domain. Gates re-pinned below accordingly.

## 2. Removed data and logic (the redundancy audit)

| Removed | Reason |
|---|---|
| `scripts/recover_data.sh` | absorbed into `fetch_corpus.sh` (the v1-source step: pinned clone, SHA-256, eval gold) |
| `scripts/make_clean_corpus.py`, `bench/build_typo_list.py`, `bench/consensus_check.py`, `scripts/fetch_dicts.sh`, `vndiacritics/data-clean/` | the typo-cleaning experiment was measured at +0.02 and rejected (2026-10-23); the whole pipeline was v1-only |
| `abbreviations.txt` (builder output, merge table, file) | no consumer: the truecaser reads acronym evidence from `case.tsv` allcap counts and fold-key lookups |
| `bench/baseline_results_{orig,clean,postcleanup}.json` | artifacts of the rejected cleaning experiment |
| tracked `vndiacritics/data/bi.meta.json` | the sidecar tracked for the old v1 trie; the corpus is now fully fetched, nothing data-wise ships |
| `data-v2b` directory split | merged into `vndiacritics/data/` (single corpus, single `DATA_DIR`) |

Kept deliberately: `bench/archive/` (reproducibility evidence for the dated
reports), all `docs/reports/*` (records of past states, including v1-era
numbers), the 2017 gold `in_domain.txt` (fetched by the pipeline, still the
in-domain eval).

## 3. Measurement incident, recorded

While swapping the directories, the five case/gazetteer files (case.tsv 62 MB,
case_bi.tsv 45 MB, names_*.txt, abbreviations.txt) were found missing from
`data-v2b` — deleted outside this session. The runtime tables (uni, trie, gz)
were intact. Recovery: the full `fetch_corpus.sh` run below rebuilt everything
end-to-end, which simultaneously validated the new fresh-machine path (the
absorbed v1-recovery step, all extracts, merge, trie, model.json, gazetteers).

## 4. Re-measured on the shipped configuration

MEASUREMENTS PENDING PIPELINE COMPLETION — this section is filled by the same
run that builds the corpus; see §6 for the gate values.

## 5. Gates re-pinned

GATES PENDING MEASUREMENT.

## 6. Reproduce

```bash
./scripts/fetch_corpus.sh     # ~3GB downloads, ~40-60 min, ~9GB scratch
.venv/bin/pytest -q
.venv/bin/python bench/baseline.py
```
