"""Command line: `vndiacritics [--data DIR]` reads text on stdin, writes restored text on stdout.

`vndiacritics --accuracy GOLD_FILE` scores the model against a gold file instead, and always
reports the skip count so a length-changing restorer cannot hide behind a good number.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vndiacritics.model import Model
from vndiacritics.normalize import nfc, strip_accent_keep_case


def _run_accuracy(model: Model, gold_file: Path, case: str) -> int:
    from vndiacritics.eval import score, split_sentences

    gold = [nfc(s) for s in split_sentences(gold_file.read_text(encoding="utf-8"))]
    pred = [model.restore(strip_accent_keep_case(g), case=case) for g in gold]
    r = score(gold, pred, case_sensitive=(case == "correct"))
    print(f"accuracy={r.accuracy:.4f} correct={r.correct} total={r.total} skipped={r.skipped}")
    return 0


def _run_stdin(model: Model, case: str) -> int:
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line.strip():
            print()
            continue
        print(model.restore(strip_accent_keep_case(line), case=case))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vndiacritics", description="Restore Vietnamese diacritics")
    ap.add_argument("--data", type=Path, default=None, help="corpus directory")
    ap.add_argument(
        "--case",
        choices=("preserve", "correct"),
        default="preserve",
        help="preserve the input's case (default) or correct case from corpus statistics",
    )
    ap.add_argument(
        "--accuracy",
        metavar="GOLD_FILE",
        default=None,
        help="score against a gold file instead of restoring stdin",
    )
    args = ap.parse_args(argv)

    model = Model.load(args.data)
    if args.accuracy:
        return _run_accuracy(model, Path(args.accuracy), args.case)
    return _run_stdin(model, args.case)


if __name__ == "__main__":
    raise SystemExit(main())
