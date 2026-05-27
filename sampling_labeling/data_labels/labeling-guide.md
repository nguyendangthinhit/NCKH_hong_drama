# Hướng dẫn Gán nhãn Dữ liệu (Labeling Guide)

**Mục đích:** Tạo gold dataset 4000 mẫu (2k Showbiz + 2k Education) cho fine-tune PhoBERT, theo phương pháp **human-in-the-loop verification** (LLM gán → người verify).

**Lợi ích:** Tiết kiệm 70-80% thời gian so với label tay từ đầu.

---

## Cấu trúc thư mục

```
data_labels/
├── labeling-guide.md                    (file này)
├── showbiz/
│   ├── pool_llm_labeled.json            (input: 5000 mẫu LLM-labeled)
│   ├── batch_01_to_verify.xlsx          (output để verify)
│   ├── batch_01_verified.xlsx           (sau khi verify)
│   ├── ...
│   ├── verified_final.json              (gộp tất cả batch, 2000 mẫu)
│   └── splits/
│       ├── train.json                   (1400)
│       ├── val.json                     (300)
│       └── test.json                    (300)
└── education/
    └── ... (tương tự)
```

---

## Quy trình tổng thể

```
Bước 1: Sample 5000 mẫu mỗi domain từ data đã LLM-label
Bước 2: Chia thành batch 500 mẫu
Bước 3: Mỗi batch export sang Excel/CSV → người verify
Bước 4: Verifier sửa nhãn sai, gắn cờ "uncertain" cho mẫu khó
Bước 5: Mẫu uncertain → 2 người verify chéo (consensus)
Bước 6: Gộp lại verified_final.json → split 70/15/15
```

---

## Bộ nhãn

### Showbiz (6 nhãn)

| Code | Nhãn | Mô tả ngắn | Ví dụ |
|---|---|---|---|
| `phan_no` | Phẫn nộ | Tức giận, lên án mạnh | "Tức điên người luôn, đồ vô liêm sỉ" |
| `ca_khia` | Cà khịa | Mỉa mai, châm biếm có ý chỉ trích | "Sao nó xấu kinh dị vậy trời 😭" |
| `dong_cam` | Đồng cảm | Thương xót, chia sẻ | "Tội nghiệp em quá, mong em mạnh mẽ" |
| `ung_ho` | Ủng hộ | Bảo vệ, bênh vực, khen ngợi | "Em xinh và tài năng, fan luôn ủng hộ" |
| `trung_lap` | Trung lập | Tóm tắt, hỏi han, không cảm xúc | "Sự việc xảy ra lúc nào vậy ạ?" |
| `is_trash` | Rác | Spam, tag tên, emoji-only, quảng cáo | "Mai @An xem nè", "🤣🤣🤣" |

### Education (5 nhãn)

| Code | Nhãn | Mô tả ngắn | Ví dụ |
|---|---|---|---|
| `tich_cuc` | Tích cực | Đồng tình, ủng hộ chính sách | "Quy định này hợp lý, ủng hộ Bộ" |
| `tieu_cuc` | Tiêu cực | Phản đối, chỉ trích, lo ngại | "Lại thay đổi nữa, học sinh khổ" |
| `trung_lap` | Trung lập | Cập nhật thông tin, không lập trường | "Năm nay áp dụng cho khối 12 thôi" |
| `y_kien_rieng` | Ý kiến riêng | Lập luận, đề xuất, ủng hộ có điều kiện | "Luật này hay nhưng nên sửa điều 5" |
| `is_trash` | Rác | Spam, tag tên, emoji-only | "Đúng rồi 👍👍" |

---

## Quy tắc verify (CRITICAL)

### Khi nào sửa nhãn LLM?

1. **Nhãn LLM rõ ràng sai**: text "Tội nghiệp em" mà gán `phan_no` → sửa thành `dong_cam`
2. **Lệch ngữ cảnh**: comment có thể đúng nhãn nếu đứng riêng, nhưng trong context của post là sai
3. **Misclassify rác**: text chỉ là "@A xem đi" mà gán nhãn cảm xúc → sửa thành `is_trash`

### Khi nào GIỮ nhãn LLM?

1. Nhãn hợp lý dù không hoàn hảo (cảm xúc hỗn hợp 50/50 → giữ LLM, không tranh luận)
2. Comment ngắn nhưng có signal rõ
3. Đoán được ý nhưng cần context — vẫn cứ giữ nếu LLM đoán hợp lý

### Khi nào gắn cờ `uncertain`?

1. Bản thân không chắc, hoặc 2-3 nhãn đều có thể đúng
2. Comment quá ngắn không đủ signal ("ờ", "vậy à")
3. Mỉa mai cao cấp khó phân biệt với khen thật

→ Mẫu `uncertain` sẽ được verify chéo bởi người thứ 2.

---

## Khó phân biệt (lưu ý)

### Showbiz: `ca_khia` vs `phan_no`
- **Cà khịa**: có hài hước, mỉa mai, dùng từ ẩn dụ, emoji 😏 🙃
- **Phẫn nộ**: trực tiếp tức giận, dùng từ mạnh, không hài hước

Ví dụ:
- "Đẹp thế này thì chỉ có team chỉnh sửa" → `ca_khia`
- "Đồ giả tạo, tởm" → `phan_no`

### Showbiz: `trung_lap` vs `dong_cam`
- **Trung lập**: chỉ tóm tắt sự kiện, không cảm xúc
- **Đồng cảm**: có signal thương xót dù nhỏ

