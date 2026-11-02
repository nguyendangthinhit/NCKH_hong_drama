# Drama Intelligence System — Đánh giá & lộ trình

> Trích riêng từ tài liệu "Đánh giá & lộ trình 4 dự án AI (ĐACN · NCKH · ĐATN)".

## Vấn đề cần giải quyết khi cầm lại dự án

- **Drama (đã làm NCKH):** chuyển từ "phân tích kho dữ liệu cố định" sang "phân tích theo yêu cầu" – web dán bất kỳ bài post, agent tự đăng nhập (clone account), tự cào, tự phân tích, trả insight. Đây là chuyển bài toán từ batch (offline) sang **on-demand**. Chi tiết ở mục Dự án 4.

---

## Dự án 4 – Drama Intelligence System (báo cáo NCKH, 05/2026)

**Mức hoàn thiện: khoảng 85%.** Báo cáo 116 trang có hệ thống chạy được (thu thập, tiền xử lý, phân tích, chatbot RAG, website, dashboard) và có đánh giá. Còn thiếu: dữ liệu Showbiz chưa cập nhật (prompt của Dispatcher nêu rõ), nhãn do LLM gán còn nhiễu, GNN chưa đạt, và đang phụ thuộc gói miễn phí.

### Ý tưởng

Phiên bản hiện tại phân tích kho dữ liệu đã thu sẵn (batch, offline). **Cải tiến bạn muốn làm là chuyển sang on-demand analysis**: web cho người dùng dán link một bài post bất kỳ → agent tự đăng nhập bằng tài khoản clone (lưu ở back-end) → tự cào post + cả cây bình luận → chạy pipeline phân tích đã có → trả insight và trend. Đây là bước nhảy thật sự so với bản NCKH vì:

- Chuyển từ "dữ liệu của nhóm nghiên cứu" sang "dữ liệu của người dùng" → biến sản phẩm thành một tổng đài social listening mở.
- Thêm bài toán kỹ thuật mới: quản lý tài khoản clone, cào on-demand với độ trễ chấp nhận được, cache, chống rate-limit, lọc post riêng tư.
- Mở gap so với Kompa/YouNet: họ bán dashboard chạy trên kho dữ liệu của họ, không cho user dán link bất kỳ.

**Rủi ro:** vi phạm điều khoản Facebook rất cao (tài khoản clone, scraping). Nếu làm ĐACN/ĐATN thì cần ghi rõ là prototype nghiên cứu, không triển khai thương mại; phần báo cáo nên có mục đạo đức/pháp lý.

### Kiến trúc và điểm mạnh

| Lớp | Dùng gì | Điểm mạnh |
|---|---|---|
| Thu thập | n8n, Apify (xoay vòng tài khoản), Firecrawl | Vượt được chặn tải trang của Facebook trong phần lớn thử nghiệm mà không tốn hạ tầng |
| Dữ liệu | 3 tầng (thô JSON, đã xử lý, tương tác); đồ thị thảo luận qua trường reply_to_id | Tái lập được; giữ cấu trúc cha-con của bình luận |
| Tiền xử lý/phân tích | Python và PySpark song song, PMI + n-gram cho từ khóa, LLM gán nhãn 2 bước, asyncio + Semaphore | Hai pipeline cho cùng kết quả (Jaccard 1,0000 trên tập bình luận sạch) |
| Truy xuất | Supabase vector + embedding Google + Cohere rerank | Hit rate 29/30 = 97% trên 30 lượt hội thoại |
| Agent | Dispatcher (router JSON) → Retrieval / Insight Analyst → LLM chain tĩnh | Chọn model theo mức tiêu hao token: Gemini cho Dispatcher, Groq cho câu trả lời cuối |
| Chống ảo giác | Luật prompt → Firecrawl live search khi không tìm thấy → ghi câu hỏi thiếu dữ liệu vào Google Sheets để bổ sung sau | Vòng phản hồi dữ liệu tự phát hiện khoảng trống |

