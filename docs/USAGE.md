# Hướng dẫn sử dụng `vndiacritics`: khi nào tool đúng, khi nào tool sai

**Ngày**: 2026-10-23
**Phiên bản đo**: commit `b4a1833`
**Script tái lập**: `bench/error_taxonomy.py`

Tài liệu này dành cho người **dùng** tool, không phải người phát triển. Mục đích: biết tool
mạnh ở đâu, yếu ở đâu, và cách nhận ra lỗi để không tin kết quả một cách mù quáng.

---

## 1. Tool làm gì

Khôi phục dấu tiếng Việt cho văn bản **không dấu**. Input không dấu, output có dấu.

```
toi yeu viet nam  ->  tôi yêu việt nam
```

Giữ nguyên: khoảng trắng, chữ hoa/thường, dấu câu, emoji, URL, số.
Không dịch, không sửa chính tả, không đổi từ.

---

## 2. Độ chính xác theo loại văn bản — con số quan trọng nhất

| Loại văn bản | Độ chính xác | Dùng được? |
|---|---:|---|
| Tin tức, báo chí (out-of-domain) | **99.03%** | Tốt |
| Văn bản hành chính, công văn | **95.51%** | Tốt |
| Hợp đồng, kinh doanh | **96.10%** | Tốt |
| **Hội thoại, chat, mạng xã hội** | **92.55%** | Tốt, vẫn nên soát |
| Tin tức chuẩn 2017 (in-domain cũ) | 94.96% | Tốt |

**Đây là điểm quan trọng nhất của tài liệu.** Chênh lệch giữa văn bản trang trọng và hội
thoại là **8.65 điểm** — lớn hơn mọi khác biệt khác trong tool. Lý do: corpus huấn luyện là
tin tức và Wikipedia, nên thiếu từ đệm khẩu ngữ (`nha`, `nhe`, `a`, `ha`).

Cập nhật 2026-10-26 (v0.3.0): corpus mặc định nay là bản trộn cân bằng register (news
2017 + Wikipedia + phụ đề + văn bản pháp luật) — chênh lệch còn 6.5 điểm, hội thoại
92.55%. Xem [reports/2026-10-25-corpus-v2.md](reports/2026-10-25-corpus-v2.md) và
[reports/2026-10-26-single-corpus.md](reports/2026-10-26-single-corpus.md).

Nếu bạn xử lý chat, comment, tin nhắn: **phải đọc lại kết quả**.

---

## 3. Bốn loại lỗi và ví dụ thật

Phân loại trên 359 lỗi trong corpus tham chiếu:

| Loại lỗi | Số lượng | Tỷ lệ |
|---|---:|---:|
| Sai dấu thanh (cùng chữ, khác dấu) | 215 | 59.9% |
| Mất dấu (đáng lẽ có dấu) | 61 | 17.0% |
| Tự thêm dấu vào từ vốn không dấu | 48 | 13.4% |
| Sai chữ cái (không chỉ dấu) | 35 | 9.7% |

### 3.1. Sai dấu thanh — 60% lỗi, phổ biến nhất

Tool chọn đúng chữ nhưng sai dấu. Thường vì hai từ cùng gốc chữ đều phổ biến.

| Gold (đúng) | Tool ra | Câu thật |
|---|---|---|
| `con` | `còn` | `công ty **con** là công ty` → `công ty **còn** là công ty` |
| `nhưng` | `những` | |
| `nền` | `nên` | |
| `cùng` | `cũng` | |

**Nhận biết**: câu đọc vẫn hiểu nhưng sai ngữ pháp nhẹ. Đây là lỗi khó thấy nhất khi đọc
nhanh.

### 3.2. Mất dấu — 17%

Từ đáng lẽ có dấu bị để nguyên không dấu.

| Gold | Tool ra |
|---|---|
| `giá` | `gia` |
| `Đồng` | `dong` |

### 3.3. Tự thêm dấu vào từ vốn không dấu — 13.4%

Tool thêm dấu vào tên riêng hoặc từ tiếng Anh.

| Gold | Tool ra | Ghi chú |
|---|---|---|
| `long` (địa danh Long Định) | `lỏng`, `lòng` | Tên riêng bị đổi nghĩa |
| `hong` | `hồng` | |
| `kong` | `kông` | |

