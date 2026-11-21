# Mô hình ML và phân tích

Document loại 6/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-11-16 (viết lại mục 1 thành ba hướng phân tích; các mục còn lại user đã duyệt 2026-10-29, chưa duyệt lại mục 1 mới).

Phạm vi: code phân tích, PhoBERT, GNN và kết quả đang lưu trong dự án. Không dùng ý tưởng phát triển để mô tả cài đặt hiện tại. Lần rà soát này chỉ đọc code/JSON và kiểm tra vị trí artifact; không huấn luyện, gọi LLM hoặc nạp checkpoint.

Nguồn nhãn và chia tập xem [loại 5](./gan-nhan-va-tap-du-lieu.md); luồng xử lý xem [loại 2](./data-pipeline.md); cấu trúc kho dữ liệu xem [loại 3](./database-va-du-lieu.md). Phương pháp đo và benchmark sẽ có tài liệu riêng theo doc-map.

## 1. Ba hướng phân tích dữ liệu bình luận

*Viết lại 2026-11-16 theo mô tả của user. Các hướng 1 và 3 là hướng đã chốt hoặc đã hoãn, không phải mô tả code đang chạy; các mục 2–7 bên dưới vẫn mô tả bản code cũ.*

Mục tiêu chung: gán nhãn cảm xúc/lập trường cho bình luận rồi tổng hợp theo sự kiện. Có ba cách làm, độc lập với nhau.

### 1.1 Hướng 1: LLM đọc cả cụm bình luận, giữ nguyên cấp bậc

Ý tưởng gốc: lấy bình luận đưa cho LLM phân tích. Có hai biến thể:

| | Cách cũ (làm phẳng) | Cách mới (giữ cấu trúc lớp) |
|---|---|---|
| Đơn vị đưa vào LLM | Mỗi bình luận và reply là một mục riêng trong danh sách phẳng | Một bình luận cấp 1 cùng toàn bộ reply con của nó |
| Reply | Tách khỏi cây; chỉ kèm một dòng ngữ cảnh cha (80 ký tự đầu) | Không tách; gom lại một chỗ, giữ nguyên cấp bậc |
| Bình luận cấp 1 không có reply | Một mục riêng | Phân tích riêng một mình nó |
| Bình luận cấp 1 có reply | Cha và con là các mục rời, rải trong các batch | Phân tích cả cụm (cha + reply con) trong một lần đọc |
| Cây | Dựng lại sau khi có nhãn, để tính `thread_stats` | Cấu trúc được giữ từ đầu vào |

Cách cũ là `analysis/single/analyze_comments.py` (mục 2). Cách mới là hướng user chốt: LLM thấy cả cuộc trao đổi nên hiểu được reply chỉ có nghĩa trong ngữ cảnh (ví dụ reply tag tên người khác, đồng tình hay phản bác comment cha).

**Cài đặt cách mới: `analysis_new/` (2026-11-17), có bản đơn luồng và bản PySpark dùng chung module.**

| Mục | Cách làm |
|---|---|
| Đầu vào | **Định dạng chính thức (user chốt 2026-11-17)**, ví dụ `data/sample/showbiz_068 (1).json`: `{id_content, event_name, sort_mode, post_content, comments[]}`, mỗi comment `{comment_id, order, text, likes, reply_count, replies[]}`, reply có thêm `reply_to_id` và lồng tiếp `replies` (nhiều cấp). Loader duỗi cây thành danh sách phẳng, `parent_id` lấy theo vị trí trong cây. Định dạng B phẳng cũ không còn đọc |
| Lọc rác | Rule `is_trash_rule` giữ nguyên bản cũ; comment rác vẫn hiện trong cụm làm ngữ cảnh nhưng không gán nhãn; cụm toàn rác không gọi LLM |
| Prompt | Nhiều cụm/request (tối đa 60 comment; nội dung bài đăng cắt 2.000 ký tự), mỗi comment mã cục bộ `K<cụm>.<số>`, thụt lề theo cấp, ghi "trả lời Kx.y". LLM trả nhãn từng comment + `summary` 1–2 câu mỗi cụm |
| Nhãn | Showbiz: emotion + toxic/toxic_type. Giáo dục: 4 stance gán một bước (bỏ bước 2 "cần xem xét" của bản cũ) + 1 request tổng hợp/sự kiện (thay 5 request cũ) |
| API | `mmodiary` `POST /v1/responses`; key dòng 4 `.env.local` (nhiều key cách bằng dấu phẩy), model tuần tự từ `model_list.txt`: dùng một model tới khi lỗi mới đổi; key hết số dư thì sang key kế. Hết key/model thì dừng |
| Đầu ra | `full/<event_id>.json` (comment gốc + `level`, `root_id`, nhãn, `label_source`; danh sách `clusters` với summary, `thread_stats`), `summary/<event_id>.json` cùng khoá với bản cũ để `analyze_insights.py` đọc được, `run_log.jsonl` |
| Chạy | Mặc định chỉ ước tính số request + ghi prompt mẫu `_dry_run/`; `--yes` mới gọi API, `--max-requests` chặn chạy vượt. Sự kiện đã có summary thì bỏ qua (resume) |

Bản PySpark (`analysis_new/spark/run_analysis_spark.py`): `flatMap` sự kiện → request, `mapPartitions` gọi LLM (mỗi partition một client, `--threads` = số request đồng thời), join theo `event_id` rồi gộp nhãn; driver ghi file. Sự kiện có request lỗi thì không ghi.