Báo cáo cũng trung thực về kết quả âm: Spark chậm hơn Python ở quy mô hiện tại và GNN bị sụp về lớp đa số.

### Số liệu chính trong báo cáo

- **Dữ liệu:** 85 sự kiện (40 Giáo dục, 45 Showbiz), 32.076 bình luận thô, 29.622 bình luận sạch, 2.454 bình luận rác (7,7%).
- **Phân loại cảm xúc (so với nhãn người):** Showbiz 80,1% (253/316), Giáo dục 75,3% (226/300).
- **RAG (LLM-as-a-judge, 30 lượt):** hit rate 97%, faithfulness 9,34/10, answer relevance 9,20/10.
- **Hiệu năng:** trên 18.245 bình luận, Python 16,69 s so với Spark local 38,67–51,96 s (0,32–0,43x); trên 90.000 bình luận giả lập, Spark đạt 1,03x. Con số "1 triệu bình luận" là ngoại suy, chưa đo.
- **GNN (GraphSAGE):** F1-macro 0,524 (Giáo dục) và 0,217 (Showbiz, do 94,2% nhãn là trung lập nên mô hình dự đoán hầu hết vào lớp này).

### Gap so với sản phẩm social listening tại Việt Nam

Báo cáo cho rằng Buzzmetrics, YouNet, Kompa chủ yếu thống kê định lượng, thiếu AI sinh văn bản và thiếu hỏi đáp. Phần này cần viết lại cho chặt hơn:

- **Kompa.ai** tự quảng cáo Generative AI viết insight, diễn giải xu hướng và dự báo; bài không nêu tính năng chat với dữ liệu và không có số đánh giá độ chính xác.
- **YouNet Media** ra mắt AI-Enhanced Social Listening Dashboard (30/06/2025) với gán nhãn cảm xúc/thuộc tính tự động, biểu đồ so sánh thuộc tính và bubble matrix; bài không mô tả tóm tắt hay chat.

Vậy khẳng định "thiếu generative AI" khó giữ. Gap còn bảo vệ được: hỏi đáp có trích dẫn đến từng bình luận gốc trên dữ liệu tiếng Việt, tận dụng cấu trúc chuỗi trả lời, và bộ đánh giá công khai. Cần kiểm thêm bản dùng thử của các sản phẩm này trước khi kết luận.

### Áp dụng cho 3 mục đích

Dự án đã là NCKH. Nếu dùng tiếp cho học phần khác, phần nộp phải có đóng góp mới và ghi rõ phần đã nộp trước đó (nên hỏi giảng viên).

| Tiêu chí | ĐACN | NCKH (đã làm) | ĐATN |
|---|---|---|---|
| Dữ liệu | Phần mới: gán nhãn vàng 10.000 mẫu | 29.622 bình luận sạch | Mở rộng TikTok/YouTube theo hướng của báo cáo |
| Công nghệ | Fine-tune PhoBERT, so với LLM API | n8n, RAG, Supabase, PySpark, GraphSAGE | Pipeline streaming + tự huấn luyện lại |
| Gap | So sánh nhãn LLM với mô hình nội bộ | Hỏi đáp có trích dẫn trên dư luận tiếng Việt | Hệ thống đầy đủ + đánh giá so sánh với sản phẩm thương mại |
| Tối ưu | Chi phí/bình luận và độ trễ (báo cáo ước tính API ~0,51 VNĐ/bình luận, ~500 ms/yêu cầu) | Đã đo cơ bản | Độ tin cậy khi chạy liên tục, không phụ thuộc gói miễn phí |

### Hạn chế và khó khăn

