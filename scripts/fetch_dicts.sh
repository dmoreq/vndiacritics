#!/usr/bin/env bash
# Fetch the five dictionaries used for multi-source typo verification.
# Licenses differ per source; see docs/reports/2026-10-23-multi-source-consensus-typo.md.
#
# These files are gitignored (.tmp/). Re-running overwrites them.
set -euo pipefail
D="$(dirname "$0")/../.tmp/dicts"
mkdir -p "$D"
raw=https://raw.githubusercontent.com

echo "fetching dictionaries into $D"
curl -sL -o "$D/Viet74K.txt"  "$raw/duyet/vietnamese-wordlist/master/Viet74K.txt"
curl -sL -o "$D/vi_VN.dic"    "$raw/titoBouzout/Dictionaries/master/Vietnamese_vi_VN.dic"
curl -sL -o "$D/vi_dict.txt"  "$raw/lingskr/Vietnamese-Corpus-and-Dictionary/master/vi_dict.txt"
curl -sL -o "$D/uts.txt"      "$raw/undertheseanlp/dictionary/master/dictionary/words.txt"
curl -sL -o "$D/syl_raw.txt"  "$raw/vietnameselanguage/syllable/master/vietnamesesyllable.txt"

# The syllable list ships as UTF-16; normalise to UTF-8 without a BOM.
python3 - "$D/syl_raw.txt" "$D/syllable_clean.txt" <<'PY'
import sys

raw = open(sys.argv[1], "rb").read()
text = raw.decode("utf-16")
lines = [line.strip() for line in text.splitlines() if line.strip()]
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print(f"{len(lines)} syllables -> {sys.argv[2]}")
PY

wc -l "$D"/Viet74K.txt "$D"/vi_VN.dic "$D"/vi_dict.txt "$D"/uts.txt "$D"/syllable_clean.txt
