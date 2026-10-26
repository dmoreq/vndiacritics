#!/usr/bin/env bash
# Fetch and build corpus v2: register-balanced, cased, license-clean.
#
# Sources (never committed; attribution in CORPORA.md):
#   - Wikipedia vi dump 20261001, CC BY-SA 3.0 (formal, cased)
#   - OPUS OpenSubtitles v2024 en-vi (Vietnamese side), ODC-BY (conversational)
#   - th1nhng0/vietnamese-legal-documents, CC BY 4.0 (official/legal, cased)
#
# Everything lands in .tmp/corpus_v2/. Final tables land in
# vndiacritics/data-v2b/ (gitignored). Default profile "lite" discards
# singleton bigrams and singleton cased-bigrams after merging (trie 240MB ->
# 43MB, no measured accuracy cost on any gold corpus); --profile full keeps
# every row.
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
OUT="${OUT:-$ROOT/vndiacritics/data-v2b}"

WIKI_URL="https://dumps.wikimedia.org/viwiki/20261001/viwiki-20261001-pages-articles-multistream.xml.bz2"
WIKI_FILE="$WORK/viwiki-20261001-pages-articles-multistream.xml.bz2"
OPUS_URL="https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/moses/en-vi.txt.zip"
OPUS_FILE="$WORK/opensubtitles_en-vi.txt.zip"
LEGAL_URL="https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents/resolve/main/data/content.parquet"
LEGAL_FILE="$WORK/legal_content.parquet"

fetch() {
  local url="$1" file="$2"
  if [ ! -f "$file" ]; then
    echo "fetching $(basename "$file")"
    curl -L -C - -o "$file" "$url"
  fi
}
fetch "$WIKI_URL" "$WIKI_FILE"
fetch "$OPUS_URL" "$OPUS_FILE"
fetch "$LEGAL_URL" "$LEGAL_FILE"

echo "== sha256 manifest =="
shasum -a 256 "$WIKI_FILE" "$OPUS_FILE" "$LEGAL_FILE" | tee "$WORK/manifest.sha256"

echo "== extracting (deterministic; sampling via --every) =="
PY="$ROOT/.venv/bin/python"
if [ ! -f "$WORK/wiki.txt" ]; then
  "$PY" "$ROOT/scripts/extract_wiki_text.py" "$WIKI_FILE" "$WORK/wiki.txt" --every 2
fi
if [ ! -f "$WORK/subtitles.txt" ]; then
  "$PY" "$ROOT/scripts/extract_opus_vi.py" "$OPUS_FILE" "$WORK/subtitles.txt"
fi
if [ ! -f "$WORK/legal.txt" ]; then
  uvx --with pyarrow "$PY" "$ROOT/scripts/extract_legal_text.py" "$LEGAL_FILE" "$WORK/legal.txt"
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

echo "== merging (v1 news corpus is the fourth source: it carries the news-register mass) =="
MERGE_ARGS=(--inputs "$ROOT/vndiacritics/data" "$WORK/build-wiki" "$WORK/build-subtitles" "$WORK/build-legal" --outdir "$OUT")
if [ "$PROFILE" = "lite" ]; then
  MERGE_ARGS+=(--min-count bi.tsv=2 --min-count case_bi.tsv=2)
fi
"$PY" "$ROOT/scripts/merge_corpus.py" "${MERGE_ARGS[@]}"
# K re-measured on this corpus (docs/reports/2026-10-25-corpus-v2.md); the
# auto-scaled default is calibrated for v1's corpus mass.
cat > "$OUT/model.json" <<JSON
{
  "bigram_conf_k": 1000,
  "profile": "$PROFILE",
  "note": "Measured with bench/ab_confidence.py on this mixture (2026-10-25): K=1000 maximizes both golds. Re-run the sweep after any mixture change."
}
JSON
# Build the trie eagerly and keep the 151 MB merged TSV compressed (same
# convention as recover_data.sh); Model.load rebuilds from bi.tsv.gz when needed.
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

echo "corpus v2 ready"
