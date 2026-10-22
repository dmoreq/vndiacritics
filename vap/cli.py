"""Command line: `vap [--data DIR]` reads text on stdin, writes restored text on stdout.

`vap --accuracy GOLD_FILE` scores the model against a gold file instead, and always
reports the skip count so a length-changing restorer cannot hide behind a good number.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vap.model import Model
from vap.normalize import nfc, strip_accent_keep_case


def _run_accuracy(model: Model, gold_file: Path) -> int:
    from vap.eval import score, split_sentences

    gold = [nfc(s) for s in split_sentences(gold_file.read_text(encoding="utf-8"))]
    pred = [model.restore(strip_accent_keep_case(g)) for g in gold]
    r = score(gold, pred)
    print(
        f"accuracy={r.accuracy:.4f} correct={r.correct} "
        f"total={r.total} skipped={r.skipped}"
    )
    return 0


def _run_stdin(model: Model) -> int:
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line.strip():
            print()
            continue
        print(model.restore(strip_accent_keep_case(line)))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vap", description="Restore Vietnamese diacritics")
    ap.add_argument("--data", type=Path, default=None, help="corpus directory")
    ap.add_argument(
        "--accuracy",
        metavar="GOLD_FILE",
        default=None,
        help="score against a gold file instead of restoring stdin",
    )
    args = ap.parse_args(argv)

    model = Model.load(args.data)
    if args.accuracy:
        return _run_accuracy(model, Path(args.accuracy))
    return _run_stdin(model)


if __name__ == "__main__":
    raise SystemExit(main())
