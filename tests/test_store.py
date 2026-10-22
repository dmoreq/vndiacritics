import pytest

pytest.importorskip("marisa_trie")

from vap.store import BigramStore


def test_roundtrip(tmp_path):
    path = tmp_path / "bi.trie"
    BigramStore.build({"công ty": 66763, "yêu em": 250}, path)
    s = BigramStore.load(path)
    assert s.get("công ty") == 66763
    assert s.get("yêu em") == 250


def test_missing_returns_zero(tmp_path):
    path = tmp_path / "bi.trie"
    BigramStore.build({"a b": 1}, path)
    s = BigramStore.load(path)
    assert s.get("x y") == 0


def test_missing_with_default(tmp_path):
    path = tmp_path / "bi.trie"
    BigramStore.build({"a b": 1}, path)
    s = BigramStore.load(path)
    assert s.get("x y", 0) == 0


def test_size_and_total_persisted(tmp_path):
    path = tmp_path / "bi.trie"
    BigramStore.build({"a b": 5, "c d": 7}, path)
    s = BigramStore.load(path)
    assert s.size == 2
    assert s.total == 12


def test_save_load_is_byte_identical(tmp_path):
    p1, p2 = tmp_path / "a.trie", tmp_path / "b.trie"
    data = {"a b": 5, "c d": 7}
    BigramStore.build(data, p1)
    BigramStore.build(data, p2)
    assert p1.read_bytes() == p2.read_bytes()
