# Kế hoạch & Prompt NotebookLM

---

## DỰ ÁN NOTEBOOKLM 1: BÀI BÁO VỀ AI & NLP

> **Phạm vi:** Dự án này chỉ tập trung vào xử lý ngôn ngữ, Agent, Prompt và kết quả đánh giá mô hình.

### 1. Plan - Nội dung chi tiết cần đưa vào bài (Từ trên xuống dưới)

1. **Đặt vấn đề:**
   - Đi thẳng vào 2 nhược điểm lớn nhất của các mô hình LLM tĩnh:
     - *"Điểm dừng dữ liệu" (Knowledge cutoff)* khiến chúng mù tịt về các sự kiện mới.
     - *"Hiện tượng ảo giác" (Hallucination)* khiến chúng tự bịa đặt câu trả lời.
   - Nêu lý do cần hệ thống RAG đa tác nhân (Multi-Agentic RAG).

2. **Khung lý thuyết:**
   - Giới thiệu ngắn gọn khái niệm RAG.
   - Xoáy sâu vào sự tiến hóa lên **Agentic RAG** và **Multi-Agentic RAG** (khả năng đệ quy, dùng tool, tự đánh giá).

3. **Kiến trúc Multi-Agent đề xuất:**
   - Trình bày sơ đồ luồng 3 lớp:
     - **Tác nhân Điều phối (Dispatcher Agent):** Dùng LLM nhỏ (Gemini Flash) để phân tích ý định (intent), quyết định luồng đi giúp tối ưu token.
     - **Tác nhân Truy xuất (Retrieval Agent):** Tìm kiếm dữ liệu từ Supabase Vector Store.
     - **Tác nhân Phân tích Insight:** Tự đọc file JSON thống kê để trả lời số liệu.

4. **Cơ chế cốt lõi:**
   - **Cơ chế chống Ảo giác (Live Web Search Fallback):** Giải thích rõ luồng logic: Nếu Vector Store trả về *"Không tìm thấy"* $\rightarrow$ n8n kích hoạt Firecrawl đi cào dữ liệu Google thực tế $\rightarrow$ LLM đọc và trả lời.
   - **Phân loại cảm xúc 2 bước:** Giải thích luồng Sequential Batch (nhận diện cơ bản) và Async Parallel (phân tích sâu lập luận "trung lập" vs "ý kiến riêng").

5. **Đánh giá thực nghiệm:**
   - Đưa 2 bảng số liệu vào:
     1. Bảng Hit Rate (97%), Faithfulness (9.34), Answer Relevance (9.20).
     2. Bảng Accuracy phân loại cảm xúc cho Showbiz (80.1%) và Giáo dục (75.3%).

---

### 2. Prompt dùng để ra lệnh cho NotebookLM (Project 1)

*Sao chép toàn bộ đoạn dưới đây và dán vào khung chat của NotebookLM 1:*

```text
Bạn là một chuyên gia nghiên cứu khoa học máy tính chuyên ngành Trí tuệ Nhân tạo. Nhiệm vụ của bạn là đọc các tài liệu nguồn tôi cung cấp và viết một bài báo khoa học chuyên sâu hoàn chỉnh với đề tài: 'Ứng dụng Multi-Agentic RAG và cơ chế Web Fallback trong xây dựng Chatbot phân tích sự kiện mạng xã hội'.

Hãy bám sát đúng cấu trúc 5 phần sau và chỉ sử dụng thông tin trong tài liệu:
1. Đặt vấn đề: Phân tích 'điểm dừng dữ liệu' và 'hiện tượng ảo giác' của LLM.
2. Khung lý thuyết: Giải thích RAG và sự tiến hóa lên kiến trúc Multi-Agentic RAG.
3. Kiến trúc Multi-Agent đề xuất: Phân tích vai trò của Router (Dispatcher) Agent, Retrieval Agent và Insight Analyst Agent. Nhấn mạnh việc tối ưu hóa Token nhờ cơ chế định tuyến của N8n.
4. Cơ chế cốt lõi: Trình bày chi tiết giải pháp chống ảo giác bằng Live Web Search (Firecrawl) và Chiến lược phân loại thái độ dư luận 2 bước (Sequential Batch & Async Parallel).
5. Đánh giá thực nghiệm: Báo cáo kết quả đánh giá chất lượng RAG (Hit Rate, Faithfulness, Answer Relevance) và độ chính xác (Accuracy, F1-score) khi dán nhãn cảm xúc ở 2 lĩnh vực Giáo dục và Showbiz.

Yêu cầu bắt buộc:
- Sử dụng văn phong học thuật, khách quan, súc tích.
- Tuyệt đối KHÔNG đưa các nội dung liên quan đến: tối ưu hóa PySpark, làm website, UI/UX, phân tích từ khóa PMI hay cấu trúc đồ thị dữ liệu vào bài báo này.
- Hãy viết nội dung liền mạch, đánh số mục rõ ràng, đi thẳng vào vấn đề.
```

