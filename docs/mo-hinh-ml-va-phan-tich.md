# Mô hình ML và phân tích

Document loại 6/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **User đã duyệt ngày 2026-10-29.**

Phạm vi: code phân tích, PhoBERT, GNN và kết quả đang lưu trong dự án. Không dùng ý tưởng phát triển để mô tả cài đặt hiện tại. Lần rà soát này chỉ đọc code/JSON và kiểm tra vị trí artifact; không huấn luyện, gọi LLM hoặc nạp checkpoint.

Nguồn nhãn và chia tập xem [loại 5](./gan-nhan-va-tap-du-lieu.md); luồng xử lý xem [loại 2](./data-pipeline.md); cấu trúc kho dữ liệu xem [loại 3](./database-va-du-lieu.md). Phương pháp đo và benchmark sẽ có tài liệu riêng theo doc-map.

## 1. Các nhóm phương pháp hiện có

| Nhóm | Cài đặt | Vai trò hiện tại |
|---|---|---|
| Rule + LLM | `analysis/single/analyze_comments.py`, `analyze_education_async.py` | Tạo emotion/toxic Showbiz, stance Giáo dục và summary |
| Thống kê tổng hợp | `merge_final_data.py`, `analyze_insights.py` | Gộp theo sự kiện và tính insight từ summary |
| Từ khóa PMI | `Analyze keywords.py`, `analysis/spark/pyspark_pmi_keywords.py` | Xếp hạng từ/cụm từ; không phải classifier có nhãn |
| PhoBERT classifier | `ml/phobert/` | Code fine-tune và batch inference riêng cho từng lĩnh vực |
| GraphSAGE | `ml/gnn/` | Phân loại nút bình luận trên đồ thị thảo luận |

Code serving đã đọc dùng `insights.json`/SQLite: `build_db.py` đọc top sự kiện từ insight; dashboard tải insight qua GitHub. `merge_final_data.py` nhận summary đã phân tích, còn `analyze_insights.py` tổng hợp JSON. Các file này không tự gọi classifier PhoBERT/GNN hoặc nạp dự đoán của chúng. Vì vậy, có code ML không đồng nghĩa mô hình đã thay LLM trong luồng phục vụ hiện tại.

## 2. Phân tích cảm xúc, lập trường và thread

Hai script phân tích dùng Groq `llama-3.3-70b-versatile`; rule lọc rác chạy trước. Showbiz có năm emotion và toxic riêng; Giáo dục có bốn stance, với bước xét lại nhóm nhãn trung gian. Bộ nhãn, fallback và nguồn dữ liệu chi tiết ở loại 5.

Sau khi gán nhãn, script dựng lại cây comment/reply và tạo `thread_stats`. Cờ `controversial` là heuristic theo phân bố nhãn: số bình luận hợp lệ trong thread lớn hơn 1 và tỷ lệ nhãn đông nhất nhỏ hơn 0,7. Đây không phải mô hình học phát hiện tranh cãi hay kiểm chứng tính đúng/sai của nội dung.

Showbiz xuất thống kê emotion, toxic, bình luận nổi bật và thread tranh cãi. Giáo dục xuất số lượng/diễn giải theo stance. Nhãn trung lập có thể đến từ fallback khi lỗi hoặc thiếu kết quả LLM; artifact cuối không luôn giữ dấu vết riêng cho nguồn fallback. Không diễn giải toàn bộ nhãn trung lập là kết quả LLM thành công.

## 3. Gộp và tạo insight

`merge_final_data.py` đọc nội dung sự kiện từ dữ liệu web, gộp summary theo `id_content` và xuất theo hai lĩnh vực. Script giữ sự kiện chưa có phân tích; không tự sinh nhãn từ nội dung web. Trường `parse_error` của record web bị bỏ khi chuẩn hóa nhưng record vẫn được giữ, nên việc đã gộp không chứng minh nội dung đầu vào đạt chất lượng.

`analyze_insights.py` tính các đại lượng sau:

| Đại lượng | Cách tính trong code |
|---|---|
| Sự kiện có phân tích | Đếm record có khóa `analyzed`; khóa tồn tại không đồng nghĩa dữ liệu bên trong đầy đủ |
| Giáo dục: sạch/rác | `comment_counts.total - comment_counts.rác` và số rác trong summary |
| Showbiz: sạch/rác | Sạch là tổng `emotion_stats`; rác là `max(total_comments - clean, 0)` |
| Phân bố stance/emotion | Cộng count qua các summary và tính phần trăm, làm tròn một chữ số |
| Toxic Showbiz | Cộng `total_toxic` và ba loại độc hại; phần trăm chia số bình luận sạch |
| Top sự kiện | Xếp giảm dần theo số sạch và lấy tối đa 10 mỗi lĩnh vực |
| Năm sự kiện | Lấy bốn ký tự đầu `time_event`, thiếu thì `unknown`; không parse ngày đầy đủ |

