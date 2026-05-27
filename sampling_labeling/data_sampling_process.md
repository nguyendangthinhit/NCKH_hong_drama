# Quy trình lấy dữ liệu mẫu (Data Sampling Process)

Quy trình này mô tả cách tổng hợp và lấy mẫu dữ liệu bình luận từ các tập dữ liệu lớn hơn (`full folders`) để tạo ra các tập dữ liệu mẫu nhỏ hơn, được phân tầng theo cảm xúc (emotion/stance).

Quy trình bao gồm hai bước chính:

1.  **Tổng hợp bình luận (Comment Aggregation)**: Sử dụng `aggregate_comments_v2.py` để gộp các bình luận từ nhiều file JSON và lọc bỏ các bình luận rác.
2.  **Lấy mẫu phân tầng (Stratified Sampling)**: Sử dụng `sample_comments.py` để chọn ra một số lượng bình luận nhất định cho mỗi loại cảm xúc, đảm bảo sự phân bố đồng đều cho mục đích phân tích hoặc huấn luyện mô hình.

---

## 1. Tổng hợp bình luận (`aggregate_comments_v2.py`)

File `aggregate_comments_v2.py` chịu trách nhiệm thu thập tất cả các bình luận từ các thư mục chứa dữ liệu đã phân tích (`analyzed_data/full`) và tổng hợp chúng vào các file JSON lớn hơn.

### **Mục đích:**

*   Gộp tất cả các bình luận từ các file JSON nhỏ lẻ thành một tập hợp duy nhất cho từng lĩnh vực (Showbiz, Education).
*   **Lọc bỏ các bình luận được đánh dấu là rác (`is_trash = True`)**.

### **Đầu vào (Input):**

*   Các thư mục chứa dữ liệu phân tích đầy đủ:
    *   `D:\py\git\NCKH_hong_drama\data\process_education\analyzed_dataa\full`
    *   `D:\py\git\NCKH_hong_drama\data\process_showbiz\analyzed_data\full`

### **Đầu ra (Output):**

*   Các file JSON chứa tất cả bình luận đã được lọc bỏ rác:
    *   `D:\py\git\NCKH_hong_drama\data\showbiz_comments.json` (cho lĩnh vực Showbiz)
    *   `D:\py\git\NCKH_hong_drama\data\education_comments.json` (cho lĩnh vực Education)

### **Cách thức hoạt động:**

1.  Script duyệt qua tất cả các file `.json` trong thư mục đầu vào đã chỉ định (ví dụ: `process_showbiz/analyzed_data/full`).
2.  Với mỗi file JSON, nó đọc dữ liệu và trích xuất các bình luận.
3.  Đối với bình luận Showbiz, nó lấy `comment_id`, `text`, `emotion`.
4.  Đối với bình luận Education, nó lấy `comment_id`, `text`, `stance`.
5.  **Chỉ những bình luận có `comment_id` và `text` không rỗng và `is_trash` là `False` mới được thêm vào danh sách tổng hợp.**
6.  Sau khi xử lý tất cả các file, danh sách bình luận tổng hợp sẽ được lưu vào file JSON đầu ra tương ứng.

### **Cách sử dụng:**

Chạy script từ thư mục `D:\py\git\NCKH_hong_drama`:

```bash
python aggregate_comments_v2.py
```

---

## 2. Lấy mẫu phân tầng (`sample_comments.py`)

File `sample_comments.py` thực hiện việc lấy mẫu dữ liệu từ các tập dữ liệu tổng hợp đã tạo ra ở bước 1, sử dụng phương pháp lấy mẫu phân tầng (stratified sampling) dựa trên các loại cảm xúc.

### **Mục đích:**

*   Tạo ra một tập dữ liệu mẫu nhỏ hơn nhưng vẫn giữ được tỷ lệ phân bố của các loại cảm xúc nhất định.
*   Hữu ích cho việc tạo tập dữ liệu kiểm thử hoặc tập dữ liệu nhỏ để nhanh chóng kiểm tra mô hình.

### **Đầu vào (Input):**

*   File JSON chứa các bình luận tổng hợp:
    *   Mặc định là `data/showbiz_comments_new.json` (hoặc `data/showbiz_comments.json` nếu không có bước trung gian `_new`).

### **Đầu ra (Output):**

*   File JSON chứa các bình luận đã được lấy mẫu:
    *   Mặc định là `data/data_test_show.json` (hoặc `data/data_test_edu.json` nếu có xử lý Education).

### **Cấu hình lấy mẫu:**

Script sử dụng một cấu hình `EMOTION_SAMPLES` để xác định số lượng mẫu mục tiêu cho mỗi loại cảm xúc:

```python
EMOTION_SAMPLES = {
    'null': 20,       # Bình luận rác hoặc không xác định cảm xúc
    'Ủng hộ': 20,      # Support
    'Đồng cảm': 40,    # Empathy
    'Phẫn nộ': 80,     # Anger
    'Cà khịa': 80,     # Sarcasm
    'Trung lập': 80    # Neutral
}
```
*Lưu ý:* `null` ở đây có thể đại diện cho các bình luận bị loại bỏ (rác) hoặc những bình luận mà cảm xúc không được xác định rõ ràng, được xử lý trong bước `normalize_emotion`.

### **Cách thức hoạt động:**

1.  **Tải dữ liệu:** Đọc các bình luận từ file JSON đầu vào (ví dụ: `showbiz_comments_new.json`).
2.  **Chuẩn hóa cảm xúc:** Hàm `normalize_emotion` được sử dụng để chuẩn hóa các giá trị cảm xúc (ví dụ: "Ứng hộ" thành "Ủng hộ") và gán 'null' cho các cảm xúc không xác định hoặc rỗng.
3.  **Nhóm theo cảm xúc:** Các bình luận được nhóm lại dựa trên giá trị cảm xúc đã chuẩn hóa của chúng.
4.  **Lấy mẫu phân tầng:**
    *   Đối với mỗi loại cảm xúc được định nghĩa trong `EMOTION_SAMPLES`, script sẽ cố gắng lấy một số lượng bình luận nhất định.
    *   Nếu số lượng bình luận có sẵn cho một cảm xúc ít hơn số lượng mục tiêu, script sẽ lấy tất cả các bình luận có sẵn cho cảm xúc đó.
    *   `random.sample` được sử dụng để chọn ngẫu nhiên các bình luận từ mỗi nhóm cảm xúc.
5.  **Lưu kết quả:** Các bình luận đã được lấy mẫu sẽ được ghi vào file JSON đầu ra.

### **Cách sử dụng:**

Chạy script từ thư mục `D:\py\git\NCKH_hong_drama`. Có thể chỉ định file nguồn, file đầu ra và seed cho random nếu muốn:

```bash
python sample_comments.py --show-src data/showbiz_comments.json --out-show data/data_test_show_final.json --seed 42
```
(Nếu không chỉ định, script sẽ sử dụng các giá trị mặc định đã khai báo.)