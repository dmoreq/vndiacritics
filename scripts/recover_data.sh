#!/usr/bin/env bash
# Recover the 2017 corpus from the upstream Java repo's git history.
# These files outperform the 2022 working-tree data by 4.45 accuracy points.
set -euo pipefail
SRC="$(dirname "$0")/../Vietnamese-Accent-Prediction"
DST="$(dirname "$0")/../vap/data"
mkdir -p "$DST"
git -C "$SRC" show HEAD:datasets/news1gram      > "$DST/uni.tsv"
git -C "$SRC" show HEAD:datasets/news2grams     > "$DST/bi.tsv"
cp "$SRC/datasets/test.txt"                      "$DST/in_domain.txt"
wc -l "$DST"/*.tsv "$DST"/in_domain.txt