1. **Nhãn nhiễu và mất cân bằng.** Nhãn do LLM gán; Showbiz có 94–95% trung lập, nên 3 trong 5 lớp có F1 = 0 khi huấn luyện GNN. Cần định nghĩa lại nhãn (ví dụ nhị phân toxic/non-toxic như báo cáo đề xuất) và có bộ nhãn người lớn hơn.
2. **Đánh giá yếu.** RAG chỉ được đánh giá trên 30 lượt lấy từ log của chính hệ thống, chấm bằng LLM-as-a-judge, không có baseline (không RAG, sản phẩm thương mại). Bảng chỉ số nêu Accuracy/F1/Precision/Recall nhưng phần kết quả chỉ báo Accuracy.
3. **Số liệu chưa nhất quán.** Bình luận sạch là 29.622 (Hình 4.7) nhưng 29.660 (Bảng 4.4); Showbiz trung lập 23.048 (95,0%) ở Hình 4.7 nhưng 19.215 (94,2%) ở Bảng 4.13. Nên thống nhất phiên bản dữ liệu. Trang 96 còn sót một "Ghi chú cho tác giả" chưa xóa.
4. **Spark chưa đáng dùng ở quy mô này.** Chính Bảng 4.10 khuyến nghị Spark từ khoảng 100.000 bản ghi trở lên; khi bảo vệ nên trình bày đây là bước chuẩn bị chứ không phải lợi ích đã chứng minh.
5. **Phụ thuộc gói miễn phí.** Một lần chạy phân tích mất khoảng 13–14 giờ do lỗi 429 và hết API key dự phòng (Hình 4.11); n8n bản free từng mất kết nối; Groq báo giới hạn token mỗi phút; live search trễ vài chục giây.
6. **Pháp lý và đạo đức.** Thu bình luận Facebook bằng Apify và nội dung nói về người thật; nên xem điều khoản nền tảng và quy định dữ liệu cá nhân trước khi công bố.

### Lộ trình nâng cấp (nếu mở rộng sang ĐACN/ĐATN hoặc viết bài báo)

1. **Tuần 1–2:** sửa lỗi nhất quán số liệu, gỡ ghi chú sót, chốt phiên bản dữ liệu.
2. **Tuần 3–6:** gán nhãn vàng 10.000 mẫu (hướng dẫn gán nhãn, đo độ đồng thuận giữa người gán, cân bằng lớp Showbiz). *Cổng:* đủ mẫu cho mỗi lớp để chia train/val/test.
3. **Tuần 7–10:** fine-tune PhoBERT và so với LLM API về F1-macro, chi phí/bình luận, độ trễ. *Cổng:* đạt mục tiêu F1-macro ≥ 0,85 mà chính báo cáo đặt ra, hoặc nêu rõ lý do chưa đạt.
4. **Tuần 11–13:** đánh giá lại RAG: bộ câu hỏi lớn hơn, baseline không RAG, so reranker, kiểm người trên một phần kết quả judge.
5. **Tuần 14 trở đi:** GNN trên nhãn mới; streaming chỉ khi dữ liệu vượt ngưỡng Spark.

### Kế hoạch triển khai 8 giai đoạn (theo thứ tự phụ thuộc)

Thứ tự: dữ liệu và nhãn, PhoBERT, đồ thị, thời gian thực, Drama Score, phân tích qua link, kiến trúc phân tán, tự động hóa hai luồng. Mỗi bước xử lý là hàm thuần (đọc Parquet, ghi Parquet, không giữ trạng thái ngầm) với schema thống nhất (`comment_id, event_id, post_id, platform, author_id, reply_to_id, ts, text, labels`), nên cùng một logic chạy được trên luồng đơn và luồng phân tán.

**GĐ1. Tăng dữ liệu, tăng nguồn, đánh label**

