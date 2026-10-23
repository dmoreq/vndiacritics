# Nên dọn corpus hiện tại hay xây corpus mới?

**Ngày**: 2026-10-23
**Commit**: `3e6f236`
**Script**: `bench/corpus_quality.py`

Câu hỏi: cải thiện corpus hiện tại, hay tìm nguồn data tin cậy hơn và huấn luyện lại?

**Trả lời**: **Cả hai đều không phải ưu tiên số một.** Đo lường cho thấy corpus không phải
nút thắt chính. Ưu tiên đúng là sửa **thuật toán ở chỗ mất context**, rồi mới đến corpus —
và khi làm corpus thì nên **mở rộng register**, không phải "làm sạch".

---

## 1. Corpus hiện tại trông thế nào

| Chỉ số | Giá trị |
|---|---:|
| Từ vựng (types) | 216,447 |
| Tổng token | 400,508,022 |
| Bigram rows | 5,553,699 |
| `bi.tsv` trên đĩa | 76.8 MB |

### Phân bố count — long tail rất dài

| Count band | Types | % types | Tokens | % tokens |
|---|---:|---:|---:|---:|
| 1 (hapax) | 68,681 | **31.73%** | 68,681 | 0.02% |
| 2 | 33,048 | 15.27% | 66,096 | 0.02% |
| 3–5 | 37,069 | 17.13% | 139,206 | 0.03% |
| 6–20 | 38,673 | 17.87% | 408,572 | 0.10% |
| 21–100 | 21,631 | 9.99% | 977,662 | 0.24% |
| 101–1k | 11,286 | 5.21% | 3,597,097 | 0.90% |
| **1k+** | **6,059** | **2.80%** | **395,250,708** | **98.69%** |

**82% từ vựng chỉ chiếm 1.31% token.** 31.7% từ chỉ xuất hiện **một lần**.

### Bigram còn nhiễu hơn

| | Rows | % |
|---|---:|---:|
| Tổng | 5,553,699 | 100% |
| Hapax (count = 1) | **1,954,008** | **35.2%** |
| Count ≤ 5 | 3,804,330 | **68.5%** |

Hơn 2/3 bảng bigram là dữ liệu cực thưa. Đây chính là nguồn của bug `tróng nằm` — cặp
2 lần trên mẫu số 53.

---

## 2. Nhưng noise đó gây ra bao nhiêu lỗi? Chỉ 2 token

Đo trực tiếp: đếm các lỗi mà **output sai là một từ hiếm trong corpus** (count < 100).

| | Số token | % corpus |
|---|---:|---:|
| Lỗi do từ hiếm | **2** | **0.02%** |

Hai trường hợp duy nhất:

| Gold | Output sai | Corpus count |
|---|---|---:|
| `và` | `vầ` | 36 |
| `xem` | `xêm` | 30 |

**Đây là phát hiện quan trọng nhất.** Dọn sạch toàn bộ long tail — dù làm được — chỉ sửa
được **2 trong 359 lỗi (0.6%)**. Corpus không phải nút thắt.

---

## 3. Vậy 359 lỗi đến từ đâu?

Đã đo ở báo cáo trước:

| Nhóm | Số | Bản chất |
|---|---:|---|
| Chọn sai form **phổ biến nhất** (rank-0) | **142 (44%)** | Model tin sai, một cách nhất quán |
| Bigram có thể lật được nếu context tốt hơn | 182 (56%) | Thiếu context |

Với 142 lỗi rank-0: model chọn đúng từ phổ biến nhất của âm tiết đó. Corpus **đã có** thống
kê đúng — vấn đề là thống kê bigram không đủ để phân biệt. Thêm data cùng thể loại sẽ
**không** sửa được, vì tỷ lệ vẫn vậy.

---

## 4. Vấn đề corpus thật: gold tự mâu thuẫn

Đây mới là chỗ corpus có vấn đề, và nó **không giải quyết được** bằng cách "làm sạch":

| Input | Các cách gold viết | Nhận xét |
|---|---|---|
| `cho` | `chợ`=87, `chờ`=6, `chỗ`=1 | |
| `tu` | `từ`=45, `tư`=27, `tự`=14, `tu`=9 | |
| `dong` | `đồng`=43, `động`=33, `đông`=9, `đóng`=5 | |
| `nhan` | `nhân`=38, `nhận`=23, `nhắn`=7 | |
| `trong` | `trong`=65, `trọng`=10, `trông`=2, `trống`=2 | |

