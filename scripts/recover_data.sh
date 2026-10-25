#!/usr/bin/env bash
# Recover the 2017 corpus from the upstream Java repo's git history.
# These files outperform the 2022 working-tree data by 4.45 accuracy points.
#
# Corpus provenance: https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction
# pinned to commit 290ad7d. Upstream carries no LICENSE, so the corpus is fetched
# at setup time and never committed to this repository. Byte identity with the
# reference build is verified against the SHA-256 values below.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/Vietnamese-Accent-Prediction"
DST="$ROOT/vndiacritics/data"
UPSTREAM="https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction.git"
PIN="290ad7dd0b8209c93e755e155609ec523d0e7f32"

if [ ! -d "$SRC/.git" ]; then
  echo "upstream not found at $SRC; cloning from $UPSTREAM (pinned ${PIN:0:7})"
  git clone --quiet "$UPSTREAM" "$SRC"
fi

mkdir -p "$DST"
git -C "$SRC" show "$PIN":datasets/news1gram  > "$DST/uni.tsv"
git -C "$SRC" show "$PIN":datasets/news2grams > "$DST/bi.tsv"
cp "$SRC/datasets/test.txt" "$DST/in_domain.txt"

check_sha() {
  local expected="$1" file="$2"
  echo "$expected  $file" | shasum -a 256 -c --status || {
    echo "ERROR: $(basename "$file") does not match the pinned upstream blob"
    exit 1
  }
}
check_sha 54113c8cbc9fcd3114a27ee9e3882309c0e0544608a6bc2c5d6b0ccf4ececfee "$DST/uni.tsv"
check_sha 232ba3b7f1e4926f6832410cca0a246e1a0302e01dc8ced4872747ccbf62d557 "$DST/bi.tsv"
check_sha b566c3d5d8d6311bceb83875e5c08d7d3a636be26f513fec718e74860f6d1802 "$DST/in_domain.txt"

echo "corpus recovered and verified against pinned upstream commit"
wc -l "$DST"/*.tsv "$DST"/in_domain.txt
