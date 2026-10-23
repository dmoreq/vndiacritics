# Benchmark: corpus sạch vs corpus gốc

**Ngày**: 2026-10-23
**Commit trước**: `531519e`
**Script**: `scripts/fetch_dicts.sh`, `bench/build_typo_list.py`,
`scripts/make_clean_corpus.py`, `bench/baseline.py`

Kết quả của plan `2026-10-23_090000-corpus-cleaning-and-rebenchmark.md`.

---

## 1. Dữ kiện corpus sạch

| | Corpus gốc | Corpus sạch | Chênh |
|---|---:|---:|---:|
| Unigram types | 216,447 | **212,520** | −3,927 |
| Bigram rows | 5,553,699 | **5,517,054** | −36,645 |
| Token mass bị xoá | — | 42,392 | 0.011% |
| Gold (`in_domain.txt`) | — | **byte-identical** | 0 |

3,927 từ bị xoá có bằng chứng kép:
1. **0/5** từ điển chứng thực (Viet74K, syllable, hunspell, lingskr, underthesea)
2. Twin cùng chữ được **≥2 nguồn** chứng thực và phổ biến **≥100×**

710 từ "cần review" (cả từ và twin đều 0 nguồn) **không bị xoá**.

### Kiểm chứng bảo toàn từ đúng

| Từ | Gốc | Sạch |
|---|---|---|
| `tróng` (từ thật: hết nước) | có | **có** |
| `trong`, `long`, `lỏng`, `khanh`, `bệnh`, `đường` | có | **có** |

`MUST_KEEP` chặn cứng — nếu một từ trong danh sách lọt vào blacklist, script raise.

---

## 2. Accuracy: corpus sạch TỐT HƠN

5 lần chạy xen kẽ, cùng gold, cùng model code, chỉ khác thư mục data:

| Run | Orig acc | Orig sent/s | Clean acc | Clean sent/s |
|---|---:|---:|---:|---:|
| 1 | 96.01% | 2,242 | **96.03%** | 2,583 |
| 2 | 96.01% | 2,298 | **96.03%** | 2,555 |
| 3 | 96.01% | 2,268 | **96.03%** | 2,645 |
| 4 | 96.01% | 2,202 | **96.03%** | 2,530 |
| 5 | 96.01% | 2,213 | **96.03%** | 2,538 |
| **median** | **96.01%** | **2,242** | **96.03%** | **2,555** |

Accuracy **bất biến trong từng cấu hình** qua 5 lần (không phải nhiễu). Đây là cải thiện thật
nhưng rất nhỏ.

| Metric | Orig | Clean | Delta |
|---|---:|---:|---:|
| In-domain accuracy | 96.01% | **96.03%** | **+0.02** |
| In-domain sent/s | 2,242 | **2,555** | **+14.0%** |
| Out-domain accuracy | 95.24% | **95.36%** | **+0.12** |
| Out-domain sent/s | 3,114 | **3,718** | **+19.4%** |

---

## 3. Chính xác điều gì đã thay đổi

So sánh output trên toàn bộ 8,995 token:

**Chỉ 2 token thay đổi:**

| Token | Orig | Clean | Đúng? |
|---|---|---|---|
| 1× | `vầ` | `và` | **Sửa đúng** |
| 1× | `xêm` | `xem` | **Sửa đúng** |

**2/8995 = 0.02% = đúng +2 token trong accuracy.**

Đây chính xác là con số đã dự đoán trong báo cáo trước: "lỗi do từ hiếm = 2 token". Corpus
sạch sửa đúng 2 lỗi đó, không hơn.

### Các ca đã biết KHÔNG được sửa

| Input | Orig | Clean |
|---|---|---|
| `tang 12.5% trong nam 2025` | `tăng 12.5% tróng nằm 2025` | **không đổi** |
| `chao ban` | `chào bán` | **không đổi** |

**Xác nhận**: bug số chen giữa và đại từ ngắn là lỗi **thuật toán**, không phải corpus. Corpus
sạch không chạm tới chúng.

---

## 4. Vì sao nhanh hơn 14–19%?

Xoá 3,927 từ hiếm làm giảm công việc ở hai chỗ:

1. **Ít candidate hơn**: 3,927 âm tiết typo không còn sinh candidate, giảm số cell trong lattice.
2. **Ít bigram hơn**: 36,645 bigram bị xoá → bảng trie nhỏ hơn, tra cứu nhanh hơn.

Đây là lợi ích phụ, không phải mục tiêu. Nhưng nó thật và ổn định qua 5 lần đo.

---

## 5. Kết luận theo bảng quyết định của plan

Plan định nghĩa trước 3 khả năng:

| Kết quả | Diễn giải | Hành động |
|---|---|---|
| clean cao hơn ≥0.05 | Typo có hại thật | Cân nhắc dùng data sạch |
| \|Δ\| < 0.05 | Không có ý nghĩa thực tế | Giữ gốc; typo list làm tài liệu |
| clean thấp hơn | Mất context | Giữ gốc |

**Kết quả thực tế: +0.02 điểm** (96.01% → 96.03%).

Theo tiêu chí plan đã đặt, đây rơi vào ô **"|Δ| < 0.05 — không có ý nghĩa thực tế"**.

### Quyết định

**Giữ `vap/data/` (corpus gốc) làm mặc định.**

Lý do:
- +0.02 điểm = 2 token trên 8,995. Không đủ để biện minh thay đổi mặc định.
- Lợi ích **thật sự đáng kể** là throughput +14–19%, nhưng đó là hiệu ứng phụ của việc xoá từ
  hiếm — có thể đạt được bằng cách khác (tăng beam pruning) mà không mất dữ liệu.
- Giữ corpus gốc bảo toàn khả năng tái lập mọi số đo đã công bố.

Corpus sạch được **lưu như artefact nghiên cứu** (`vap/data-clean/`, gitignored) và tái lập
được bằng script — không phải mặc định.

---

## 6. Điều plan này đã chứng minh

| Giả thuyết | Kết quả |
|---|---|
| "Corpus sạch làm accuracy tăng đáng kể" | **Sai** — chỉ +0.02 |
| "Lỗi do typo là 2 token" | **Đúng** — chính xác 2 token |
| "Bug `12.5%` là lỗi thuật toán, không phải corpus" | **Đúng** — không đổi sau khi làm sạch |
| "Xoá từ hiếm làm nhanh hơn" | **Đúng** — +14–19% throughput |

Lợi ích thật của việc dọn corpus là **tốc độ**, không phải accuracy. Đó là kết luận ngược với
kỳ vọng thông thường ("data sạch → model tốt hơn") và chỉ biết được nhờ đo.

---

## 7. Việc còn lại

| Việc | Trạng thái |
|---|---|
| 710 từ "cần review" | Không xoá; cần tra thêm nguồn nếu muốn |
| Bug `12.5%` mất context | **Chưa sửa** — plan riêng |
| Overfit `tróng nằm` (2/53) | **Chưa sửa** — cần smoothing theo `n1` |
| Register hội thoại 89.89% | **Chưa sửa** — ROI cao nhất còn lại |

Nếu ưu tiên là accuracy chứ không phải tốc độ, việc đúng là **bổ sung corpus hội thoại**, không
phải dọn typo: khoảng cách ở đó là 8.65 điểm, không phải 0.02.