**Kiểm chứng (2026-11-17, gọi API thật):** response mmodiary có text ở `output[].content[].text` (kèm `usage`, có `reasoning_tokens`). File `showbiz_068`: 787 comment, 590 cụm, sâu 7 cấp → 12 request. Đo trên bộ con 150 comment, model `doitac3/deepseek-v4.1-flash`: lô 60 comment mất ~130s, đủ nhãn 57/57 và tóm tắt 47/47 cụm; lô 150 comment từng ra 122/125 nhãn méo chữ ("Trung立"), nhưng lần chạy sau lô 60 cũng bị 47/57 → lỗi ngẫu nhiên của model, không do kích thước lô. Sửa: LLM trả nhãn bằng mã ASCII (`PN/CK/DC/UH/TL`, `TC/TI/TL/YK`, toxic `CB/CN/NT`), code đổi về tiếng Việt; vẫn giữ 60 comment/request vì đã kiểm chứng. Thời gian chờ mỗi request 600s (180s cũ gây timeout rồi gửi lại, tốn request). Cảnh báo khi >20% nhãn của một request bị fallback. 14 test offline đạt.

Giới hạn: rule rác cũ coi reply "tên người + dưới 30 ký tự" là rác, nên một số reply tag tên có nội dung ngắn bị bỏ khỏi gán nhãn.

### 1.2 Hướng 2: fine-tune PhoBERT

Fine-tune `vinai/phobert-base-v2` trên dữ liệu đã gán nhãn (`labeling data/`), rồi áp dụng để dự đoán nhãn cho bình luận mới. Chi tiết cài đặt ở mục 5 và `ml/phobert/`.
- Mỗi bình luận được phân loại theo nội dung của chính nó; mô hình không đọc cụm reply như hướng 1.
- Chưa chạy fine-tune thật (cần Colab/GPU). Từ 2026-11-21 code đọc cột `label` và `is_synthetic`; dòng sinh chỉ vào tập train, không vào val/test (user đồng ý 2026-11-21).

### 1.3 Hướng 3: GNN (tạm hoãn)

Phân loại nút bình luận trên đồ thị thảo luận (mục 6–7, `ml/gnn/`). **Tạm hoãn theo user, 2026-11-16:** `labeling data/` là mẫu ngẫu nhiên cộng dòng sinh, không có quan hệ cha-con nên không dùng được cho GNN. Mở lại khi có dữ liệu cào đủ cây reply, gán nhãn trên chính dữ liệu đó. Khung đã có và baseline thử cho GNN ≈ MLP vì đồ thị 0 cạnh: xem [khung-gnn-neo4j-phobert.md](./khung-gnn-neo4j-phobert.md).

### 1.4 Bảng cài đặt hiện có

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

Công thức score và quy tắc trigram bám nhánh Python. Import đã sửa sang `preprocessing.spark...` (2026-11-17) và script đã chạy lại được trên snapshot hiện tại. Không khẳng định hai nhánh tương đương trên snapshot mới khi chưa kiểm tra lại.

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
5. Working tree hiện có `ml/gnn/train_gnn_colab.ipynb`, `ml/gnn/requirements.txt` và notebook fine-tune PhoBERT. Requirements GNN chỉ khai báo active các gói chuẩn bị local; nhóm torch/transformers/PyG cho Colab còn ở comment. Notebook chưa có output được lưu, checkpoint vẫn cần đối chiếu đúng vị trí; sự hiện diện của notebook không chứng minh đã chạy lại thành công. Chi tiết tái lập ở loại 16.

6. Từ 2026-11-07 có khung chuẩn bị cho lần làm lại (embedding API, split theo sự kiện, Neo4j, code fine-tune PhoBERT mới): xem [khung-gnn-neo4j-phobert.md](./khung-gnn-neo4j-phobert.md). Các mục 5–7 ở trên mô tả bản code cũ.

## 9. Nguồn đối chiếu

- [Insight](../analysis/single/analyze_insights.py), [gộp sự kiện](../analysis/single/merge_final_data.py), [phân tích Showbiz](../analysis/single/analyze_comments.py), [Giáo dục](../analysis/single/analyze_education_async.py).
- [PMI Python](../analysis/single/Analyze%20keywords.py), [giải thích PMI đã có](../analysis/single/analyze_keywords_explanation.md), [PMI Spark](../analysis/spark/pyspark_pmi_keywords.py).
- [PhoBERT fine-tune](../ml/phobert/phobert_finetune_colab.py), [batch inference](../ml/phobert/phobert-batch-inference.py).
- [Dựng graph](../ml/gnn/build_discussion_graph.py), [PhoBERT features](../ml/gnn/extract_phobert_features.py), [TF-IDF](../ml/gnn/extract_tfidf_features.py), [ghép features](../ml/gnn/concat_node_features.py).
- [GraphSAGE](../ml/gnn/model_graphsage_classifier.py), [trainer](../ml/gnn/train_gnn_node_classification.py), [so sánh GNN/LLM](../ml/gnn/evaluate_gnn_vs_llm.py), [README GNN cũ](../ml/gnn/README.md).
- [Metric Giáo dục](../data/gnn/metrics_education.json), [metric Showbiz](../data/gnn/metrics_showbiz.json).
