#!/usr/bin/env bash
# Fetch and build the vndiacritics corpus: register-balanced, cased,
# license-clean. This is the ONE setup command: it recovers the 2017 news
# tables from the upstream repo (as a mixture component, not a corpus of its
# own), downloads three cased sources, and merges everything.
#
# Sources (never committed; attribution in CORPORA.md):
#   - 2017 news unigram/bigram tables via
#     https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction pinned to
#     290ad7d, SHA-256 verified (no LICENSE upstream: fetched, not shipped)
#   - Wikipedia vi dump 20261001, CC BY-SA 3.0 (formal, cased)
#   - OPUS OpenSubtitles v2024 en-vi (Vietnamese side), ODC-BY (conversational)
#   - th1nhng0/vietnamese-legal-documents, CC BY 4.0 (official/legal, cased)
#
# Everything lands in .tmp/corpus_v2/ (gitignored, ~9 GB peak). Final tables
# land in vndiacritics/data/. Default profile "lite" discards singleton
# bigrams and singleton cased-bigrams after merging (measured: no accuracy
# cost on any gold corpus); --profile full keeps every row.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/.tmp/corpus_v2"
mkdir -p "$WORK"

PROFILE="lite"
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    *) OUT="$1"; shift ;;
  esac
done
OUT="${OUT:-$ROOT/vndiacritics/data}"

PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then PY="$(command -v python3)"; fi

fetch() {
  local url="$1" file="$2"
  if [ ! -f "$file" ]; then
    echo "fetching $(basename "$file")"
    curl -L -C - -o "$file" "$url"
  fi
}

echo "== source 1/4: 2017 news tables (upstream git history, pinned) =="
V1_UPSTREAM="https://github.com/tienthanhdhcn/Vietnamese-Accent-Prediction.git"
V1_PIN="290ad7dd0b8209c93e755e155609ec523d0e7f32"
V1_DIR="$WORK/Vietnamese-Accent-Prediction"
V1_OUT="$WORK/build-v1"
if [ ! -f "$V1_OUT/uni.tsv" ]; then
  if [ ! -d "$V1_DIR/.git" ]; then
    git clone --quiet "$V1_UPSTREAM" "$V1_DIR"
  fi
  mkdir -p "$V1_OUT"
  git -C "$V1_DIR" show "$V1_PIN":datasets/news1gram  > "$V1_OUT/uni.tsv"
  git -C "$V1_DIR" show "$V1_PIN":datasets/news2grams > "$V1_OUT/bi.tsv"
  check_sha() {
    local expected="$1" file="$2"
    echo "$expected  $file" | shasum -a 256 -c --status || {
      echo "ERROR: $(basename "$file") does not match the pinned upstream blob"
      exit 1
    }
  }
  check_sha 54113c8cbc9fcd3114a27ee9e3882309c0e0544608a6bc2c5d6b0ccf4ececfee "$V1_OUT/uni.tsv"
  check_sha 232ba3b7f1e4926f6832410cca0a246e1a0302e01dc8ced4872747ccbf62d557 "$V1_OUT/bi.tsv"
  # The upstream test set is the in-domain eval gold (see tests/test_accuracy_gate.py).
  cp "$V1_DIR/datasets/test.txt" "$WORK/in_domain.txt"
fi

echo "== sources 2-4/4: downloads =="
WIKI_URL="https://dumps.wikimedia.org/viwiki/20261001/viwiki-20261001-pages-articles-multistream.xml.bz2"
WIKI_FILE="$WORK/viwiki-20261001-pages-articles-multistream.xml.bz2"
OPUS_URL="https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/moses/en-vi.txt.zip"
OPUS_FILE="$WORK/opensubtitles_en-vi.txt.zip"
LEGAL_URL="https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents/resolve/main/data/content.parquet"
LEGAL_FILE="$WORK/legal_content.parquet"
fetch "$WIKI_URL" "$WIKI_FILE"
fetch "$OPUS_URL" "$OPUS_FILE"
fetch "$LEGAL_URL" "$LEGAL_FILE"

