# CORPORA.md — data sources

The shipped corpus (built into `vndiacritics/data/` by
`scripts/fetch_corpus.sh`) is a register-balanced, cased mixture. No source is
committed or redistributed: everything is downloaded into `.tmp/` at setup and
rebuilt into tables. Update this file whenever a pinned URL or hash changes.

| Source | Role | Register | License | Pinned access |
|---|---|---|---|---|
| 2017 news 1-/2-gram tables via `tienthanhdhcn/Vietnamese-Accent-Prediction` @ `290ad7dd` | mixture component (news-register mass) + the in-domain eval gold | news | **no LICENSE upstream** — fetched at build time, never shipped | git history of the pinned clone; SHA-256 verified by the fetch script |
| Wikipedia vi dump `20261001`, every 2nd article (~200M tokens) | mixture | encyclopedic, cased | **CC BY-SA 3.0** | `https://dumps.wikimedia.org/viwiki/20261001/viwiki-20261001-pages-articles-multistream.xml.bz2` (SHA-256 in `.tmp/corpus_v2/manifest.sha256` after fetch) |
| OPUS OpenSubtitles v2024 en-vi, Vietnamese side (credit-filtered, ~250M tokens) | mixture | conversational, cased | **ODC-BY 1.0** | `https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/moses/en-vi.txt.zip` |
| `th1nhng0/vietnamese-legal-documents` `content.parquet` | mixture | official/legal, cased | **CC BY 4.0** | `https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents/resolve/main/data/content.parquet` |
| `duyet/vietnamese-namedb` (boy.txt/girl.txt) | truecaser gazetteer | person names | **MIT** | `https://raw.githubusercontent.com/duyet/vietnamese-namedb/master/` |
| GeoNames VN | truecaser gazetteer | place names | **CC BY 4.0** | `https://download.geonames.org/export/dump/VN.zip` |

History: through v0.2.x the 2017 news tables were also the standalone default
corpus (built by the former `recover_data.sh`). v0.3.0 removed that runtime
role; the tables survive only as the mixture component above. See
[docs/reports/2026-10-26-single-corpus.md](docs/reports/2026-10-26-single-corpus.md).

## License notes

- **CC BY-SA 3.0 (Wikipedia)**: derived n-gram tables are built at setup and
  never redistributed as a dataset, so share-alike does not attach to this
  repository's code. Attribution to Wikipedia contributors is recorded here.
- **ODC-BY (OpenSubtitles)**: attribution required, no share-alike. Extracts
  are subtitle text; upstream attribution is to OPUS and OpenSubtitles.
- **CC BY 4.0 (legal docs, GeoNames)**: attribution in this file satisfies the
  terms for non-redistributing use.
- Deliberately EXCLUDED: `tmnam20/Vietnamese-News` (license unstated),
  VOZ-HSD / ViHSD / ViCTSD / UIT-VSFC / ViLexNorm (research-only or NC),
  OSCAR (gated). None may be added without a license check.

## Build profile

Default profile **lite** discards singleton bigrams and singleton
cased-bigrams after merging (`--min-count bi.tsv=2 case_bi.tsv=2`): trie
240 MB -> 43 MB with no measured accuracy cost on any gold corpus.
`./scripts/fetch_corpus.sh --profile full` keeps every row.

## Determinism

Wikipedia sampling takes articles by dump order (`--every 2`), so a rebuild
of the same dump yields byte-identical text. Subtitle and legal extracts are
unsampled (filters only). All extraction scripts are deterministic: same
inputs, same output bytes.
