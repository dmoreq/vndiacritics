# CORPORA.md — data sources for corpus v2

The v1 corpus is fetched at setup from an unlicensed upstream repo (see
`scripts/recover_data.sh`). Corpus v2b EXTENDS v1 (v1 stays a mixture
component and the default) with register-balanced sources that carry
explicit licenses. No source is committed or redistributed:
everything is downloaded by `scripts/fetch_corpus_v2.sh` into `.tmp/` and
rebuilt into tables at setup. Update this file whenever a pinned URL or hash
changes.

| Source | Register | Size (extracted) | License | Pinned access |
|---|---|---|---|---|
| Wikipedia vi dump `20261001` | formal, encyclopedic, cased | sampled 1-in-2 articles (~200M tokens) | **CC BY-SA 3.0** | `https://dumps.wikimedia.org/viwiki/20261001/viwiki-20261001-pages-articles-multistream.xml.bz2` (SHA-256 in `.tmp/corpus_v2/manifest.sha256` after fetch) |
| OPUS OpenSubtitles v2024 en-vi, Vietnamese side | conversational dialogue, cased | full vi side after credit filtering (~250M tokens) | **ODC-BY 1.0** | `https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/moses/en-vi.txt.zip` |
| `th1nhng0/vietnamese-legal-documents` `content.parquet` | official/legal, cased | statute prose lines | **CC BY 4.0** | `https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents/resolve/main/data/content.parquet` |

Gazetteers (WS3 truecaser, dev-only):

| Source | Content | License |
|---|---|---|
| `duyet/vietnamese-namedb` | 6,284+ Vietnamese given names + surnames | **MIT** |
| GeoNames VN | Vietnamese place names | **CC BY 4.0** |

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

## Sampling determinism

`--every 2` on Wikipedia takes articles by dump order (page index), so a
rebuild of the same dump yields byte-identical text. Subtitle and legal
extracts are unsampled (filters only). All extraction scripts are
deterministic: same inputs, same output bytes.