- **Tăng sự kiện (85 lên 200+):** đặt tiêu chí chọn trước, ví dụ tối thiểu 200 comment/sự kiện. Giữ riêng một nhóm sự kiện mới theo thời gian làm tập test để kiểm tra khả năng tổng quát hóa.
- **YouTube:** nguồn chính thức, khả thi. `commentThreads.list` tốn 1 unit/lần, hạn mức mặc định 10.000 unit/ngày. `search.list` có hạn mức riêng chỉ 100 lần/ngày, nên lấy video qua danh sách upload của kênh (`playlistItems`) chứ không tìm bằng search.
- **TikTok Research API:** cần nộp đơn và được duyệt theo đề tài. Hạn mức 1.000 request/ngày, mỗi request tối đa 100 record. Trang FAQ không nêu vùng đủ điều kiện nên chưa chắc Việt Nam được cấp. Nộp đơn sớm, dự phòng bằng scraper Apify (có rủi ro điều khoản dịch vụ, chỉ dùng cho nghiên cứu).
- Chuẩn hóa mọi nền tảng về một schema, có trường `platform`.
- **Đánh label (10.000 gold):** chọn mẫu có chủ đích vì neutral chiếm 94%; oversample các comment Gemini gán non-neutral, các comment Gemini và Groq bất đồng, và các comment chứa từ khóa độc hại.
- Gemini gán trước, người kiểm tra và sửa. Dùng Label Studio hoặc Argilla tự host.
- Viết guideline cho 2 người, có 10–15% mẫu chồng lấp để tính Cohen's κ. Mốc tham chiếu ViHOS: F1 0.86, κ 0.72.
- Tách train/test theo sự kiện, không tách theo comment.
- Dữ liệu ngoài để khởi động: ViHSD (khoảng 33.400 comment) và ViHOS (11.056 comment).
- Khối lượng khoảng 28 giờ công, chia cho 2–3 người.
- **Làm tối thiểu ngay từ đây:** một worker chạy job đơn giản dưới máy (bảng `jobs` trên Supabase/Postgres, worker polling). Bản đầy đủ làm ở GĐ8.

**GĐ2. Làm PhoBERT**

- Fine-tune `vinai/phobert-base-v2`, đầu vào cần tách từ trước (VnCoreNLP hoặc underthesea).
- Multi-task: đầu ra sentiment và đầu ra toxicity.
- Xử lý mất cân bằng bằng weighted loss hoặc focal loss. Theo dõi F1-macro, mục tiêu ≥ 0.85.
- Baseline so sánh: Gemini (80.1% Showbiz, 75.3% Education) và PhoBERT chưa fine-tune.
- Train trên Colab/Kaggle trong lúc GPU của nhóm chưa dùng được (lỗi driver), export ONNX để suy luận.
- Lợi ích: bỏ phụ thuộc Gemini/Groq, lần phân tích 13–14 giờ vì lỗi 429 giảm xuống còn vài phút, chi phí API về 0.
- **Phân loại chủ đề (BERTopic)** làm ngay sau PhoBERT vì dùng chung embedding: BERTopic (UMAP + HDBSCAN) để khám phá, LLM đặt tên cụm, rồi chốt taxonomy 8–12 nhãn và train classifier. Chia hai tầng: chủ đề cấp sự kiện và chủ đề cấp comment.

**GĐ3. Làm lại dữ liệu theo hướng đồ thị**

- **Schema Neo4j:** `(User)-[WROTE]->(Comment)-[IN]->(Post)-[ABOUT]->(Event)`, `(Comment)-[REPLY_TO]->(Comment)`, `(Comment)-[HAS_TOPIC]->(Topic)`, `(Comment)-[MENTIONS]->(Entity)`, cộng thêm `SAME_AUTHOR` và `NEXT_IN_TIME` theo hướng mở rộng ở mục 4.6.
- Neo4j chạy Docker local, làm lớp lưu trữ, truy vấn và trực quan hóa.
- **Phân tích:** PageRank (tài khoản then chốt), Louvain/Leiden (các phe), FastRP, chạy bằng GDS ở luồng đơn.
- **Học đồ thị:** export subgraph sang PyTorch Geometric để train GraphSAGE, feature là CLS của PhoBERT đã fine-tune. Showbiz chuyển sang bài toán nhị phân toxic/non-toxic. Đích F1-macro ≥ 0.80.
- Kết quả (embedding, community, centrality) ghi ngược vào Neo4j.
- **Giao diện chung cho phân tích đồ thị** (để luồng phân tán thay thế được ở GĐ7): đầu vào là bảng cạnh `(src, dst, type, ts)` dạng Parquet, đầu ra là bảng thuộc tính nút `(node_id, pagerank, community_id)`. Phần còn lại của hệ thống chỉ đọc bảng đầu ra.
- Cần kiểm tra: giới hạn GDS và Aura chưa được xác minh. Bản Neo4j Community theo hiểu biết hiện tại không phân tán.

