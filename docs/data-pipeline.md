# Data pipeline

Document loại 2/16 (xem `docs/doc-map.md`). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: chỉ mô tả pipeline đang có trong code và dữ liệu. Hạng mục làm sau (micro-batch, luồng phân tán, Phase 01 PySpark làm lại, luồng cào FB mới) nằm ở bảng "Việc làm sau" trong `doc-map.md`, chưa viết vào đây.
Cấu trúc dữ liệu từng file: loại 3. Cách n8n thu thập: loại 4. Số đo hiệu năng: loại 8.

---

## 1. Tổng quan

Có **hai nhánh xử lý song song** trên cùng dữ liệu bình luận sạch:
- **Nhánh chính (Python, đã dùng để ra dữ liệu cuối):** lọc rác → gán nhãn bằng LLM → gộp → insight → DB web.
- **Nhánh Spark:** tiền xử lý và PMI bằng PySpark, dùng để đối chiếu với nhánh Python (benchmark, kiểm tra trùng khớp). Không tham gia ra dữ liệu cuối của web/dashboard.

```mermaid
flowchart TD
  N8N[n8n: JSON thô\nbáo chí + bình luận FB] --> RAW[(data/raw/\nGoogle Drive)]
  RAW --> S1[1. Chuẩn hóa schema + gộp\n(script lưu trữ)]
  S1 --> S2[2. tienxuly_vietlaiorder.py\nLLM lọc rác, đánh order, comment_id]
  S2 --> CLEAN[(cleaned_data_input /\ninput_clean_data)]
  CLEAN --> S3E[3a. analyze_education_async.py\nstance]
  CLEAN --> S3S[3b. analyze_comments.py\nemotion + toxic]
  S3E --> AN[(analyzed_data/full + summary)]
  S3S --> AN
  AN --> S4[4. merge_final_data.py\n+ data_web.json]
  S4 --> OUT[(data/processed/outputnew)]
  OUT --> S5[5. analyze_insights.py] --> INS[(insights.json)]
  AN --> S6[6. aggregate_comments_v2.py] --> FLAT[(*_comments.json phẳng)]
  FLAT --> S7[7. Analyze keywords.py\nPMI + n-gram] --> KW[(keyword_analysis_v4.*)]
  INS --> S8[8. build_db.py] --> DB[(events.db)]
  CLEAN -.-> SP1[Spark: pyspark_preprocessing.py] --> PQ[(spark-output/clean Parquet)]
  PQ -.-> SP2[Spark: pyspark_pmi_keywords.py]
  AN --> GR[ml/gnn: dựng đồ thị] --> GN[(data/gnn/)]
  AN --> SM[sampling_labeling/\nexport_5k_for_verification.py] --> LB[(verify_*_5k.xlsx/csv)]
```

## 2. Các bước (nhánh chính)

