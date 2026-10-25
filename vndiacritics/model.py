"""Assembles loaders, index, store and restorer into one importable object."""

from __future__ import annotations

import json
from pathlib import Path

from vndiacritics.data import DATA_DIR, load_bigram, load_unigram
from vndiacritics.index import CandidateIndex
from vndiacritics.restore import Restorer
from vndiacritics.store import BigramStore
from vndiacritics.truecase import Truecaser, load_case_tables


class Model:
    def __init__(self, restorer: Restorer) -> None:
        self._restorer = restorer

    @classmethod
    def load(cls, directory: Path | None = None) -> Model:
        d = Path(directory) if directory is not None else DATA_DIR
        # The corpus is not shipped in the wheel (it is rebuilt from git history).
        # Fail with the command that fixes it instead of a bare FileNotFoundError.
        if not (d / "uni.tsv").exists():
            raise FileNotFoundError(
                f"corpus not found at {d}. Build it with:  ./scripts/recover_data.sh  "
                f"(or pass directory=... pointing at a corpus directory)"
            )
        unigram = load_unigram(d / "uni.tsv")
        trie_path = d / "bi.trie"
        # The trie and its metadata sidecar are one cache artifact: a trie without
        # its sidecar cannot answer size/total, so rebuilding both is cheaper than a
        # partial load. This covers a MISSING sidecar only -- not a stale or corrupt
        # one, which would need an atomic cache protocol.
        meta_path = trie_path.with_suffix(".meta.json")
        if not trie_path.exists() or not meta_path.exists():
            BigramStore.build(load_bigram(d / "bi.tsv"), trie_path)
        store = BigramStore.load(trie_path)
        # corpus-measured smoothing override: the auto-scaled bigram_conf_k is
        # calibrated for the 2017 corpus; a different corpus must carry its own
        # measured K in model.json (see docs/reports/2026-10-25-corpus-v2.md).
        conf_k: int | None = None
        model_json = d / "model.json"
        if model_json.exists():
            conf_k = int(json.loads(model_json.read_text(encoding="utf-8"))["bigram_conf_k"])
        # Case statistics are optional: present in corpus v2 (case.tsv), absent
        # in the 2017 corpus. Built lazily on the first case="correct" call —
        # loading them costs seconds and gigabytes, and default-mode users
        # never pay it. case="correct" raises a helpful error without them.
        truecaser_factory = None
        if (d / "case.tsv").exists():
            truecaser_factory = lambda: Truecaser(load_case_tables(d))
        restorer = Restorer(
            unigram,
            CandidateIndex(unigram),
            store,
            bigram_conf_k=conf_k,
            truecaser_factory=truecaser_factory,
        )
        return cls(restorer)

    def restore(self, text: str, case: str = "preserve") -> str:
        return self._restorer.restore(text, case=case)