Ví dụ:
- "Vụ này diễn ra ở đâu vậy?" → `trung_lap`
- "Khổ thân, sao lại rơi vào tình huống này" → `dong_cam`

### Education: `trung_lap` vs `y_kien_rieng`
- **Trung lập**: nêu thông tin khách quan, không có lập luận
- **Ý kiến riêng**: có "tôi nghĩ", "nên là...", đề xuất giải pháp

Ví dụ:
- "Năm 2026 áp dụng quy định mới" → `trung_lap`
- "Tôi nghĩ nên áp dụng từ từ, đừng vội" → `y_kien_rieng`

### Phân biệt `is_trash`
- Tag tên thuần ("@An xem đi") → `is_trash`
- Tag tên + nội dung có ý nghĩa ("@An xem nè, vụ này hay quá") → KHÔNG phải `is_trash`, gán nhãn cảm xúc thực
- Emoji-only → `is_trash`
- Emoji + 1-2 từ thường ("Đúng 👍") — coi như `trung_lap` hoặc `ung_ho` tùy emoji

---

## Format file Excel verify

| comment_id | text | parent_text | llm_label | verified_label | confidence | note |
|---|---|---|---|---|---|---|
| cmt_show_001_0001 | Sao nó xấu thế | (post gốc) | ca_khia | ca_khia | high | |
| cmt_show_001_0002 | @An xem đi | | trung_lap | is_trash | high | LLM sai, đây là tag tên thuần |
| cmt_show_001_0003 | Cũng được | | trung_lap | trung_lap | low | uncertain — quá ngắn |

**Cột confidence**: high / medium / low (low = uncertain, cần verify chéo)

---

## Stratified sampling

### Showbiz target distribution

| Nhãn | Số mẫu | % |
|---|---|---|
| phan_no | 333 | 16.7% |
| ca_khia | 333 | 16.7% |
| dong_cam | 333 | 16.7% |
| ung_ho | 333 | 16.7% |
| trung_lap | 333 | 16.7% |
| is_trash | 335 | 16.6% |
| **Tổng** | **2000** | 100% |

### Education target distribution

| Nhãn | Số mẫu | % |
|---|---|---|
| tich_cuc | 400 | 20% |
| tieu_cuc | 400 | 20% |
| trung_lap | 400 | 20% |
| y_kien_rieng | 400 | 20% |
| is_trash | 400 | 20% |
| **Tổng** | **2000** | 100% |

**Lưu ý**: phân phối thực tế của LLM bị lệch (Showbiz nhiều `phan_no`/`ca_khia` hơn, Education nhiều `tieu_cuc`). Stratified sample sẽ over-sample các lớp ít để cân bằng.

---

## Tooling cần xây

### Script 1: `sample_for_labeling.py`
- Input: thư mục `process_*/full_analyzed/*.json`
- Output: `pool_llm_labeled.json`
- Logic:
  - Đọc tất cả comment có nhãn LLM
  - Stratified sample theo target distribution
  - Random sample 500 mẫu/batch
  - Export Excel với template ở trên

### Script 2: `merge_verified_batches.py`
- Input: tất cả Excel `batch_*_verified.xlsx`
- Output: `verified_final.json`
- Logic:
  - Đọc cột `verified_label`
  - Skip mẫu uncertain chưa verify chéo
  - Validate phân phối nhãn còn balanced
  - Export JSON

### Script 3: `split_train_val_test.py`
- Input: `verified_final.json`
- Output: `splits/{train,val,test}.json`
- Logic:
  - Stratified split 70/15/15
  - Test set: ưu tiên dùng lại 300 mẫu human-label cũ (Bảng 4.1)
  - Set seed = 42 cho reproducibility

---

## Phân chia công việc nhóm

Giả sử nhóm 3-4 người, mỗi người làm 500 mẫu/ngày:

| Ngày | Người 1 | Người 2 | Người 3 |
|---|---|---|---|
| 1 | Showbiz batch 1 (500) | Showbiz batch 2 (500) | Education batch 1 (500) |
| 2 | Showbiz batch 3 (500) | Showbiz batch 4 (500) | Education batch 2 (500) |
| 3 | Education batch 3 (500) | Education batch 4 (500) | Verify chéo uncertain |
| 4 | Buffer + finalize | | |

Tổng: 4 ngày làm việc.

---

## Quality control

### Inter-Annotator Agreement (IAA)

(Optional — đẹp về academic nhưng tốn thời gian)

- Mỗi người verify chéo 100 mẫu của người khác
- Tính Cohen's Kappa giữa từng cặp annotator
- Mục tiêu: Kappa ≥ 0.7 (substantial agreement)
- Nếu Kappa < 0.6 ở 1 lớp nào → review guideline cho lớp đó

### Spot check ngẫu nhiên

- Người leader random check 50 mẫu/batch của mỗi người
- Tỷ lệ sai > 10% → batch đó verify lại

---

## Thời gian ước tính

- Verify 1 mẫu: ~10-20 giây (LLM đã gán sẵn, người chỉ kiểm tra)
- 500 mẫu/người/ngày = ~2-3 giờ làm tập trung
- 4000 mẫu × 15 giây = ~17 giờ làm 1 người, hoặc ~5-6 giờ với 3 người

→ **Có thể xong trong 4-5 ngày** với nhóm 3 người.

---

## Câu hỏi chưa giải quyết

1. Số lượng nhóm verify cuối cùng là bao nhiêu người?
2. Có dùng Label Studio (open-source UI) thay Excel không? (Đẹp hơn nhưng setup tốn thời gian)
3. Inter-Annotator Agreement có làm không?
