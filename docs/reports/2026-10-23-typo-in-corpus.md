# Typo trong corpus: đồng ý về nguyên tắc, nhưng phải làm đúng cách

**Ngày**: 2026-10-23
**Commit**: `16913ab`
**Script**: `bench/typo_audit.py`

Câu hỏi: corpus huấn luyện bị sai chính tả là không nên — có đúng không?

**Trả lời**: **Đúng về nguyên tắc.** Corpus có typo là lỗi thật, không nên có. Nhưng cách sửa
có hai ngã, và chỉ một ngã an toàn. Chi tiết dưới đây.

---

## 1. Typo có tồn tại, và đo được

Phương pháp: tìm từ hiếm (count < 100) mà **cùng bộ chữ với một từ phổ biến gấp ≥100 lần**
(chỉ khác dấu thanh). Đây chính xác là dạng typo `tróng` vs `trong`.

| | Số lượng |
|---|---:|
| Từ hiếm (count < 100) | 199,011 (91.9% từ vựng) |
| **Nghi là typo** (cùng chữ, bị từ phổ biến áp đảo ≥100×) | **5,155** |
| Token mà chúng chiếm | 73,854 (**0.018% corpus**) |

### Ví dụ thật trong corpus

| Typo | Count | Đúng | Count đúng |
|---|---:|---|---:|
| `đỗng` | 1 | `đồng` | 1,218,589 |
| `duồng` | 1 | `đường` | 483,194 |
| `bếnh` | 1 | `bệnh` | 385,596 |
| `bễnh` | 1 | `bệnh` | 385,596 |
| `xach` | 1 | `xách` | 17,260 |
| `đuong` | 1 | `đường` | 483,194 |

Và ba từ đã gây lỗi thật:

| Typo | Count | Đúng | Count đúng |
|---|---:|---|---:|
| `tróng` | **53** | `trong` | 2,943,468 |
| `vầ` | **36** | `và` | 4,374,499 |
| `xêm` | **30** | `xem` | 230,535 |

Ba từ này không phải lỗi chính tả hiếm gặp — chúng xuất hiện **hàng chục lần** và có ảnh
hưởng thật.

### Ngoài ra còn có dữ liệu hỏng hoàn toàn

Audit phát hiện các key rác:

```
̀n    count=1    (chỉ có dấu, không có chữ)
̃n    count=1
̣n    count=1
ở̉    count=1    -> ở   count=1,452,952
```

Đây là dấu Unicode tách rời (NFD) lọt vào corpus dưới dạng từ riêng. Không có lý do gì để giữ.

---

## 2. Nhưng sửa typo chỉ cứu 2/359 lỗi

Đo trực tiếp: lỗi mà output sai là từ hiếm (count < 100) = **2 token (0.02%)**.

Vì sao? Corpus có 73,854 token typo, nhưng chúng hiếm nên **hầu như không bao giờ thắng**
trong DP. Chỉ khi context bị đứt (token số chen vào, như bug `tróng nằm`), từ hiếm mới có cơ
hội thắng.

**Kết luận quan trọng**: typo không tự gây lỗi. Nó chỉ gây lỗi **khi context đã bị đứt**.

---

## 3. Hai cách sửa, một cách an toàn

### Cách A: Lọc/xoá typo khỏi corpus — RỦI RO CAO

| | |
|---|---|
| Cách làm | Xoá 5,155 từ nghi typo khỏi `uni.tsv` / `bi.tsv` |
| Cứu được | ~2 token |
| Rủi ro | **Xoá nhầm tên riêng hợp lệ** |

Ví dụ rủi ro: `long` là địa danh thật (Long Định, Long An). Nếu bị coi là typo của `lòng`,
xoá nó sẽ làm mất khả năng nhận đúng tên địa danh. Cùng vấn đề với `kong`, `hong`, `khanh`.

Tiêu chí "cùng chữ + hiếm" **không phân biệt được** typo với tên riêng.

### Cách B: Sửa thuật toán để không phụ thuộc vào typo — AN TOÀN