| # | Bước | Script | Đầu vào | Đầu ra | Ghi chú |
|---|---|---|---|---|---|
| 0 | Thu thập | n8n (ngoài repo) | Google Sheets (URL `pending`) | JSON thô, Drive | Xem loại 4 |
| 1 | Chuẩn hóa schema cũ → mới, gộp file | `data/archive/luu_tru/normalize_education.py`, `Normalize showbiz.py`, `merge_data.py` | JSON cũ (khóa theo tên nhân vật) | JSON theo `id_content` | Script nằm trong thư mục lưu trữ, không còn ở thư mục chính |
| 2 | Lọc rác, đánh lại thứ tự | `preprocessing/single/tienxuly_vietlaiorder.py` | thư mục `input_clean_data` | thư mục `cleaned_data_input` | Gemini 2.5 Flash, batch 20 bình luận, xoay key khi `ResourceExhausted`. Gán `order` và `comment_id = cmt_{id_content}_{0001}`. Bỏ qua file đã có ở đích. Thư mục vào/ra viết cứng tương đối theo thư mục chạy |
| 3a | Gán lập trường (Giáo dục) | `analysis/single/analyze_education_async.py` | `cleaned_data_input` | `analyzed_dataa/{full,summary}`, `run_log.jsonl` | Groq `llama-3.3-70b-versatile`, batch 10, hai bước (nhận diện cơ bản rồi phân tích sâu "trung lập" và "ý kiến riêng"). Nhãn: tích cực / tiêu cực / trung lập / ý kiến riêng |
| 3b | Gán cảm xúc + độc hại (Showbiz) | `analysis/single/analyze_comments.py` | `input_clean_data` | `analyzed_data/{full,summary}`, `run_log.jsonl` | Groq `llama-3.3-70b-versatile`, batch 10, `asyncio.Semaphore`. Lọc rác bằng luật (`is_trash_rule`) trước khi gọi LLM, kiểm `valid_ids` chống LLM bịa. Nhãn: Phẫn nộ / Cà khịa / Đồng cảm / Ủng hộ / Trung lập; toxic: chửi bới / công kích cá nhân / công kích người thân |
| 4 | Gộp phân tích + dữ liệu web | `analysis/single/merge_final_data.py --web --edu_sum [--show_sum] --output` | `data_web.json`, `summary/` | `data/processed/outputnew/{education,showbiz}` (40 và 45 file) | Gộp theo `id_content`; sự kiện chưa phân tích vẫn có file |
| 5 | Insight tổng hợp | `analysis/single/analyze_insights.py --input --output` | `outputnew/` | `data/analysis-output/insights.json` | Có `overall`, `education`, `showbiz` (xem loại 3) |
| 6 | Gộp bình luận phẳng | `sampling_labeling/aggregate_comments_v2.py` | `analyzed_data*/full` | `showbiz_comments.json`, `education_comments.json` | Bỏ bình luận `is_trash` |
| 7 | Từ khóa PMI | `analysis/single/Analyze keywords.py` | `education_comments.json`, `showbiz_comments.json` | `keyword_analysis_v4.txt` cạnh script (JSON hiện có là artifact riêng, chưa xác minh bước xuất) | Unigram/bigram/trigram, `min_count=3`, ngưỡng PMI 1.0, `score = freq × log2(1+PMI)`, stopwords. Giải thích thuật toán: `analysis/single/analyze_keywords_explanation.md` |
| 8 | Dữ liệu cho web | `serving/web_v2/backend/build_db.py` | `data_web.json`, `insights.json`, Apps Script | `events.db` | Xem loại 3, 10 |

Các nhánh phụ:
- **Đồ thị / GNN** (`ml/gnn/`): `build_discussion_graph.py` → `extract_tfidf_features.py` / `extract_phobert_features.py` → `concat_node_features.py` → `train_gnn_node_classification.py` → `evaluate_gnn_vs_llm.py`. Đầu ra ở `data/gnn/`. Chi tiết: loại 6.
- **Lấy mẫu gán nhãn** (`sampling_labeling/`): `export_5k_for_verification.py` (seed 42, 5000 mẫu mỗi lĩnh vực) → `data_labels/verify_{domain}_5k.xlsx/.csv`. Phụ trợ: `count_comments.py`, `count_nontrash_comments.py`, `map_id_content.py` (ghi `id_content` vào Google Sheet), `sample_comments.py` (lấy mẫu phân tầng theo cảm xúc). Chi tiết: loại 5.

## 3. Nhánh Spark

