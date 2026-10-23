# Tại sao `tăng 12.5% tróng nằm 2025`? — Chẩn đoán gốc

**Ngày**: 2026-10-23
**Commit**: `291d8e1`
**Script**: `/tmp/mech.py`, `/tmp/trace.py`, `/tmp/root.py` (không commit, chỉ để tra)

Câu hỏi: `tróng` không phải từ tiếng Việt thông dụng — lỗi này do data hay do thuật toán?

**Trả lời ngắn**: Cả hai, và yếu tố quyết định là **thuật toán**, không phải data.

---

## 1. Data có chứa `tróng` — đây là sự thật

| Từ | Unigram count |
|---|---:|
| `trong` | 2,943,468 |
| `tróng` | **53** |

`tróng` **có** trong corpus, không phải bịa ra. Kiểm tra trực tiếp `vap/data/uni.tsv`:

```
tróng	53
```

Ngữ cảnh của nó trong `bi.tsv`:

```
tróng hành    tróng toàn    tróng suốt    tróng tiếp
tróng thì     tróng câm     tróng khi     tróng lại
```

Đây là **typo thật trong corpus** — đúng phải là `trong hành`, `trong toàn`, `trong suốt`.
Nguồn gốc: corpus lấy từ Wikipedia/news tiếng Việt chưa qua kiểm chính tả.

Vậy câu hỏi đúng không phải "sao có từ này" mà "sao model **chọn** nó".

---

## 2. Chuỗi tính điểm — số thật

Input: `tang 12.5% trong nam 2025`

Cột ứng viên:

| # | Token | Ứng viên | Ghi chú |
|---|---|---|---|
| 0 | `tang` | `tăng`, `tầng`, `tặng`, `tang`... | 8 ứng viên |
| 1 | `12.5%` | `12.5` | **1 ứng viên, không phải từ tiếng Việt** |
| 2 | `trong` | `trong`, `trọng`, `trồng`, `trông`, `trống`, `tròng`, `tróng`... | 8 ứng viên |
| 3 | `nam` | `năm`, `nam`, `nằm`, `nắm`... | 8 ứng viên |
| 4 | `2025` | `2025` | 1 ứng viên |

### Điểm từng bước

Cột 1 là `12.5` — không có bigram nào với nó, nên **mọi** ứng viên cột 2 nhận cùng điểm UNK:

| Cột 2 candidate | Điểm |
|---|---:|
| `trong` | −20.5152 |
| `trọng` | −20.5152 |
| `tróng` | −20.5152 |

**Tất cả hòa nhau ở UNK = −20.5152.** Context bị đứt hoàn toàn ở đây.

### Cột 3 quyết định

Với `prev = trong`:
| Candidate | n2 | n1 | Điểm |
|---|---:|---:|---:|
| `năm` | 71,291 | 2,943,468 | **−3.7206** |
| `nằm` | 10 | 2,943,468 | −12.4972 |

Với `prev = tróng`:
| Candidate | n2 | n1 | Điểm |
|---|---:|---:|---:|
| `năm` | 0 | 53 | −20.5152 |
| `nằm` | **2** | 53 | **−2.8904** |

### Tổng hai đường đi

| Đường | Cột 2 | Cột 3 | Tổng |
|---|---:|---:|---:|
| **A (đúng)**: `trong` → `năm` | −20.5152 | −3.7206 | **−24.2358** |
| **B (sai)**: `tróng` → `nằm` | −20.5152 | −2.8904 | **−23.4056** |

**Đường B thắng 0.83 điểm.**

---

## 3. Nguyên nhân thật: xác suất giả tạo từ mẫu số nhỏ

Công thức hiện tại:

```
score = log((n2 + 1) / (n1 + 1))
```

| Cặp | n2 (bigram) | n1 (unigram prev) | Tỷ lệ | log |
|---|---:|---:|---:|---:|
| `trong năm` | 71,291 | 2,943,468 | 2.42% | −3.72 |
| `tróng nằm` | **2** | **53** | **3.77%** | **−2.89** |