| | |
|---|---|
| Cách làm | Giữ corpus nguyên; sửa chỗ model **mất context** |
| Cứu được | Ít nhất 2 token typo + **một phần 182 lỗi thiếu context** |
| Rủi ro | Không xoá gì, không mất dữ liệu |

Cơ chế đã chứng minh bằng số: với `tang 12.5% trong nam 2025`, token `12.5` làm cột `trong`
nhận UNK cho **mọi** ứng viên. Khi context đứt, model rơi về bigram với từ thay thế, và
`tróng nằm` (2/53) thắng `trong năm` (71,291/2.9M).

Nếu giữ được context qua token số, `tróng` **không bao giờ có cơ hội thắng** — dù nó vẫn nằm
trong corpus.

---

## 4. Điểm cần thống nhất: đây là hai câu hỏi khác nhau

| Câu hỏi | Trả lời |
|---|---|
| "Corpus có typo là không nên?" | **Đúng** — không nên có |
| "Có nên dọn bây giờ?" | Không, **trừ khi** làm cùng lúc với việc tái lập số đo |
| "Dọn có cứu được gì?" | **2/359 lỗi (0.6%)** |
| "Sửa gì trước?" | Giữ context — an toàn hơn, cứu nhiều hơn |

Về nguyên tắc, tôi đồng ý với bạn: một corpus dùng để huấn luyện **nên** sạch chính tả.

Nhưng nếu mục tiêu là **làm tool tốt hơn**, thì dọn typo là việc sai thứ tự: nó tốn công
lớn, có rủi ro xoá nhầm tên riêng, và cứu 0.6% lỗi. Trong khi sửa cách xử lý token số là
thay đổi nhỏ, không mất dữ liệu, và nhắm đúng nhóm lỗi lớn nhất.

---

## 5. Khi nào thì NÊN xây corpus sạch

Có ba tình huống làm việc đó đáng công:

1. **Khi bạn đã có pipeline kiểm chính tả độc lập.** Ví dụ đối chiếu với từ điển tiếng Việt
   chính thức có dấu, hoặc dùng một model spell-check đã kiểm định. Khi đó typo được xác
   định bằng bằng chứng ngoài corpus, không phải bằng phỏng đoán "cùng chữ + hiếm".

2. **Khi corpus mới phủ register mới.** Hội thoại đang 89.89% — kém 8.65 điểm. Đây là lợi
   ích lớn hơn nhiều so với việc dọn typo.

3. **Khi cần công bố/benchmark.** Corpus sạch để so sánh công bằng với model khác.

Tiêu chí corpus mới nếu làm:

| Tiêu chí | Lý do |
|---|---|
| Có kiểm chính tả đối chiếu từ điển | Xác định typo bằng bằng chứng, không phỏng đoán |
| Phủ nhiều register (đặc biệt hội thoại) | Đóng khoảng cách 8.65 điểm |
| Ghi rõ license từng phần | Corpus hiện tại không rõ nguồn từng phần |
| Giữ khả năng tái lập | Lưu version, hash |

---

## 6. Kết luận

**Bạn đúng về nguyên tắc**: corpus huấn luyện có typo là không nên, và corpus hiện tại có
5,155 từ nghi typo cùng một số key Unicode hỏng.

**Nhưng tôi không khuyến nghị dọn ngay**, vì:
- Chỉ cứu **2/359 lỗi (0.6%)**
- Có rủi ro xoá nhầm tên riêng (không phân biệt được bằng tiêu chí heuristic)
- Làm sai lệch số đo đã công bố

**Thay vào đó**: sửa chỗ mất context trước. Typo chỉ gây hại khi context đứt — chặn nguyên
nhân thì typo vô hại. Đó là cách sửa rẻ và an toàn hơn.

Nếu bạn muốn xây corpus sạch, hãy làm **với pipeline kiểm chính tả độc lập** và **kèm register
mới**, chứ không chỉ lọc bớt từ hiếm.