**GĐ4. Xử lý theo hướng thời gian thực**

- **Khám phá sự kiện theo yêu cầu, không quét liên tục.** Khi user hỏi "có vấn đề nào mới không?", hệ thống mới quét RSS/trang giải trí (Kenh14, Znews, VnExpress...). Firecrawl lấy nội dung bài và trích xuất theo schema (tên sự kiện, nhân vật, thời điểm, nguồn). Kết quả lưu vào DB. Khử trùng lặp bằng độ tương đồng embedding. Mỗi sự kiện có vòng đời: mới nổi, đỉnh, hạ nhiệt. Giới hạn gói free của Firecrawl chưa kiểm tra.
- **Cửa sổ trượt (micro-batch):** khi có comment mới, job tính lại đặc trưng cho từng sự kiện: tốc độ tăng volume, tỉ lệ toxic, phân cực, sentiment entropy. Giai đoạn này chạy trên luồng đơn.
- Sự kiện mới có thể kích hoạt job thu thập comment và gửi cảnh báo Telegram.

**GĐ5. Drama Score**

- **Thành phần:** tốc độ tăng volume (z-score so với nền), tỉ lệ toxic, mức phân cực (modularity của các cộng đồng), mức lan rộng (số nền tảng, số tài khoản), entropy của sentiment, độ tập trung của tài khoản trung tâm, số bài báo đưa tin.
- **Trọng số:** không tự đặt. Cho 3 người xếp hạng cặp "sự kiện nào drama hơn" trên các sự kiện, rồi fit hồi quy ordinal/logistic. Kiểm định bằng Spearman và ablation.
- **Đầu ra:** điểm 0–100, xu hướng theo thời gian, bản tóm tắt tình hình (hai phe, ngòi nổ, tài khoản then chốt).

**GĐ6. Phân tích post qua link**

- Luồng: web dán link, webhook n8n, nhận diện nền tảng, thu thập comment (đồng bộ tối đa khoảng 300–500 comment, phần còn lại chạy bất đồng bộ), PhoBERT, từ khóa, đồ thị nhỏ, RAG tìm sự kiện tương tự trong dữ liệu cũ, tóm tắt, hiển thị tiến độ qua SSE.
- Cache theo hash của URL.
- Với Facebook, tài khoản clone yếu về pháp lý và ổn định. Bản demo ưu tiên link YouTube, Facebook chỉ giới hạn số lượng.

**GĐ7. Kiến trúc phân tán (PySpark + RAPIDS)**

- **Hiện trạng:** báo cáo đã có pipeline PySpark chạy `local[8]` trên 8 core CPU (8 module, khoảng 1.135 dòng, thư mục `data/spark/`), đối chiếu chéo với pipeline Python và cho kết quả trùng khớp (29.660 comment sạch). HDFS/S3 mới là hướng phát triển (mục 4.6.3): hiện đọc JSON qua driver Python do giới hạn Hadoop FS trên Windows. GĐ này nâng pipeline từ local lên cụm đa node.
- **Luận điểm thí nghiệm:** "dữ liệu nhỏ thì không cần Spark" thường được phát biểu mà không kèm số liệu cho workload này. Nhóm đo thực nghiệm: nếu dữ liệu chưa đủ lớn thì có số liệu chỉ ra ở quy mô nào Spark chưa đáng; nếu đủ lớn thì chứng minh kiến trúc phân tán hợp lý với dữ liệu quy mô lớn. Cả hai kết quả đều có ý nghĩa báo cáo.

