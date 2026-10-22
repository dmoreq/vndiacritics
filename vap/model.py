"""Assembles loaders, index, store and restorer into one importable object."""

from __future__ import annotations

from pathlib import Path

from vap.data import DATA_DIR, load_bigram, load_unigram
from vap.index import CandidateIndex
from vap.restore import Restorer
from vap.store import BigramStore


class Model:
    def __init__(self, restorer: Restorer) -> None:
        self._restorer = restorer

    @classmethod
    def load(cls, directory: Path | None = None) -> "Model":
        d = Path(directory) if directory is not None else DATA_DIR
        unigram = load_unigram(d / "uni.tsv")
        trie_path = d / "bi.trie"
        if not trie_path.exists():
            BigramStore.build(load_bigram(d / "bi.tsv"), trie_path)
        store = BigramStore.load(trie_path)
        restorer = Restorer(unigram, CandidateIndex(unigram), store)
        return cls(restorer)

    def restore(self, text: str) -> str:
        return self._restorer.restore(text)
