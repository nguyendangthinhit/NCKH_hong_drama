# DỰ ÁN: NCKH Hồng Drama — Social Media Intelligence System

**Vai trò:** AI/ML Engineer | Data Engineer | Data Scientist (Tùy chọn)
**Mô tả:** Hệ thống end-to-end thu thập, tiền xử lý phân tán, phân tích ngữ nghĩa (NLP) và phục vụ dữ liệu dư luận trên mạng xã hội để phục vụ nghiên cứu khoa học cấp trường.

---

## 🛠 TECH STACK / CÔNG NGHỆ SỬ DỤNG
- **Ngôn ngữ:** Python, JavaScript / TypeScript, Java (cho JVM/Hadoop).
- **Big Data & Data Processing:** Apache PySpark, Hadoop, Pandas, PyArrow, Parquet.
- **Machine Learning & NLP:** PyTorch, Graph Neural Network (GraphSAGE), PhoBERT, LLMs (Gemini, Llama-3.3), Underthesea, TF-IDF. agentic rag    
- **Web & Automation:** React.js, Vite, Node.js, n8n.

---

## 🚀 ĐỊNH HƯỚNG 1: Dành cho vị trí AI / ML Engineer (Tập trung vào Mô hình & NLP)

**Trách nhiệm & Thành tựu:**
- Thiết kế hệ thống NLP pipeline xử lý văn bản tiếng Việt từ mạng xã hội, ứng dụng LLM (Gemini 2.5 Flash, Llama-3.3) để gán nhãn cảm xúc (emotion) và quan điểm (stance) tự động với độ chính xác >81%.
- Xây dựng quy trình lấy mẫu phân tầng (Stratified Sampling) và quy trình chuẩn hóa dữ liệu để chuẩn bị bộ dữ liệu *gold-label* (10k+ mẫu) phục vụ fine-tune mô hình **PhoBERT-base-v2**.
- Nghiên cứu và hiện thực hóa Mạng nơ-ron đồ thị **(Graph Neural Network - GraphSAGE)** kết hợp đặc trưng từ TF-IDF và trích xuất embedding từ PhoBERT để phân tích ngữ cảnh của các luồng thảo luận (discussion threads).
- Triển khai thuật toán trích xuất từ khóa xu hướng dựa trên **PMI (Pointwise Mutual Information)** và N-gram, tối ưu hóa tiền xử lý (loại bỏ nhiễu, định dạng tag) giúp tìm ra các insights chính xác từ dữ liệu thô.
- Tối ưu chi phí bằng cách kết hợp bộ lọc rác dựa trên luật (Rule-based) thay thế một phần cho LLM, giúp tăng tốc độ phân tích lên 1.000 lần mà không giảm độ chính xác.

---

## 🚀 ĐỊNH HƯỚNG 2: Dành cho vị trí Data Engineer (Tập trung vào Big Data & Pipeline)

**Trách nhiệm & Thành tựu:**
- Thiết kế và phát triển toàn bộ kiến trúc Data Pipeline (Ingestion → Preprocessing → Analysis → ML → Serving) xử lý tự động hàng chục ngàn bình luận.
- Phát triển hệ thống xử lý song song và phân tán bằng **Apache PySpark**, bao gồm module làm phẳng cấu trúc cây JSON, lọc rác bằng UDF (User Defined Functions), tokenize tiếng Việt và tính toán PMI quy mô lớn.
- Thực hiện kiểm thử và benchmark hiệu năng chi tiết giữa Python đơn luồng và kiến trúc Spark (Local mode): Tối ưu hóa Spark Pipeline đạt độ khớp dữ liệu tuyệt đối (100% Jaccard index), đạt điểm hòa vốn hiệu năng tại mốc 90.000 bản ghi.
- Đề xuất kiến trúc có khả năng mở rộng (horizontal scalability) dự kiến xử lý 1 triệu bản ghi chỉ trong ~1.5 phút trên cụm Cluster 10-node trong tương lai.
- Ứng dụng định dạng lưu trữ **Parquet** để tối ưu hóa I/O và giảm chi phí tính toán cho Spark trên nền tảng Hadoop cục bộ (Hadoop binaries for Windows/Local FS).
- Thiết lập hệ thống cào dữ liệu tự động tích hợp **n8n workflow**.

---

## 🚀 ĐỊNH HƯỚNG 3: Dành cho vị trí Data Scientist / Data Analyst (Tập trung vào Phân tích & Insight)

**Trách nhiệm & Thành tựu:**
- Chịu trách nhiệm toàn bộ vòng đời dữ liệu (Data Lifecycle) từ thu thập thô đến việc trích xuất insight trên hai lĩnh vực Giáo dục và Showbiz.
- Ứng dụng các thuật toán khai phá văn bản (Text Mining) như N-gram và **Pointwise Mutual Information (PMI)** để phát hiện tự động các chủ đề và từ khóa nổi bật định hình dư luận.
- Đánh giá chất lượng của dữ liệu và nhãn gán bởi các mô hình LLM tiên tiến, đối chiếu và chuẩn hóa các metric đo lường độ chính xác (Accuracy, F1-macro) giữa baseline và thực tế.
- Thiết kế **Web Dashboard** (React, Vite) kết nối với dữ liệu phân tích nhằm trực quan hóa các xu hướng, tần suất từ khóa, biểu đồ cảm xúc hỗ trợ ra quyết định và báo cáo nghiên cứu khoa học.
- Đề xuất và xây dựng pipeline lấy mẫu (sampling pipeline) giải quyết vấn đề mất cân bằng dữ liệu (data imbalance) trong phân tích cảm xúc mạng xã hội.