| Tầng | Luồng đơn | Luồng phân tán |
|---|---|---|
| Lưu trữ | Parquet cục bộ / Supabase | Parquet/Delta trên object storage (S3-compatible hoặc HDFS), phân vùng theo `event_id`/ngày |
| Tiền xử lý, xử lý | pandas/Polars | PySpark (từ `local[8]` lên cụm) |
| Suy luận PhoBERT | ONNX trong worker | Batch trên GPU qua pandas UDF hoặc Spark-RAPIDS |
| Mô hình hóa, phân tích | pandas + scikit-learn | cuDF/cuML (RAPIDS); tích hợp Spark qua spark-rapids (chưa kiểm chứng) |
| Đồ thị | Neo4j GDS | Mặc định: Spark + GraphFrames (CPU). Tùy chọn: cuGraph (GPU) nếu có server GPU. Kết quả nạp vào Neo4j |
| Thời gian thực | micro-batch bằng job | Structured Streaming đọc thư mục Parquet mới; chưa dùng Kafka |

- **Kafka:** chưa dùng vì nguồn dữ liệu (Apify, YouTube, TikTok) là kéo theo lô, không phải luồng sự kiện. Chỉ cân nhắc khi có nguồn đẩy sự kiện thật hoặc nhiều consumer cùng đọc một luồng. Thêm vào sau cũng không phải sửa các bước xử lý.
- **Thí nghiệm scaling:** chạy lại cùng các bước trên cả hai luồng ở nhiều mức N (30k đến 1M+), từng stage riêng, đổi số core/partition, đo thời gian, throughput, RAM, chi phí, lặp nhiều lần để tìm điểm giao nhau. Nếu có GPU thì thêm so sánh GraphFrames (CPU) và cuGraph (GPU) theo kích thước đồ thị. Dữ liệu thật chưa đủ thì sinh thêm dữ liệu mô phỏng (ghép lại và biến đổi comment thật) và nói rõ trong báo cáo.
- GPU hiện chưa dùng được nên không chặn GĐ1–6. Từ GĐ7 chạy trên server GPU thuê.

**GĐ8. Tự động hóa hoàn toàn, hai luồng**

- **Nối n8n với script dưới máy:** n8n tự host bằng Docker, chỉ lo lịch, gọi API, Telegram. Việc nặng đi qua hàng đợi `jobs` trong Postgres/Supabase (id, type, payload, status, attempts, result_ref). Worker Python dưới máy polling, xử lý xong ghi kết quả. Máy tắt thì job chờ, bật lên chạy tiếp, không cần mở port.
- Không dùng Execute Command: n8n 2.0 tắt node này mặc định, bật lại phải đặt `NODES_EXCLUDE`.
- **Luồng đơn:** n8n, hàng đợi, worker Python, các bước đơn lẻ.
- **Luồng phân tán:** cùng điểm kích hoạt từ n8n, job trỏ sang Spark (submit lên `local[8]` trước, sau đó lên cụm). Cờ `mode: single|distributed` trong payload quyết định luồng.
- Rate limit: token bucket, xoay key, backoff khi gặp 429.
- Active learning: comment có độ tin cậy dưới 0.7 vào hàng chờ duyệt (Label Studio), retrain hàng tuần.
- Nếu n8n gò bó, chuyển phần điều phối sang Prefect hoặc Dagster; n8n vẫn giữ trigger và thông báo.

---

## Brainstorm chức năng — Hóng drama

Ngoài web-dán-link đã bàn, dưới đây là 15 chức năng gợi ý. Nhóm theo mức độ "gap" so với social listening hiện có.

### Nhóm E — Dòng thời gian & lan truyền (gap trung bình)