Tổng: **hàng trăm dạng không dấu có nhiều hơn một cách viết đúng trong gold.**

Không corpus nào sửa được điều này — đây là **nhập nhằng tiếng Việt thật**. Chỉ context rộng
hơn mới phân biệt được `đồng` và `động`.

---

## 5. So sánh ba phương án

### Phương án A: Dọn corpus hiện tại

| Hạng mục | Đánh giá |
|---|---|
| Lỗi sửa được | **2 token (0.02%)** |
| Công sức | Rất cao — phải rà 216k từ, 5.5M bigram |
| Rủi ro | Cao: xoá nhầm tên riêng hợp lệ |
| **Kết luận** | **Không đáng** |

Ngoài ra: corpus là bản 2017 lấy từ git history. Sửa nó làm mất khả năng tái lập số đo cũ.

### Phương án B: Xây corpus mới từ nguồn tin cậy hơn

| Hạng mục | Đánh giá |
|---|---|
| Lỗi sửa được (do noise) | **~2 token** |
| Lỗi sửa được (nhờ register mới) | **Có thể lớn** — hội thoại đang 89.89% |
| Công sức | Cao: crawl + chuẩn hoá + kiểm định |
| **Kết luận** | **Chỉ đáng nếu corpus mới phủ register khác** |

Điểm mấu chốt: xây corpus mới **không** để "sạch hơn" mà để **phủ thể loại khác**. Corpus
hiện tại là news + Wikipedia. Hội thoại kém 8.65 điểm vì thiếu từ đệm khẩu ngữ.

### Phương án C: Sửa thuật toán chỗ mất context

| Hạng mục | Đánh giá |
|---|---|
| Lỗi sửa được | Chưa đo, nhưng nhắm đúng 182 lỗi thiếu context |
| Công sức | **Thấp** — sửa `_viterbi`, không cần data mới |
| Rủi ro | Trung bình, nhưng đo được ngay |
| **Kết luận** | **Ưu tiên số một** |

Bug `tróng nằm` đã chứng minh cơ chế: token số làm đứt context → model rơi về unigram →
từ hiếm thắng nhờ mẫu số nhỏ. Nếu giữ được context qua token số, cả 2 lỗi hiếm biến mất và
một phần 182 lỗi kia cũng cải thiện.

---

## 6. Khuyến nghị theo thứ tự

| # | Việc | Lý do | Chi phí |
|---|---|---|---|
| **1** | Giữ context qua token số/URL/mã | Sửa đúng cơ chế đã chứng minh; 0 data mới | Thấp |
| **2** | Thêm smoothing theo `n1` (yêu cầu `n2` tối thiểu) | Chặn overfit dữ liệu thưa — gốc của `tróng` | Thấp |
| **3** | Bổ sung corpus **hội thoại** (Tatoeba, mạng xã hội) | Đóng khoảng cách 89.89% → ~95% | Trung bình |
| **4** | Dọn corpus hiện tại | Chỉ sửa 2 token | **Không nên** |

### Về "nguồn data tin cậy hơn"

Nếu vẫn muốn xây corpus mới, tiêu chí nên là:

- **Phủ register**, không phải "sạch": thêm hội thoại, văn nói, comment.
- **Có kiểm chính tả**: nguồn có biên tập (báo chính thống) tốt hơn wiki mở.
- **Ghi rõ license** trước khi crawl — hiện corpus 2017 không rõ nguồn từng phần.

Nhưng lưu ý: corpus mới cũng sẽ có long tail tương tự. 31.7% hapax là **bản chất ngôn ngữ**,
không phải lỗi thu thập. Tatoeba hay báo lớn đều vậy.

---

## 7. Kết luận một câu

Corpus hiện tại bẩn thật (35% bigram hapax, 82% từ vựng là long tail) nhưng **chỉ gây 2 lỗi
trong 359**. Xây corpus mới chỉ đáng khi nhằm **mở rộng thể loại văn bản**, không phải để làm
sạch. Việc đúng trước tiên là sửa chỗ model **mất context**, vì đó là cơ chế đã được chứng
minh bằng số và không cần data mới.