Đây là tổng hợp từ summary, không chạy lại phân loại từng bình luận và không tự kiểm tra chênh lệch với các file `full/`. Không coi số liệu đầu ra là số đếm trực tiếp từ cây bình luận hiện tại. Chênh snapshot đã ghi ở loại 5.

## 4. Phân tích từ khóa PMI

### 4.1 Nhánh Python

`analysis/single/Analyze keywords.py` đọc danh sách bình luận phẳng cho từng lĩnh vực, tách từ bằng underthesea, lowercase và lọc token/stopwords. Nó thống kê unigram, bigram và trigram trong phạm vi từng bình luận.

Bigram dùng công thức `PMI(w1,w2) = log2(P(w1,w2) / (P(w1) × P(w2)))`: xác suất bigram lấy count chia tổng bigram, xác suất từng từ lấy count chia tổng unigram. Bigram được giữ khi đủ tần suất và vượt ngưỡng PMI, cùng các kiểm tra token/stopwords trong code.

Trigram chỉ giữ khi đủ tần suất và hai bigram liền kề đều đã vượt bộ lọc; điểm trigram là trung bình PMI của hai bigram đó, không phải một ước lượng PMI ba biến riêng.

Ở vòng đếm xếp hạng, unigram cấu thành cụm high-PMI bị suppress. Điểm cuối là `frequency × log2(1 + max(PMI, 0))`; unigram còn lại có PMI 0 nên score 0. Code còn thống kê tần suất theo mã sự kiện trích từ `comment_id`.

`main()` đặt `min_count = 3`, `min_pmi = 1.0`, top 10 mỗi lĩnh vực; mặc định của các hàm bên trong là `min_count = 5`, nên phải phân biệt cấu hình entry point và mặc định hàm. Đầu vào được tìm cùng thư mục script; `main()` hiện ghi `keyword_analysis_v4.txt`. File JSON từ khóa đã có trong kho dữ liệu không phải đầu ra được tái tạo trực tiếp bằng đoạn `main()` hiện tại này.

### 4.2 Nhánh Spark

`analysis/spark/pyspark_pmi_keywords.py` đọc Parquet sạch, tokenize qua UDF, tạo n-gram và đếm bằng Spark. Phần bigram/trigram đủ tần suất được collect về driver để tính PMI; không phải mọi bước đều phân tán. Mặc định CLI: min-count 3, min-pmi 1.0, top 10, threads 4; có tùy chọn `--strip-names`.

Công thức score và quy tắc trigram bám nhánh Python. File hiện còn import `data.spark...` trong khi module đã chuyển thư mục; chưa chạy lại được coi là thành công chỉ từ artifact cũ. Không khẳng định hai nhánh tương đương trên snapshot mới khi chưa kiểm tra lại.

## 5. PhoBERT: classifier bình luận

### 5.1 Kiến trúc và dữ liệu

`phobert_finetune_colab.py` dùng `vinai/phobert-base-v2` qua `AutoModel`; lấy hidden state token đầu, dropout 0,1, Linear từ 768 chiều ra số lớp. Showbiz có sáu lớp (năm emotion + `is_trash`), Giáo dục có năm lớp (bốn stance + `is_trash`). Không có head toxic riêng trong classifier này.

Tokenizer pad/truncate tối đa 256 token. Script đưa text từ CSV trực tiếp vào tokenizer, không có bước word segmentation tiếng Việt riêng được gọi trước đó trong luồng fine-tune. Nguồn nhãn ưu tiên `verified_label`, fallback nhãn LLM; cờ `is_trash=True` ghi đè nhãn cuối. Các giới hạn kiểm duyệt và chia tập đã nêu ở loại 5.

### 5.2 Huấn luyện và đầu ra

| Mục | Cấu hình mặc định trong code |
|---|---|
| Chia tập | Stratified theo dòng, train/val/test 70/15/15, seed 42 |
| Epoch / batch / LR | 10 / 16 / 2e-5 |
| Loss | Cross entropy với class weight balanced tính từ train |
| Optimizer | AdamW, weight decay 0,01; clip gradient norm 1,0 |
| Scheduler | Linear, warmup 10% tổng bước dự kiến |
| Chọn checkpoint | Val F1-macro tốt nhất; early stopping patience 3 |
| Thư mục mặc định | `/content/phobert_checkpoints/{domain}/` |
| File xuất | `best_model.pt`, `config.json`, `test_results.json` |