| Script | Việc | Đầu vào | Đầu ra |
|---|---|---|---|
| `preprocessing/spark/pyspark_preprocessing.py` | Đọc JSON ở driver Python (tránh lỗi `winutils` trên Windows), `explode` cây bình luận (root + reply, `depth` 0/1), lọc rác bằng UDF `is_trash` | `--inputs` (các thư mục JSON), `--output`, `--threads` (mặc định 4) | Parquet: `id_content, event_name, comment_id, parent_comment_id, order, text, likes, depth` |
| `preprocessing/spark/is_trash_rule.py` | Hàm `is_trash(text)` thuần, không gọi LLM: quá ngắn (<3 ký tự), chỉ emoji, chỉ tag tên, chuỗi lặp, chỉ thán từ | – | – |
| `preprocessing/spark/text_tokenizer.py` | Tách từ `underthesea`, lowercase, bỏ dấu câu; import lười trong worker | – | – |
| `preprocessing/spark/spark_session_factory.py` | `get_spark(app_name, n_threads)`; đặt `JAVA_HOME`, `PYSPARK_PYTHON`, `HADOOP_HOME` | – | `SparkSession` `local[N]` |
| `analysis/spark/pyspark_pmi_keywords.py` | Parquet → tokenize UDF → n-gram → đếm → PMI → top-N, cùng công thức bản Python | `--parquet`, `--output`, `--top` | `keyword_analysis_spark.json` |
| `preprocessing/spark/verify_preprocessing.py` | Kiểm tập `comment_id` Spark = tập bản đơn luồng; đạt khi Jaccard = 1.0 | `data/spark-output/clean` | in kết quả |
| `analysis/spark/verify_pmi_keywords.py` | So top-10 PMI Spark và baseline; đạt khi Jaccard ≥ 0.7 và top-5 trùng 100% | `benchmark/keyword_analysis_spark.json` | in kết quả |

Khác biệt chính giữa hai nhánh ở bước lọc rác: nhánh Python dùng LLM (bước 2) kết hợp luật (bước 3b), nhánh Spark chỉ dùng luật.

Môi trường Spark viết cứng trong `spark_session_factory.py`: `JAVA_HOME=D:/jdk/jdk-17.0.13+11`, `HADOOP_HOME=D:/hadoop`, Python của `.venv-ml`. Đổi máy thì sửa các hằng này.

## 4. Các tầng dữ liệu theo thư mục

| Thư mục | Nội dung | Số lượng |
|---|---|---|
| `data/raw/` | `data_web.json` (nội dung báo, khóa `showbiz` / `giáo dục`), `data_Sukien.json` (tên sự kiện + nhân vật), `education.json`, `showbiz.json`, `*_comments_new.json`, `total_comments.json`, `clean_data(chua_viet_lai_oder)/` | – |
| `data/processed/process_education/` | `input_clean_data/`, `cleaned_data_input/`, `analyzed_dataa/{full,summary}` | 21 file mỗi thư mục |
| `data/processed/process_showbiz/` | `input_clean_data/`, `analyzed_data/{full,summary}` | 29 file mỗi thư mục |
| `data/processed/outputnew/` | Kết quả bước 4 | 40 + 45 file |
| `data/spark-output/clean/` | Parquet từ nhánh Spark | 8 part |
| `data/analysis-output/` | `insights.json`, `keyword_analysis_v4.*` | – |
| `data/test-sets/` | `data_test_edu.json`, `data_test_show.json`, `data_test_show_da_check.json` | – |
| `data/gnn/`, `data/gnn-result/` | Đồ thị, đặc trưng, metrics của GNN; kết quả từ Colab | – |
| `data/archive/` | `luu_tru/` (script và dữ liệu cũ), `workspace/`, `education_fb.json` | – |

Quy mô theo `insights.json`: 85 sự kiện (40 Giáo dục, 45 Showbiz), **50 sự kiện đã phân tích** (20 + 30); 36.078 bình luận thô, 29.622 sạch, 6.456 rác (17,9%).

## 5. Cách chạy (theo `README.md` và docstring, đối chiếu code)