echo "== sha256 manifest =="
shasum -a 256 "$WIKI_FILE" "$OPUS_FILE" "$LEGAL_FILE" | tee "$WORK/manifest.sha256"

echo "== extracting (deterministic; sampling via --every) =="
if [ ! -f "$WORK/wiki.txt" ]; then
  "$PY" "$ROOT/scripts/extract_wiki_text.py" "$WIKI_FILE" "$WORK/wiki.txt" --every 2
fi
if [ ! -f "$WORK/subtitles.txt" ]; then
  "$PY" "$ROOT/scripts/extract_opus_vi.py" "$OPUS_FILE" "$WORK/subtitles.txt"
fi
if [ ! -f "$WORK/legal.txt" ]; then
  uvx --with pyarrow python3 "$ROOT/scripts/extract_legal_text.py" "$LEGAL_FILE" "$WORK/legal.txt"
fi

echo "== building per-source tables =="
for SRC in wiki subtitles legal; do
  if [ ! -f "$WORK/build-$SRC/uni.tsv" ]; then
    "$PY" "$ROOT/scripts/build_corpus.py" "$WORK/$SRC.txt" --outdir "$WORK/build-$SRC"
  fi
done

echo "== gazetteers (truecaser reinforcement) =="
mkdir -p "$WORK/gazetteer"
NAMEDB_URL="https://raw.githubusercontent.com/duyet/vietnamese-namedb/master"
for F in boy.txt girl.txt; do
  fetch "$NAMEDB_URL/$F" "$WORK/gazetteer/$F"
done
fetch "https://download.geonames.org/export/dump/VN.zip" "$WORK/gazetteer/VN.zip"
if [ ! -f "$WORK/gazetteer/VN.txt" ]; then
  (cd "$WORK/gazetteer" && unzip -oq VN.zip VN.txt)
fi
if [ ! -f "$OUT/names_persons.txt" ]; then
  "$PY" "$ROOT/scripts/build_gazetteer.py" \
    --persons "$WORK/gazetteer" --places "$WORK/gazetteer" --outdir "$OUT"
fi

echo "== merging (news tables carry the news-register mass) =="
MERGE_ARGS=(--inputs "$V1_OUT" "$WORK/build-wiki" "$WORK/build-subtitles" "$WORK/build-legal" --outdir "$OUT")
if [ "$PROFILE" = "lite" ]; then
  MERGE_ARGS+=(--min-count bi.tsv=2 --min-count case_bi.tsv=2)
fi
"$PY" "$ROOT/scripts/merge_corpus.py" "${MERGE_ARGS[@]}"
# K re-measured on this corpus (docs/reports/2026-10-25-corpus-v2.md); the
# auto-scaled default is calibrated for the pre-merge corpus mass.
cat > "$OUT/model.json" <<JSON
{
  "bigram_conf_k": 1000,
  "profile": "$PROFILE",
  "note": "Measured with bench/ab_confidence.py on this mixture (2026-10-25): K=1000 maximizes both golds. Re-run the sweep after any mixture change."
}
JSON
# Build the trie eagerly, keep the merged TSV compressed: the runtime set is
# uni.tsv + bi.trie + bi.meta.json (+ bi.tsv.gz for rebuilds). Skipped when
# marisa-trie is not installed yet (CI installs the package afterwards and
# Model.load builds the trie from the plain TSV).
if "$PY" -c "import marisa_trie" 2>/dev/null; then
  "$PY" - "$ROOT" "$OUT" <<'PYEOF'
import sys
from pathlib import Path
root, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root))
from vndiacritics.data import load_bigram
from vndiacritics.store import BigramStore
BigramStore.build(load_bigram(out / "bi.tsv"), out / "bi.trie")
print("trie built:", out / "bi.trie")
PYEOF
  gzip -9 -f "$OUT/bi.tsv"
else
  echo "marisa-trie not installed yet; leaving bi.tsv plain (Model.load will build the trie)"
fi
# Eval gold (unlicensed upstream test set): fetched, never committed.
cp "$WORK/in_domain.txt" "$OUT/in_domain.txt"

echo "corpus ready at $OUT (profile: $PROFILE)"
