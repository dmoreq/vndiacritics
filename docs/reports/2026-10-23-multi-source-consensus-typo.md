# Phát hiện typo bằng đồng thuận đa nguồn từ điển

**Ngày**: 2026-10-23
**Commit**: `cb8ab25`
**Script**: `bench/consensus_check.py`, `bench/typo_detect.py`
**Từ điển**: tải trong `.tmp/dicts/` (gitignored)

Quy tắc bạn đặt ra: từ được nhiều nguồn đồng thuận là đúng; từ chỉ có một nguồn thì tra
cứu thêm.

Đã thực hiện. Kết quả **phủ định một giả định quan trọng của tôi trước đó**.

---

## 1. Năm nguồn đã tải

| Nguồn | Entries | Bản chất |
|---|---:|---|
| `Viet74K.txt` (duyet) | 72,535 | Danh sách từ phổ biến, xếp theo tần suất |
| `syllable_clean.txt` (vietnameselanguage) | 6,653 | Âm tiết hợp lệ về ngữ âm |
| `vi_VN.dic` (titoBouzout / hunspell-spellcheck-vi) | 6,634 | Từ điển hunspell dùng cho spell-check |
| `vi_dict.txt` (lingskr) | 6,643 | Từ điển rút từ corpus báo chí |
| `uts.txt` (underthesea) | 79,226 | **Có trường `source` ghi rõ nguồn gốc từng từ** |

### underthesea là nguồn đặc biệt

Mỗi entry ghi rõ nguồn nào chứng thực:

```json
{"text": "a", "source": ["hongocduc", "tudientv", "wiktionary"]}
```

Phân bố đồng thuận trong underthesea:

| Số nguồn upstream | Số từ |
|---|---:|
| 1 nguồn | 35,096 |
| 2 nguồn | 25,297 |
| **3 nguồn** | **18,833** |

Ba nguồn upstream độc lập: `hongocduc` (73,172 từ), `tudientv` (36,533), `wiktionary`
(32,484).

---

## 2. KẾT QUẢ BẤT NGỜ: `tróng` là từ THẬT

Trước đây tôi kết luận `tróng` là typo của `trong`. **Sai.** Đối chiếu 5 nguồn:

| Từ | Đồng thuận | Kết luận |
|---|---:|---|
| `tróng` | **5/5** | **TỪ THẬT** |
| `trong` | 5/5 | Từ thật |
| `và` | 5/5 | Từ thật |
| `xem` | 5/5 | Từ thật |
| `đường` | 5/5 | Từ thật |
| `bệnh` | 5/5 | Từ thật |
| `long` | 5/5 | Từ thật |
| `lỏng` | 5/5 | Từ thật |
| `khanh` | 5/5 | Từ thật |
| `vầ` | **0/5** | **Không nguồn nào** → typo |
| `xêm` | **0/5** | **Không nguồn nào** → typo |
| `duồng` | **0/5** | **Không nguồn nào** → typo |
| `bếnh` | **0/5** | typo |
| `kong` | 0/5 | tên riêng nước ngoài |
| `arsenal` | 0/5 | tên riêng nước ngoài |
| `boeing` | 0/5 | tên riêng nước ngoài |

`tróng` nghĩa là **"hết nước, khô kiệt"** (ví dụ *giếng tróng*) — từ thật, hiếm nhưng hợp lệ.

### Hệ quả: bug `tăng 12.5% tróng nằm 2025` KHÔNG phải lỗi corpus

Phân rã đúng:

1. Token `12.5` làm đứt context → **nguyên nhân chính** (đã chứng minh)
2. Model chọn `tróng` (count 53) thay vì `trong` (count 2.9M) → **chọn sai từ**
3. Vì `tróng nằm` = 2/53 thắng `trong năm` = 71,291/2,943,468 → **overfit dữ liệu thưa**

Corpus **không bẩn** ở đây. `tróng` là từ hợp lệ nằm trong từ điển. Lỗi hoàn toàn thuộc về
thuật toán.

Điều này củng cố kết luận trước: ưu tiên là sửa decoder, không phải dọn corpus.

---

## 3. Đối chiếu toàn bộ ứng viên trong corpus

Chạy trên 5,035 từ nghi vấn (hiếm, cùng chữ với từ phổ biến gấp ≥100 lần):

| Phân loại | Số từ | Ý nghĩa |
|---|---:|---|
| **ABSENT** (0 nguồn) | **3,987** | Không nguồn nào chứng thực |
| **CORRECT** (≥3 nguồn) | **947** | Từ thật, chỉ hiếm |
| UNVERIFIED (1 nguồn) | 99 | Cần tra cứu thêm |
| LIKELY CORRECT (underthesea 2+ upstream) | 2 | |