Config lưu mapping `label2id`/`id2label` cùng cấu hình chính; checkpoint lưu state dict, epoch và best F1. Script không xuất sẵn manifest chia tập cố định. Nếu không có val F1 nào lớn hơn giá trị khởi tạo 0, đoạn train không tạo best checkpoint mới nhưng bước sau vẫn cố nạp file; chưa có xử lý hoàn chỉnh trường hợp này.

### 5.3 Batch inference

`phobert-batch-inference.py` nhận model directory và CSV, nạp config/checkpoint, tokenize theo cấu hình rồi ghi CSV thêm `predicted_label`, `confidence`. Confidence là max softmax, không có bước hiệu chỉnh xác suất hoặc ngưỡng chuyển sang LLM. `--domain` là tham số bắt buộc nhưng mapping thực tế lấy từ config; không thấy bước kiểm tra domain yêu cầu khớp domain của checkpoint.

Chưa tìm thấy bộ checkpoint/config/test_results của classifier PhoBERT trong các vị trí artifact local đã khảo sát. Vì vậy tài liệu chỉ mô tả code, chưa có metric PhoBERT đã xác minh từ file hiện tại. Embedding PhoBERT dùng cho GNN không tự chứng minh classifier đã fine-tune thành công.

## 6. GNN: đồ thị và đặc trưng

### 6.1 Dựng đồ thị thảo luận

`build_discussion_graph.py` tạo một graph cho mỗi sự kiện. Node là comment/reply không rác có nhãn hợp lệ; Giáo dục dùng bốn stance, Showbiz dùng năm emotion. Không thêm lớp rác vào GNN.

Cạnh ban đầu có hướng `reply → parent`, chỉ giữ khi cả hai node còn hợp lệ. Nếu comment cha bị lọc, node reply có thể còn nhưng cạnh tới cha bị bỏ. Mỗi node có depth, in-degree và sibling count; node không có cha hợp lệ được gom vào nhóm `ROOT` khi tính sibling. Mã comment trùng trong sự kiện có thể làm bảng ánh xạ ID→index ghi đè; không mặc định đồ thị đã khắc phục vấn đề ID trong dữ liệu nguồn.

Đầu ra code là `graphs_{domain}.pkl`, `nodes_meta_{domain}.parquet` trong `data/gnn/`.

### 6.2 Đặc trưng hybrid

| Nguồn | Cài đặt |
|---|---|
| PhoBERT 768 chiều | `extract_phobert_features.py`: lấy token đầu, mặc định pretrained; tùy chọn checkpoint chỉ nạp phần `bert.*` của classifier đã fine-tune |
| TF-IDF tối đa 300 chiều | `extract_tfidf_features.py`: unigram/bigram, min_df 3, max_df 0,9, lowercase và gộp whitespace |
| Cấu trúc 3 chiều | depth, in-degree, sibling count |

`concat_node_features.py` dùng thứ tự chuẩn `event_id::comment_id`, assert ID PhoBERT/TF-IDF khớp rồi ghép thành mảng float32. Kích thước được thiết kế là 768 + 300 + 3 = 1.071, nhưng TF-IDF có thể có ít hơn 300 features nếu vocabulary không đủ; metadata slice đang viết cố định theo 300.

TF-IDF được fit trên mọi node trước khi chia train/test; GNN training giữ graph và feature toàn bộ node khi message passing. Đây là thiết lập chia node trên graph đã biết, không chứng minh khả năng tổng quát sang sự kiện hoàn toàn mới.

## 7. GNN: mô hình, huấn luyện và artifact

`GraphSAGEClassifier` có hai `SAGEConv` mean aggregation, hidden 128, ReLU, dropout 0,3 giữa hai lớp, rồi Linear ra bốn/năm lớp. Constructor import PyG trực tiếp; docstring nói fallback pure PyTorch nhưng không có nhánh fallback thực tế trong constructor.

Trainer nối graph các sự kiện bằng offset index, thêm cạnh đảo chiều để message passing hai hướng; không thêm cạnh giữa hai sự kiện. Chia node stratified 70/15/15, seed 42. Mặc định 300 epoch, LR 1e-3, Adam weight decay 5e-4, early stopping patience 50 theo val F1-macro.

Chế độ loss auto: Giáo dục dùng weighted cross entropy với sqrt-inverse weight; Showbiz dùng focal loss gamma 2 với log-inverse weight. Weight lấy từ nhãn train. Code cho phép chọn loss/weight khác; metric đang lưu không đủ thông tin để suy ra chắc chắn đã dùng đúng mặc định hiện tại.

