# Phân tích file Analyze keywords.py

## 1. Mục đích và Chức năng chính
File `Analyze keywords.py` là một công cụ phân tích tần suất từ khóa (Keyword Frequency Analyzer v4) thuộc hệ thống Drama Intelligence System.
Mục tiêu của nó là đọc các file JSON chứa comment (như `education_comments.json` và `showbiz_comments.json`), tiến hành tách từ (tokenize), tính toán sự liên kết giữa các từ (PMI - Pointwise Mutual Information), và xếp hạng các từ/cụm từ nổi bật nhất theo một công thức chấm điểm kết hợp giữa tần suất và PMI. Kết quả cuối cùng sẽ lọc ra các sự kiện, chủ đề hoặc từ khóa đáng chú ý nhất.

## 2. Cách thức hoạt động

Quá trình phân tích trải qua các bước chính sau:

### Bước 1: Tiền xử lý (Preprocessing) & Lọc Stopwords
- **Stopwords:** File định nghĩa một tập hợp từ dừng (stopwords) rất đa dạng. Bản v4 bổ sung thêm nhiều từ như: "sao", "nữa", "nên", "đừng", "vui", "buồn"... để loại bỏ các từ không mang nhiều ý nghĩa đặc trưng.
- **Làm sạch (Cleaning):** Loại bỏ các từ có độ dài < 3, các đường dẫn URL (http, www), các ký tự đặc biệt hoặc số `is_valid_token()`.
- **Tokenize:** Sử dụng thư viện `underthesea` (word_tokenize) để cắt câu tiếng Việt thành các từ (token). Các từ ghép có gạch dưới "_" sẽ được thay thế bằng khoảng trắng `base_tokenize()`.

### Bước 2: Trích xuất N-grams (Sliding Window)
- Đoạn mã sử dụng hàm `sliding_window` để tạo ra các cụm từ (N-grams) gồm 1 từ (unigram), 2 từ (bigram) và 3 từ (trigram) liên tiếp nhau trong một câu comment.

### Bước 3: Tính toán PMI (Pointwise Mutual Information)
- **PMI là gì?** Nó đo lường khả năng hai từ xuất hiện cùng nhau có lớn hơn xác suất chúng xuất hiện ngẫu nhiên hay không. Ví dụ: "trốn" và "thuế" xuất hiện cạnh nhau nhiều sẽ có PMI cao.
- Thuật toán đếm tổng số lần xuất hiện của các unigram, bigram và trigram `compute_pmi_scores()`.
- Chỉ các bigram và trigram có tần suất xuất hiện lớn hơn hoặc bằng `min_count` (mặc định là 3 hoặc 5) và có chỉ số PMI lớn hơn `min_pmi` (mặc định là 1.0) mới được giữ lại để đánh giá.

### Bước 4: Đếm tần suất (Frequency Counting)
- Ở lần quét thứ 2 `analyze_file()`, thuật toán sẽ đếm số lần xuất hiện của các token (unigram) cũng như các bigram/trigram đã lọt qua vòng tuyển PMI.
- Những token nào đã là một phần của bigram/trigram thì sẽ không được đếm với tư cách là từ đơn (unigram) nữa, để tránh bị trùng lặp.
- Đồng thời nó cũng đếm xem cụm từ đó xuất hiện trong bao nhiêu "bài viết" (dựa vào `id_content`).

## 3. Cơ chế chấm điểm và xếp hạng (Scoring & Ranking)

Công thức xếp hạng ở phiên bản v4 là:
**`Score = Frequency × log2(1 + max(PMI, 0))`**

Trong đó:
- **Frequency (freq):** Tổng số lần xuất hiện của từ/cụm từ đó.
- **PMI:** Điểm liên kết giữa các từ. Nếu là từ đơn (unigram), PMI được tính bằng 0.

**Tại sao lại dùng công thức này?**
- Đối với từ đơn (unigram): PMI = 0 $\rightarrow$ log2(1) = 0 $\rightarrow$ Score = 0. Việc này sẽ đẩy các từ đơn xuống thấp, ưu tiên các cụm từ có ý nghĩa hơn.
- Nếu chỉ dùng tần suất (freq), những từ phổ biến vô nghĩa nhưng chưa lọt vào danh sách stopwords sẽ lên top (ví dụ: "chỉ", "cũng").
- Bằng cách nhân tần suất với giá trị logarit của PMI, hệ thống sẽ ưu tiên các cụm từ vừa có tần suất cao vừa mang tính đặc trưng, liên kết chặt chẽ (ví dụ: "gian lận", "tống tiền", "trốn thuế"). Những từ này dù có tần suất không quá cao nhưng nhờ PMI lớn nên vẫn có thể vượt qua các từ phổ biến thông thường.

## 4. Cách lấy ra Top các sự kiện/từ khóa
- Hàm `top_keywords()` tính toán điểm (Score) cho tất cả các từ/cụm từ dựa theo công thức trên.
- Sau đó, nó sắp xếp danh sách giảm dần theo `Score` và lấy ra `top_n` (mặc định là 10) từ/cụm từ đứng đầu.
- Hàm `format_output()` sẽ lấy kết quả này, in ra báo cáo rõ ràng gồm: Tên từ khóa, loại n-gram, tổng số lần xuất hiện, số bài viết xuất hiện, điểm PMI, điểm tổng (Score) và chi tiết số lượng ở từng ID bài viết.

## 5. Kết luận
Thuật toán hoạt động rất hiệu quả trong việc khai phá văn bản tiếng Việt. Thay vì chỉ đếm từ như thông thường, nó áp dụng chỉ số PMI kết hợp tần suất để làm nổi bật các cụm từ mang tính "sự kiện", "drama" (đặc trưng cao). Điều này giúp tự động tóm tắt được các chủ đề nổi cộm nhất đang được thảo luận trong tập dữ liệu JSON mà không bị nhiễu bởi các từ ngữ thông dụng.