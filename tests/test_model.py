import pytest

pytest.importorskip("marisa_trie")


def test_from_directory(tmp_path):
    from vndiacritics.model import Model
    from vndiacritics.store import BigramStore

    (tmp_path / "uni.tsv").write_text("con\t10\ncòn\t99\n", encoding="utf-8")
    (tmp_path / "bi.tsv").write_text("con là\t5\n", encoding="utf-8")
    BigramStore.build({"con là": 5}, tmp_path / "bi.trie")
    m = Model.load(tmp_path)
    assert m.restore("con") == "còn"


def test_missing_trie_is_rebuilt(tmp_path):
    from vndiacritics.model import Model

    (tmp_path / "uni.tsv").write_text("con\t10\n", encoding="utf-8")
    (tmp_path / "bi.tsv").write_text("con la\t5\n", encoding="utf-8")
    m = Model.load(tmp_path)
    assert (tmp_path / "bi.trie").exists()
    assert m.restore("con") == "con"


def test_missing_trie_rebuilds_from_gzip_table(tmp_path):
    """Recovery keeps the big TSV compressed; Model.load must read bi.tsv.gz."""
    import gzip

    from vndiacritics.model import Model

    (tmp_path / "uni.tsv").write_text("con\t10\n", encoding="utf-8")
    with gzip.open(tmp_path / "bi.tsv.gz", "wt", encoding="utf-8") as fh:
        fh.write("con la\t5\n")
    m = Model.load(tmp_path)
    assert (tmp_path / "bi.trie").exists()
    assert m.restore("con") == "con"


def test_no_bigram_source_raises_actionable_error(tmp_path):
    """Neither bi.tsv nor bi.tsv.gz: the error names the recovery commands."""
    import gzip

    from vndiacritics.model import Model

    (tmp_path / "uni.tsv").write_text("con\t10\n", encoding="utf-8")
    with gzip.open(tmp_path / "bi.tsv.gz", "wt", encoding="utf-8") as fh:
        fh.write("con la\t5\n")
    Model.load(tmp_path)  # builds trie from the gz
    (tmp_path / "bi.trie").unlink()
    (tmp_path / "bi.tsv.gz").unlink()
    (tmp_path / "bi.meta.json").unlink()
    with pytest.raises(FileNotFoundError, match="recover_data"):
        Model.load(tmp_path)


def test_uses_trie_not_dict(tmp_path):
    """Ensure the restorer sees one and two gram totals correctly via the store."""
    from vndiacritics.model import Model
    from vndiacritics.store import BigramStore

    (tmp_path / "uni.tsv").write_text("công\t1000\nty\t500\ncon\t10\ncòn\t900\n", encoding="utf-8")
    (tmp_path / "bi.tsv").write_text("công ty\t8000\ncông con\t1\ncông còn\t1\n", encoding="utf-8")
    BigramStore.build({"công ty": 8000, "công con": 1, "công còn": 1}, tmp_path / "bi.trie")
    m = Model.load(tmp_path)
    assert m.restore("cong con") == "công con"


def test_missing_metadata_rebuilds_trie_pair(tmp_path):
    from vndiacritics.model import Model
    from vndiacritics.store import BigramStore

    (tmp_path / "uni.tsv").write_text("tôi\t500\ntoi\t1\n", encoding="utf-8")
    (tmp_path / "bi.tsv").write_text("tôi tôi\t3\n", encoding="utf-8")
    trie_path = tmp_path / "bi.trie"
    BigramStore.build({"tôi tôi": 3}, trie_path)
    trie_path.with_suffix(".meta.json").unlink()
    model = Model.load(tmp_path)
    assert trie_path.with_suffix(".meta.json").exists()
    assert model.restore("toi") == "tôi"