Trainer xuất `checkpoints/gnn_{domain}.pt`, `metrics_{domain}.json`, `predictions_{domain}.json`; predictions gồm cả train/val/test kèm trường split. Metric test phải đọc đúng split, không coi dự đoán toàn node là test độc lập.

| Metric JSON đang lưu tại `data/gnn/` | Train / val / test | Test F1-macro | Test F1-weighted |
|---|---|---:|---:|
| Giáo dục | 3.759 / 805 / 806 | 0,5239 | 0,6267 |
| Showbiz | 14.280 / 3.060 / 3.060 | 0,2170 | 0,9161 |

Đây là số đọc từ file cũ, không phải kết quả huấn luyện lại. Weighted F1 Showbiz cao không phủ nhận macro F1 thấp; nhãn dùng để đánh giá là nhãn trong artifact, chưa chứng minh gold set độc lập.

Đọc header NPY (không nạp tensor) cho thấy node_features Giáo dục có shape (5.370, 1.071), Showbiz (20.400, 1.071); embedding PhoBERT tương ứng (5.370, 768) và (20.400, 768), đều float32. Code dựng graph chỉ giữ nhãn hợp lệ, nên loại lỗi chính tả `Ứng hộ`; không tự chuẩn hóa như script export 5k.

Các `.npy` PhoBERT/node_features và checkpoint GNN tìm thấy ở `data/gnn-result/content/drive/MyDrive/NCKH/NCKH_hong_drama/data/gnn/`, trong khi script mặc định đọc/ghi `data/gnn/`. Không tự suy ra các artifact khớp hoàn toàn code/JSON metric hiện tại khi chưa kiểm tra nguồn và phiên chạy.

`evaluate_gnn_vs_llm.py` đọc metric đã có và có hàm đo inference GNN trên toàn bộ node: nạp checkpoint, warmup rồi lấy thời gian trung bình 5 forward pass. Phía LLM dùng giả định 0,5 giây/bình luận và hằng số token/chi phí. Speedup/chi phí trong bản đánh giá không phải phép benchmark LLM thật hay bảng giá hiện tại; cần phân biệt với đo inference GNN.

## 8. Hiện trạng và giới hạn còn mở

1. Theo trạng thái user đã lưu, PhoBERT và GNN chưa được chấp nhận hoàn thành, vẫn pending và cần làm lại; code/artifact không đổi trạng thái đó.
2. Chưa có bằng chứng nối dự đoán PhoBERT/GNN vào luồng tạo summary/insight đang phục vụ web. Không có fallback LLM tự động trong batch inference hiện tại.
3. CSV kiểm duyệt chưa có verified_label, có ID lặp; chia theo dòng/node và TF-IDF fit toàn dữ liệu giới hạn cách diễn giải kết quả. Chi tiết dữ liệu ở loại 5.
4. Snapshot insight/full không hoàn toàn khớp; code tổng hợp hiện tại và artifact có thể khác phiên bản. Cần xác định input/lần chạy chuẩn để tái lập.
5. README GNN có đường dẫn notebook/requirements/checkpoint mang tính hướng dẫn nhưng không phải tất cả file đều có trong working tree; tài liệu này mô tả code đã kiểm tra, không coi chuỗi lệnh cũ là đã chạy lại thành công.

## 9. Nguồn đối chiếu

- [Insight](../analysis/single/analyze_insights.py), [gộp sự kiện](../analysis/single/merge_final_data.py), [phân tích Showbiz](../analysis/single/analyze_comments.py), [Giáo dục](../analysis/single/analyze_education_async.py).
- [PMI Python](../analysis/single/Analyze%20keywords.py), [giải thích PMI đã có](../analysis/single/analyze_keywords_explanation.md), [PMI Spark](../analysis/spark/pyspark_pmi_keywords.py).
- [PhoBERT fine-tune](../ml/phobert/phobert_finetune_colab.py), [batch inference](../ml/phobert/phobert-batch-inference.py).
- [Dựng graph](../ml/gnn/build_discussion_graph.py), [PhoBERT features](../ml/gnn/extract_phobert_features.py), [TF-IDF](../ml/gnn/extract_tfidf_features.py), [ghép features](../ml/gnn/concat_node_features.py).
- [GraphSAGE](../ml/gnn/model_graphsage_classifier.py), [trainer](../ml/gnn/train_gnn_node_classification.py), [so sánh GNN/LLM](../ml/gnn/evaluate_gnn_vs_llm.py), [README GNN cũ](../ml/gnn/README.md).
- [Metric Giáo dục](../data/gnn/metrics_education.json), [metric Showbiz](../data/gnn/metrics_showbiz.json).