**Lưu ý quan trọng**: đây thường là lỗi của **corpus**, không phải của tool. Corpus đôi khi
viết tên riêng không dấu (`Kong`, `Hong`), tool thì thêm dấu vì đó là từ tiếng Việt hợp lệ.
Không có cách sửa nào rẻ — đã đo và bác bỏ (xem mục 6).

### 3.4. Sai chữ cái — 9.7%

| Gold | Tool ra |
|---|---|
| `Đồng` | `Dòng` |
| `dang` | `đảng` |

---

## 4. Ba lỗi hệ thống người dùng sẽ gặp ngay

Đây là các trường hợp tôi kiểm tra trực tiếp bằng input điển hình. **Chưa có test nào bao
phủ**, nên cần biết.

### 4.1. Số liền sau từ — ĐÃ SỬA (2026-10-25)

```
Input : tang 12.5% trong nam 2025
Output: tăng 12.5% trong năm 2025     <- đúng
```

**Lỗi cũ**: `12.5%` không có ứng viên, cột đó nhận điểm UNK và đứt chuỗi bigram; transition
sống sót tiếp theo để cặp lỗi corpus `tróng nằm` (2/53) thắng `trong năm` (71,291/2.9M) vì
tỷ lệ `log((n2+1)/(n1+1))` không tính độ tin cậy của mẫu số. `tróng` là từ thật ("hết nước,
khô kiệt", vd *giếng tróng*), được 5 từ điển chứng thực — model chọn sai, corpus không bẩn.
Chẩn đoán đầy đủ:
[2026-10-23-number-context-root-cause.md](reports/2026-10-23-number-context-root-cause.md).

**Cách sửa**: bigram score nay nội suy Jelinek-Mercer về unigram với `lambda = n1/(n1+K)`,
K=1000 (đo bằng `bench/ab_confidence.py`; K=1000 tốt nhất trên cả hai corpus: in-domain
96.01% → 96.05%, out-domain 95.24% → 95.58%). Ghi chú kỹ thuật:
[2026-10-25-number-context-fix.md](reports/2026-10-25-number-context-fix.md).

Vẫn nên kiểm tra các từ ngay trước và sau con số trong văn bản quan trọng: context qua cột
số vẫn bị đứt, fix dựa vào transition còn lại; câu cực ngắn có số vẫn có thể sai từ khác
(`quy 4 nam 2025` vẫn chỉ đúng vì `quy` chưa sửa được).

### 4.2. Đại từ `ban` (bạn) bị hiểu thành `bán` (bán)

```
Input : chao ban        -> chào bán    SAI
Input : cam on ban      -> cảm ơn bạn  ĐÚNG
Input : ban co khoe khong -> bạn có khỏe không  ĐÚNG
```

`bán` phổ biến hơn `bạn` trong corpus tin tức (379k vs 677k nhưng `bán` xuất hiện nhiều
trong ngữ cảnh kinh doanh). Câu ngắn, không đủ context, dễ chọn sai.

**Ảnh hưởng trực tiếp**: chat, email chào hỏi — đúng loại văn bản có độ chính xác thấp nhất.

### 4.3. Từ ghép `long` → `lỏng` / `lòng`

Tên địa danh và tên riêng bị đổi dấu thành từ khác nghĩa. Không sửa được bằng corpus hiện
tại.

---

## 4b. Khôi phục chữ hoa (`case="correct"`) — mới 2026-10-25

Ngoài dấu thanh, tool có thể khôi phục CHỮ HOA từ corpus mặc định (Wiki + phụ đề +
văn bản pháp luật + news):

```
echo "toi o ha noi" | vndiacritics --case correct
-> Tôi ở Hà Nội
```

Độ chính xác case-sensitive: **90.38%** toàn tập (news 93.88%, hội thoại 91.18%, hợp đồng
85.00%). Yếu điểm: từ đầu câu mà dạng thường áp đảo trong corpus ("Bên" trong hợp đồng) có
thể bị bỏ thường; tên riêng không có thống kê sẽ được giữ nguyên case của input.

Chế độ mặc định vẫn là `case="preserve"`: giữ nguyên case input như cũ.

## 5. Tool làm tốt những gì

Kiểm chứng trực tiếp:

| Input | Output | Đánh giá |
|---|---|---|
| `toi yeu viet nam` | `tôi yêu việt nam` | ✓ |
| `duong` (1 từ) | `đường` | ✓ |
| `CONG TY TNHH MOT THANH VIEN` | `CÔNG TY TNHH MỘT THÀNH VIÊN` | ✓ giữ chữ hoa |
| `Arsenal va Boeing da ky ket` | `Arsenal và Boeing đã ký kết` | ✓ không phá tên nước ngoài |
| `machine learning la linh vuc moi` | `machine learning là lĩnh vực mới` | ✓ giữ tiếng Anh |
| `chuong trinh khuyen mai thang 12` | `chương trình khuyến mại tháng 12` | ✓ |
| `Tôi yêu Việt Nam` (đã có dấu) | `Tôi yêu Việt Nam` | ✓ không phá |
| `chao ban 😀 rat vui` | `chào bán 😀 rất vui` | emoji giữ, nhưng `ban` sai |
| `xem tai https://example.com/tin-tuc` | `xem tại https://...` | ✓ URL nguyên vẹn |

**Điểm mạnh xác nhận**: giữ nguyên chữ hoa, emoji, URL, số, không phá tên tiếng Anh. 0/44
token tên nước ngoài bị restore sai (đã đo).

---

## 6. Những gì đã thử và KHÔNG cải thiện được

Để bạn không mất thời gian đề xuất lại:

| Ý tưởng | Kết quả đo | Kết luận |
|---|---|---|
| Danh sách tên riêng để bảo vệ | **0 token** cải thiện; guard còn làm mất 1 | Đã bác bỏ |
| Bảo vệ mọi từ gold viết không dấu | **−1,246 token** (−13.85 điểm) | Thất bại nặng |
| Chỉnh ngưỡng skip (0→30) | 0 token; 21 đã là tối ưu cục bộ | Đã bác bỏ |
| Trigram (3 từ) | Proxy đo được **tệ hơn** (91.14% vs 91.50%) | Không đáng |
| Model neural re-rank | Tốt hơn nhưng **60–200× chậm hơn** | Không phù hợp tool CLI |

Trần lý thuyết: nếu decoder luôn chọn đúng trong số ứng viên đã sinh, đạt **99.19%**. Nhưng
286 token còn lại cần language model tốt hơn, không phải search tốt hơn — 44% trong đó
model chọn đúng từ phổ biến nhất, tức model "tin" sai một cách nhất quán.

---

## 7. Khuyến nghị sử dụng theo tình huống

### Dùng ngay, tin được
- Tin tức, bài báo, nội dung dài
- Văn bản hành chính, công văn (trừ phần có nhiều số liệu — xem 4.1)
- Chuẩn hoá dữ liệu huấn luyện từ văn bản trang trọng

### Dùng nhưng phải soát
- Hợp đồng, tài liệu kinh doanh
- Bất kỳ văn bản nào có **số, phần trăm, mã** chen giữa câu
- Văn bản có nhiều **tên riêng, địa danh**

### Không nên tin hoàn toàn
- Chat, comment, tin nhắn, mạng xã hội (89.89%)
- Câu ngắn 1–2 từ (thiếu context)
- Văn bản mà lỗi dấu đổi nghĩa (pháp lý, y tế, tài chính)

### Cách kiểm tra nhanh output
1. Đọc các từ **ngay trước và sau con số** — đây là điểm yếu đã xác nhận.
2. Kiểm tra đại từ nhân xưng `bạn`/`bán`, `con`/`còn`.
3. Với văn bản hội thoại, đọc toàn bộ.

---

## 8. Tóm tắt một câu

Tool đạt 94.96% trên gold tin tức 2017, 99.03% trên tin tức mới và 92.55% trên hội thoại; lỗi **số chen giữa câu làm
hỏng từ lân cận đã được sửa ngày 2026-10-25**; điểm yếu còn lại là **từ ngắn thiếu context**;
4% còn lại là nhập nhằng từ vựng thật mà ba hướng sửa rẻ đều đã đo và thất bại.