```bash
# Spark: tiền xử lý
python preprocessing/spark/pyspark_preprocessing.py \
  --inputs data/processed/process_education/cleaned_data_input data/processed/process_showbiz/input_clean_data \
  --output data/spark-output/clean
# Spark: PMI
python analysis/spark/pyspark_pmi_keywords.py --parquet data/spark-output/clean --output data/analysis-output/keyword_analysis_spark.json
# Insight
python analysis/single/analyze_insights.py --input data/processed/outputnew --output data/analysis-output/insights.json
# Benchmark
python benchmark/benchmark_pmi.py ; python benchmark/benchmark_apples_to_apples.py
# Phân tích LLM (chạy từ thư mục script, cần khóa API Groq)
python analyze_education_async.py ./cleaned_data_input ./analyzed_dataa
python analyze_comments.py ./input_clean_data ./analyzed_data
```

Khóa API: mỗi script giữ danh sách `API_KEYS` ngay trong file (`tienxuly_vietlaiorder.py`, `analyze_comments.py`), để trống trong repo; `analyze_comments.py` dừng với thông báo nếu danh sách rỗng (`analyze_comments.py:645`). Cách quản lý khóa: loại 12.

## 6. Chỗ lệch giữa code, docstring và thực tế

Code là source of truth. Các điểm sau cần biết khi chạy lại pipeline:

| # | Vấn đề | Bằng chứng |
|---|---|---|
| 1 | **Ba script Spark import từ `data.spark...` nhưng thư mục này không còn** (đã dời sang `preprocessing/spark/`, `analysis/spark/`). Chạy trực tiếp sẽ lỗi `ModuleNotFoundError`. Chỉ `verify_preprocessing.py` và `benchmark/*.py` đã dùng đường dẫn mới | `pyspark_preprocessing.py:31-32`, `pyspark_pmi_keywords.py:35-36`, `verify_pmi_keywords.py:41` |
| 2 | Docstring Spark vẫn ghi đường dẫn cũ (`data/spark/clean`, `data/process_education/...`) | đầu `pyspark_preprocessing.py`, `pyspark_pmi_keywords.py` |
| 3 | `Analyze keywords.py` đọc `education_comments.json` / `showbiz_comments.json` **cùng thư mục với script** (`analysis/single/`), nhưng thư mục này không có hai file đó; `aggregate_comments_v2.py` ghi ra `data/` | `Analyze keywords.py:310-313`; `ls analysis/single` |
| 4 | `aggregate_comments_v2.py` viết cứng `D:\py\git\NCKH_hong_drama\data\process_education\...`; thực tế là `data/processed/process_education/...` | `aggregate_comments_v2.py` |
| 5 | `data_sampling_process.md` hướng dẫn chạy `python aggregate_comments_v2.py` ở thư mục gốc, file nằm ở `sampling_labeling/` | `ls sampling_labeling` |
| 6 | Báo cáo mô tả gán nhãn bằng Gemini; code hiện tại gọi **Groq `llama-3.3-70b-versatile`** cho cả hai lĩnh vực. Gemini chỉ còn ở bước lọc rác (`tienxuly_vietlaiorder.py`) và ở n8n | `analyze_comments.py:40`, `analyze_education_async.py:46` |
| 7 | `merge_data.py`, `normalize_*.py` mà báo cáo gọi tên nằm trong `data/archive/luu_tru/`, không nằm trong luồng chính | `git ls-files` |
| 8 | Showbiz không có thư mục `cleaned_data_input`: dữ liệu showbiz vào bước 3b từ `input_clean_data`. Chưa rõ showbiz có đi qua bước 2 hay không | `ls data/processed/process_showbiz` |

## 7. Câu hỏi mở

1. Bước 2 có chạy cho Showbiz không (xem lệch #8)?
2. Hai file `education_comments.json`, `showbiz_comments.json` dùng cho PMI đang nằm ở đâu khi chạy bước 7 gần nhất?
3. Phase 01 PySpark ghi `done` nhưng 3 script còn import `data.spark`: bạn muốn ghi nhận đây là hiện trạng hỏng đến khi làm lại?