---
---

## DỰ ÁN NOTEBOOKLM 2: BÀI BÁO VỀ DATA ENGINEERING

> **Phạm vi:** Dự án này chỉ tập trung vào cách tổ chức dữ liệu, tối ưu hóa hệ thống phân tán, Spark và PMI.

### 1. Plan - Nội dung chi tiết cần đưa vào bài (Từ trên xuống dưới)

1. **Đặt vấn đề:**
   - Phân tích khó khăn khi thu thập dữ liệu Facebook (luật Anti-Scraping, cấu trúc phi tuyến tính).
   - Giới hạn "nghẽn cổ chai" của Python khi chạy đơn luồng trên dữ liệu lớn.

2. **Quy trình thu thập và Lưu trữ:**
   - Giới thiệu luồng n8n kết hợp Apify (Proxy Rotation).
   - Nhấn mạnh vào **Lược đồ Đồ thị Thảo luận (Discussion Graph Schema)** sử dụng trường khóa ngoại `reply_to_id` để nối bình luận cha-con.

3. **Kiến trúc Tiền xử lý phân tán:**
   - Giới thiệu pipeline PySpark chạy song song 8 luồng.
   - **Điểm nhấn:** Giải thích cách đóng gói bộ lọc rác (Rule-based Filter) thành **Spark UDF (User-Defined Function)** đảm bảo tính picklable để chạy phân tán.

4. **Trích xuất đặc trưng (PMI):**
   - Giải thích thuật toán trích xuất N-grams kết hợp tính điểm PMI (Pointwise Mutual Information).
   - Phân tích công thức Scoring và tác dụng của cấu hình `--strip-names`.

5. **Đánh giá thực nghiệm:**
   - **Độ chính xác:** Chứng minh PySpark và Python cho ra kết quả khớp 100% (29.660 bình luận sạch, Jaccard 1.0).
   - **Hiệu năng (Scalability):** Đưa bảng Benchmark thời gian, chỉ ra "điểm hòa vốn" (break-even) ở mốc 90.000 bình luận và phép ngoại suy dự phóng cho 1.000.000 bình luận chạy trên Cluster.

---

### 2. Prompt dùng để ra lệnh cho NotebookLM (Project 2)

*Sao chép toàn bộ đoạn dưới đây và dán vào khung chat của NotebookLM 2:*

```text
Bạn là một chuyên gia Kỹ sư Dữ liệu (Data Engineer) và Khoa học Dữ liệu. Nhiệm vụ của bạn là đọc các tài liệu nguồn tôi cung cấp và viết một bài báo khoa học chuyên sâu với đề tài: 'Tối ưu hóa đường ống thu thập và trích xuất đặc trưng dư luận mạng xã hội phi tuyến tính sử dụng Apache PySpark'.

Hãy bám sát đúng cấu trúc 5 phần sau và chỉ sử dụng thông tin trong tài liệu:
1. Đặt vấn đề: Những rào cản khi cào dữ liệu Facebook (Anti-scraping) và giới hạn hiệu năng của xử lý dữ liệu Python đơn luồng.
2. Quy trình thu thập và Lược đồ dữ liệu: Phân tích luồng Apify/Key rotation và Lược đồ Đồ thị Thảo luận (Discussion Graph) qua khóa ngoại reply_to_id.
3. Kiến trúc Tiền xử lý phân tán: Trình bày kiến trúc PySpark. Tập trung phân tích sâu việc đóng gói bộ lọc rác cơ học (Rule-based Filter) thành Spark UDF cho kiến trúc phân tán.
4. Thuật toán trích xuất từ khóa: Phân tích phương pháp dùng N-grams kết hợp chỉ số PMI, giải thích công thức xếp hạng (Scoring) và vai trò của cấu hình --strip-names.
5. Đánh giá thực nghiệm: Báo cáo số liệu đối chiếu tính đúng đắn (khớp 100% giữa Spark và Python). Phân tích bảng Benchmark hiệu năng thời gian, điểm hòa vốn (break-even) ở 90.000 mẫu và phép ngoại suy (extrapolation) lên 1 triệu bình luận.

Yêu cầu bắt buộc:
- Sử dụng văn phong học thuật, tập trung vào tính mở rộng (scalability) và hiệu năng tính toán.
- Tuyệt đối KHÔNG đưa các nội dung liên quan đến: Chatbot RAG, LLM Prompting, cơ chế chống ảo giác Firecrawl hay giao diện Web/Dashboard vào bài báo này.
- Hãy viết nội dung liền mạch, đánh số mục rõ ràng, phân tích sâu các con số thực nghiệm.
```
