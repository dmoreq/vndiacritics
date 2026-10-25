from vndiacritics.cli import main


def test_restore_from_stdin(monkeypatch, capsys, tmp_path):
    import io

    (tmp_path / "uni.tsv").write_text("con\t10\ncòn\t99\n", encoding="utf-8")
    (tmp_path / "bi.tsv").write_text("con la\t5\n", encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO("con\n"))
    assert main(["--data", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "còn" in out


def test_accuracy_mode(capsys, tmp_path):
    (tmp_path / "uni.tsv").write_text("con\t10\ncòn\t99\n", encoding="utf-8")
    (tmp_path / "bi.tsv").write_text("con la\t5\n", encoding="utf-8")
    gold = tmp_path / "gold.txt"
    gold.write_text("còn\n", encoding="utf-8")
    assert main(["--data", str(tmp_path), "--accuracy", str(gold)]) == 0
    out = capsys.readouterr().out
    assert "accuracy=1.0000" in out
    assert "skipped=0" in out