| # | Chức năng | Mô tả |
|---|---|---|
| E1 | **Timeline reconstruction** | Cho một drama, agent dựng dòng thời gian tự động: ai nói gì lúc nào, điểm bùng phát, nhánh phụ |
| E2 | **Playback/replay timelapse** | Xem drama bùng nổ dạng 30 giây: comment xuất hiện theo thứ tự thật, màu theo cảm xúc |
| E3 | **Toxicity heatmap theo thời gian** | Biểu đồ độ độc hại tăng/giảm theo giờ, phát hiện "giờ cao điểm chửi" |
| E4 | **Velocity/forecasting** | Dựa trên tốc độ comment, sentiment velocity → dự báo "nguội trong 48h" hay "còn leo thang" |

### Nhóm F — Người và quan hệ (gap cao, đáng NCKH)

| # | Chức năng | Mô tả |
|---|---|---|
| F1 | **Narrative/stance clustering** | Gom comment cùng góc nhìn: "nhóm bênh", "nhóm chửi", "nhóm châm biếm", "nhóm trung lập" + comment đại diện mỗi nhóm (dùng cấu trúc graph thảo luận đã có) |
| F2 | **Influencer/KOL detector** | Comment nào được react/reply nhiều, tạo nhánh lớn → xếp top người ảnh hưởng của drama |
| F3 | **Troll/bot/seeding detection** | Phát hiện pattern comment lặp lại, tài khoản mới, cùng wording, cùng mốc thời gian → cảnh báo seeding/review bomb |
| F4 | **Hồ sơ nhân vật** | Mỗi `actor_related` trong schema NCKH → trang riêng: từng xuất hiện ở drama nào, sentiment người ta dành cho họ theo thời gian |
| F5 | **Cross-drama linking** | "Drama này liên quan tới drama Y 3 tháng trước không?" (cùng nhân vật, cùng công ty, cùng motif) → graph các drama |

### Nhóm G — Nội dung & kiểm chứng (gap cao)

| # | Chức năng | Mô tả |
|---|---|---|
| G1 | **Fact vs opinion separator** | Tách comment chứa claim thực tế (có số liệu, link) khỏi comment cảm xúc |
| G2 | **Debunk assistant** | Comment chứa thông tin sai → agent cross-check với báo chí (Firecrawl đã có) → gợi ý câu trả lời đính chính |
| G3 | **Audio/video drama extension** | Reels/TikTok có bình luận voice, hoặc video drama → VAD + ASR tiếng Việt → đưa vào cùng pipeline |

### Nhóm H — Sản phẩm hoá (dễ demo, khó NCKH)

| # | Chức năng | Mô tả |
|---|---|---|
| H1 | **Early warning cho brand/người** | Subscribe một brand/người → push notify khi drama nổ, kèm severity, vài comment đại diện |
| H2 | **Comparative report** | So hai sự kiện cùng loại: "khủng hoảng của A vs B" — cùng khung metric |
| H3 | **Export cho báo chí/PR** | Xuất PDF/slide "sự kiện X: hiện trạng, 3 insight, 10 trích dẫn tiêu biểu", dùng ngay cho bộ phận truyền thông |

### Chọn chức năng để nâng cấp drama

Nếu drama làm NCKH/CDIO4 lần hai, gap thật sự là **F1 + F3 + G1**: hai cái đầu tận dụng graph thảo luận đã có (nhánh reply_to_id) mà baseline Buzzmetrics/Kompa khó làm vì họ không giữ cấu trúc graph; G1 (fact vs opinion) là nền cho G2 (debunk) và là ứng dụng hiếm trên tiếng Việt. Thêm E1 (timeline) để có visual mạnh khi demo.

**Không khuyến nghị cho lần hai:** E3, H1, H2 — là tính năng dashboard, phần lớn Kompa/YouNet đã có, khó bảo vệ là đóng góp mới.