`tróng nằm` chỉ xuất hiện **2 lần** nhưng cho xác suất **cao hơn** `trong năm` (71,291 lần).
Vì mẫu số `n1 = 53` quá nhỏ — chỉ cần 2 lần trùng là đủ tỷ lệ cao.

**Đây là overfitting vào dữ liệu thưa.** Model tin một cặp xuất hiện 2 lần hơn một cặp
xuất hiện 71 nghìn lần.

### Xác nhận: cùng cơ chế với `long` → `lỏng`

| Từ | Count |
|---|---:|
| `long` (đúng, địa danh) | 116,772 |
| `lỏng` (sai) | 13,314 |

`lỏng` count thấp → bigram với nó có xác suất cao giả tạo → thắng `long`.

---

## 4. Thứ tự nguyên nhân (quan trọng)

Tôi đã kiểm tra và loại bỏ hai giả thuyết sai:

| Giả thuyết | Kiểm chứng | Kết luận |
|---|---|---|
| Công thức `(n2+1)/(n1+1)` sai, phải là `n2/n1` | `n2/n1` cho A=−3.72, B=−3.28 → **A vẫn thua** | **Không phải nguyên nhân** |
| Data bẩn (không có từ `tróng`) | `tróng` có 53 lần trong corpus | Data bẩn **là điều kiện**, không phải nguyên nhân |

**Nguyên nhân thật, xếp theo đóng góp:**

1. **Thiếu smoothing theo độ tin cậy của `n1`** (chính). Model không phân biệt "2/53 với mẫu số 53" và "71,291/2.9M với mẫu số 2.9M".
2. **Context bị đứt bởi token số** (điều kiện kích hoạt). Nếu không có `12.5`, `prev` sẽ là `tăng` và `trong` thắng ngay — đã kiểm tra: `thang 12` → `tháng 12` ✓, `nam 2025` → `năm 2025` ✓.
3. **Corpus có typo `tróng`** (điều kiện cần). Nếu `tróng` không tồn tại, không có đường B.

---

## 5. Sửa được không?

| Hướng | Vấn đề | Đánh giá |
|---|---|---|
| Loại token số khỏi DP | Đúng hướng — khôi phục context | **Khả thi, tôi chưa thử** |
| Smoothing theo `n1` (vd. yêu cầu `n2 >= 3` mới tin) | Có thể giảm overfit | Cần đo, có thể mất accuracy nơi khác |
| Xoá typo khỏi corpus | Corpus cố định từ 2017; sửa corpus = thay đổi kết quả đo | Không nên |
| Tăng beam | Không ảnh hưởng — cả 2 ứng viên đều trong beam | Vô ích |

**Điểm quan trọng**: đây **không phải** lỗi data đơn thuần. Data chỉ tạo ra cơ hội. Lỗi nằm ở
việc model coi "2/53" là bằng chứng mạnh hơn "71,291/2,943,468".

---

## 6. Ảnh hưởng tới người dùng

Bất kỳ câu nào có **token số chen giữa** đều có thể kích hoạt:

- Model mất context ở cả hai phía của con số.
- Từ hiếm trong corpus được "thưởng" vì mẫu số nhỏ.
- Kết quả là từ vô nghĩa (`tróng`) xuất hiện trong output.

Vì corpus là tin tài chính/bất động sản, các từ hiếm bị thưởng thường là **tên riêng và
typo**, nên lỗi hay rơi vào đúng chỗ người đọc dễ thấy.

**Khuyến nghị cho người dùng** (đã có trong `docs/USAGE.md` mục 4.1): soát lại các từ ngay
trước và sau con số.

---

## 7. Correction

Trong hội thoại tôi đã nói *"`tróng` không phải từ tiếng Việt nên chắc model bịa"*. Sai —
`tróng` có 53 lần trong corpus. Và tôi cũng đoán công thức `n2/n1` sẽ sửa được; kiểm chứng
cho thấy **không** (A vẫn thua). Cả hai phát biểu đều đã được sửa bằng đo lường trong tài
liệu này.
