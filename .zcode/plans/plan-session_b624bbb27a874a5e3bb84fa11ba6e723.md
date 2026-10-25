# vndiacritics upgrade roadmap — data + features (case correction)

**TL;DR (Vietnamese):** Kế hoạch 5 workstream: (WS0) viết n-gram builder bằng Python — hiện chưa tồn tại, chặn mọi việc data; (WS1) sửa bug number-context bằng n1-confidence smoothing — ưu tiên 1 theo diagnosis sẵn có; (WS2) corpus v2 quy mô vừa (~15-30M bigrams) cân bằng register từ Wikipedia + legal + OpenSubtitles, tất cả license rõ ràng; (WS3) tính năng `case="correct"` — truecaser thống kê kiểu Moses (sentence-initial + proper nouns + gazetteer); (WS4) đánh version + báo cáo theo văn hóa đo lường của dự án. Neural được ghi nhận nhưng hoãn vô thời hạn với tiêu chí revisit rõ ràng.

## Research foundations (completed this session)

| Finding | Number | Consequence |
|---|---|---|
| Corpus v1 | 216k uni / 5.5M bi rows, **0 uppercase keys** | Case stats phải đến từ corpus mới có case |
| Corpus cleaning ceiling | sửa 2/359 lỗi (+0.02) | Corpus mới chỉ đáng giá để thêm register |
| Number-context root cause | `log((n2+1)/(n1+1))` thiếu n1-confidence: 2/53 thắng 71,291/2.9M | Fix #1, độc lập với data |
| Decoder ceiling | 99.19%; 286/359 có thể sửa | Statistical còn headroom |
| Conversational gap | 89.89% vs 98.54%; từ đệm CÓ sẵn (`nha`=53k) | Thiếu ngữ liệu hội thoại, không phải từ vựng |
| Không có raw-text builder | chỉ có Java `NGramer.java` upstream | WS0 là chặn đường cho mọi việc data |
| SOTA reference | statistical trigram+KN ≈ 97%; Moses truecaser ≈ 98% EN / 85-95% VI; neural CPU 60-200 sent/s | Targets thực tế không cần neural |

Corpus sources (license-clean, fetch-at-setup, không commit/redistribute): Wikipedia vi dump (CC BY-SA 3.0, có case) + `th1nhng0/vietnamese-legal-documents` (CC BY 4.0) + OpenSubtitles en-vi tiếng Việt (ODC-BY, nguồn hội thoại permissive lớn duy nhất). Gazetteers: `duyet/vietnamese-namedb` (MIT), GeoNames VN (CC BY 4.0). `tmnam20/Vietnamese-News` loại trừ (license không rõ).

## Workstreams

### WS1 — Number-context fix (algorithm, priority 1, ~0.5 ngày)
- `restore.py::_best_transition`: thêm n1-confidence vào bigram score qua Jelinek-Mercer interpolation `lambda = n1/(n1+K)` blend về unigram, tham số `bigram_conf_k` (0 = hành vi cũ).
- A/B đo với `bench/ab_confidence.py` (k ∈ {0, 10, 100, 1000, 10000}) trên cả 2 gold corpora + câu bug `tang 12.5% trong nam 2025`; chọn k theo đo.
- Cập nhật pinned test `test_number_adjacency_known_weakness` (test TỰ yêu cầu update khi bug được sửa) + USAGE.md §4.1 + báo cáo dated.

### WS0 — Python n-gram + case-statistics builder (foundation, ~0.5-1 ngày)
- `scripts/build_corpus.py` (stdlib-only, streaming): raw text dir → `uni.tsv`/`bi.tsv` (lowercase) + `case.tsv` (lower/cap/initial_cap counts theo type) + `case_bi.tsv` (bigram capitalized-form) + `abbreviations.txt` (all-caps types).
- Tokenizer mirror semantics của upstream `NGramer.java` (lowercase fold, Vietnamese charset filter) để so sánh v1 được.
- Acceptance: deterministic (same input → same output), output load được qua `Model.load(dir)`, unit tests cho tokenizer (NFD, đ/Đ, punctuation).

### WS2 — Corpus v2 register-balanced, quy mô vừa (~1-2 ngày)
- `scripts/fetch_corpus_v2.sh`: pinned snapshots (Wikipedia dump date, HF revisions) + SHA manifest; `CORPORA.md` ghi nguồn/license/token counts.
- Mixture tunable per-register weights (wiki, legal, subtitles); target 15-30M bigrams, trie ≤ 150MB, load ≤ 2s.
- Gates giữ nguyên: in-domain ≥ 96.0%, out-domain ≥ 95.24%, conversational ≥ 91%. v2 chỉ thành default khi pass; trước đó A/B qua `baseline.py --data/--tag`.

### WS3 — Case correction (`case="correct"`, ~2-3 ngày) — roadmap item đã chốt
- API: `Model.restore(text, case="preserve"|"correct")` default `"preserve"` (zero behavior change); CLI `--case`. Module mới `vndiacritics/truecase.py` (Moses-style):
  1. Sentence-initial: viết hoa trừ function words (theo sentence-initial stats).
  2. Proper nouns: case-variant stats + capitalized bigram continuation (Hà Nội, Bộ Tài chính).
  3. Gazetteer bonus: tên người (namedb MIT) + địa danh (GeoNames CC BY 4.0).
  4. Preserve: acronym (ASCII all-caps/mixed attestation), digits, URL; ALL-CAPS input → title case theo stats.
- Integration tại seam có sẵn (giữa `_viterbi` và `_reapply_case`); positional copy giữ làm fallback.
- Eval: `eval.score` case-sensitive variant; `bench/data/cased_eval_v0.txt` (~200 câu, đủ register + tên riêng); acceptance ≥ 85% case-sensitive accuracy; 58 test cũ pass KHÔNG ĐỔI ở default mode.

### WS4 — Versioning, CI, neural record
- **v0.2.0 = WS1 + WS3** (code changes, default behavior không đổi); **v0.3.0 = WS2 default switch** (data change). Tách code/data để attribution sạch.
- Mỗi workstream một dated report trong `docs/reports/` + một review độc lập trước khi sang workstream tiếp.
- Neural: deferred với tiêu chí revisit (conversational < 91% sau WS2); path đã ghi: distilled encoder + ONNX INT8 (~110MB, 5-15 ms/câu) như `vndiacritics[neural]`.

## Sequencing
WS1 → WS0 → WS2 → WS3, WS4 dệt xen kĩ. Mỗi step có review độc lập trước khi commit/merge.