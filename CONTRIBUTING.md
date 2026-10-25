# Contributing to vndiacritics

## Setup

```bash
git clone https://github.com/dmoreq/vndiacritics.git
cd vndiacritics
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
./scripts/recover_data.sh   # fetches the corpus from the pinned upstream commit
pre-commit install          # optional but recommended
```

## Workflow

1. Run the targeted tests for what you touch: `pytest tests/test_restore.py -q`.
2. Run lint and format before committing: `ruff check . && ruff format .`.
3. The accuracy gates in `tests/test_accuracy_gate.py` pin measured numbers
   (in-domain 96.01%). If your change moves them, the number must be re-measured
   with `bench/baseline.py` and updated in the same change.

## Conventions

- Every performance claim in code comments or README carries a measured number.
  Add one or cite an existing report; do not write "should be faster".
- Findings and investigations land as dated reports in `docs/reports/`. The
  report is the durable artifact; scripts in `bench/` support it.
- Code marked "must not be cleaned up" (see `vndiacritics/restore.py`) carries
  measured costs for its branches. Do not refactor those branches without
  re-measuring.

## Data licensing

The corpus is fetched at setup from an upstream repository that has no LICENSE,
so it is never committed here. Do not commit anything under
`vndiacritics/data/` or `vndiacritics/data-clean/`.