### Phân tích

**947 từ "nghi typo" hoá ra là từ thật** (19% tổng ứng viên). Đây là bằng chứng định lượng
rằng heuristic "cùng chữ + hiếm" trước đây **sai 19% trường hợp** — nếu tôi xoá chúng, sẽ
mất 947 từ tiếng Việt hợp lệ.

**3,987 từ ABSENT** — nhưng nhóm này **trộn lẫn** hai loại không phân biệt được bằng từ điển:

| Loại thật sự | Ví dụ | Nên xoá? |
|---|---|---|
| Typo thật | `vầ`, `xêm`, `duồng`, `bếnh` | Có |
| Tên riêng nước ngoài | `kong`, `arsenal`, `boeing` | **Không** |
| Tên riêng Việt | nhiều địa danh, nhân danh | **Không** |
| Chuỗi Unicode hỏng | `̀n`, `ở̉`, `̣̣t` | Có |
| Từ mới / tiếng lóng | | Không |

**Đây là giới hạn của phương pháp từ điển**: ABSENT không đồng nghĩa typo.

---

## 4. Cách tách typo khỏi tên riêng mà không cần phỏng đoán

Từ điển một mình không đủ. Cần thêm một tín hiệu: **có "twin" có dấu phổ biến hơn không**.

| Điều kiện | Kết luận |
|---|---|
| ABSENT + cùng chữ với từ CÓ trong từ điển, phổ biến ≥100× | **Typo** (vd `bếnh` ↔ `bệnh`) |
| ABSENT + không có twin có dấu | **Tên riêng hoặc từ ngoại lai** (vd `kong`, `arsenal`) |
| ABSENT + chứa ký tự Unicode tổ hợp đơn lẻ | **Dữ liệu hỏng** (vd `̀n`) |
| ABSENT + chỉ 1 nguồn trong underthesea | **Cần tra cứu thêm** |

Bộ lọc này cho ra tập typo **có thể xoá an toàn** vì mỗi từ đều có bằng chứng kép:
(a) không nguồn nào chứng thực, và (b) có từ đúng cùng chữ được nguồn chứng thực.

---

## 5. Công cụ đã viết

### `bench/consensus_check.py`

```bash
# Kiểm tra từ cụ thể
python bench/consensus_check.py --verify tróng vầ kong arsenal

# Quét toàn bộ ứng viên trong corpus
python bench/consensus_check.py --corpus-typos
```

Phân loại theo đúng quy tắc bạn đặt:
- ≥3 nguồn → **CORRECT (strong consensus)**
- 2 nguồn → **CORRECT (some consensus)**
- 1 nguồn + underthesea ≥2 upstream → **LIKELY CORRECT**
- 1 nguồn → **UNVERIFIED (single source, needs lookup)**
- 0 nguồn → **ABSENT**

### `bench/typo_detect.py`

Danh sách ứng viên typo với bằng chứng (không tự xoá gì).

---

## 6. Khuyến nghị

| # | Việc | Đánh giá |
|---|---|---|
| 1 | **Giữ nguyên corpus** | `tróng` là từ thật; xoá theo heuristic sẽ mất 947 từ hợp lệ |
| 2 | Sửa decoder (context qua token số) | Cứu cả 2 lỗi đã biết + một phần 182 lỗi |
| 3 | Nếu muốn dọn corpus: dùng bộ lọc 4 điều kiện ở mục 4 | An toàn, nhưng vẫn chỉ cứu ~2/359 lỗi |
| 4 | Cải thiện smoothing theo `n1` | Chặn overfit `tróng nằm` 2/53 |

**Xoá 3,987 từ ABSENT là sai lầm** — phần lớn là tên riêng. Đây là điều tôi gần làm và đã
tránh được nhờ đối chiếu đa nguồn theo yêu cầu của bạn.

---

## 7. Correction

Trong báo cáo trước tôi khẳng định `tróng` là **typo của `trong`** và dùng nó làm ví dụ chính
cho "corpus bẩn". Đối chiếu 5 nguồn cho thấy **`tróng` được 5/5 nguồn đồng thuận là từ thật**
(nghĩa: hết nước, khô kiệt).

Sai sót này ảnh hưởng đến kết luận: tôi đã dùng `tróng` để lập luận corpus bẩn, trong khi
thực tế đó là thuần lỗi thuật toán. Kết luận cuối (ưu tiên sửa decoder) không đổi, nhưng lý lẽ
đã được sửa từ "corpus bẩn" thành "chọn sai từ trong tập từ hợp lệ".
