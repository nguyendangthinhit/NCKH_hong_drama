# Hướng dẫn đọc code từng thư mục

Cập nhật: 2026-11-19. **Bản nháp chờ user đọc và sửa.** Yêu cầu của user (2026-10-31): biết thư mục nào làm việc gì nhưng chưa nắm code bên trong chạy ra sao.

Mỗi mục trả lời 4 câu: **điểm vào** (chạy cái gì), **thứ tự gọi**, **vào → ra**, **lưu ý**. Nguồn: đọc code ngày 2026-11-19 (docstring, tên hàm, đoạn `main`); không chạy script nào để kiểm. Bức tranh tổng: `docs/kien-truc-tong-the.md`; đường dẫn dữ liệu chi tiết: `docs/data-pipeline.md`.

Thứ tự theo luồng dữ liệu: 1 Thu thập → 2 Tiền xử lý → 3 Phân tích → 4 Lấy mẫu/gán nhãn → 5 ML → 6 Benchmark → 7 Phục vụ (API, web, dashboard, chat agent).

---

## 1. Thu thập

### `FB_Crawl_skills/` (crawler Facebook đang dùng)
- **Điểm vào:** `python scripts/fb_cli.py crawl deep <url> --target N`.
- **Thứ tự gọi:** `fb_cli.py` (argparse, nhiều lệnh con: `open`, `status`, `navigate`, `crawl`, `clean`, `export`, `bulk`, `schedule`, `audit`, `list`) → `cmd_crawl` chạy `scripts/05_auto_scrape_cdp.py` → nối vào Chrome đang mở qua CDP cổng 9222 (profile đã đăng nhập tài khoản test) → mở URL bài, cuộn để tải comment, lấy comment bằng JavaScript qua CDP, gom tích lũy mỗi vòng cuộn (Facebook ảo hóa DOM) → ghi JSON thô + `post.json` + run manifest/checkpoint (`_run_manifest.py`).
- **Lệnh khác:** `clean` (thô → `clean.jsonl` + quarantine + stats), `export` (CSV/JSON/Parquet), `bulk` (danh sách URL), `schedule` (YAML). `06`–`09_*.py` cào group/nhiều bài/timeline/profile, `_browser.py`/`_stealth.py` quản lý Chrome.
- **Vào → ra:** URL bài (+ `--event-id`) → `data/posts/` (comment có reply, `post.json`, `common.jsonl` theo schema chung; chuyển đổi ở `_common_schema.py`, xem `thu-thap-du-lieu.md` mục 6b).
- **Lưu ý:** Facebook chỉ trả khoảng 50 comment cho tài khoản test; script chưa có test tự động; dữ liệu **chưa** nối sang `data/raw/` hay `preprocessing/`.

### `ingestion/n8n/cào data.json`
- Không phải code Python: bản export workflow n8n (SerpApi tìm URL, Firecrawl cào báo, Gemini tổng hợp, Apify cào comment FB, ghi JSON lên Google Drive, đổi trạng thái `pending → done` trong Google Sheets). Chạy trên n8n cloud, không chạy từ repo. Chi tiết: `docs/thu-thap-du-lieu.md`.

---

## 2. Tiền xử lý

### `preprocessing/single/tienxuly_vietlaiorder.py` (bản gọi LLM)
- **Điểm vào:** chạy thẳng file (không có `main()`, không có tham số). Cuối file gọi `process_directory("input_clean_data", "cleaned_data_input")`, hai thư mục **tương đối với thư mục đang đứng**.
- **Thứ tự gọi:** `process_directory` duyệt từng `*.json` (bỏ qua file đã có ở đích) → `check_noise_batch(texts)` hỏi Gemini theo lô xem comment nào là rác (xoay `APIKeyManager`; lỗi lạ thì coi là không rác để khỏi mất dữ liệu) → giữ comment không rác, đánh lại `order` từ 1 và `comment_id = cmt_<id_content>_<0001>` → ghi file sạch.
- **Vào → ra:** JSON sự kiện (có `comments`) → JSON cùng tên, bỏ rác, `order`/`comment_id` mới.

### `preprocessing/spark/` (bản luật + PySpark)
- **Điểm vào:** `pyspark_preprocessing.py` (`main` → `run`).
- **Thứ tự gọi:** `get_spark()` (`spark_session_factory.py`: đặt JAVA_HOME, Python, Hadoop) → `read_posts` đọc JSON sự kiện → `flatten_comments` làm phẳng cây (gốc + reply) thành DataFrame → `filter_trash` gọi `is_trash` (`is_trash_rule.py`: quá ngắn, chỉ emoji, chỉ tag tên, ký tự lặp… không dùng LLM) → ghi Parquet.
- **Vào → ra:** `data/processed/process_education/cleaned_data_input/`, `data/processed/process_showbiz/input_clean_data/` → `data/spark-output/clean/`.
- **Phụ:** `verify_preprocessing.py` so tập `comment_id` giữ lại với baseline Python; `text_tokenizer.py` bọc `underthesea` cho PMI.
- **Lưu ý:** bản Spark thay LLM bằng luật (bản đối chiếu của `verify_preprocessing.py` cũng là luật, không phải bản Gemini); chạy 2026-11-18: 33.379 thô → 31.757 sạch.

---

## 3. Phân tích

### `analysis_new/` (hướng mới: LLM đọc cả cụm, giữ cấp bậc)
- **Điểm vào:** `python -m analysis_new.single.run_analysis_single <input> <output_dir> [--domain ...] [--yes] [--max-requests N]` (đơn luồng) hoặc `analysis_new/spark/run_analysis_spark.py` (PySpark, cùng luồng). Mặc định chỉ **ước tính số request và ghi prompt mẫu** (`_dry_run/`); thêm `--yes` mới gọi API.
- **Thứ tự gọi (dùng chung qua `event_pipeline.py`):**
  1. `thread_loader.load_event` đọc định dạng B (phẳng, `parent_id`), `build_clusters` gom bình luận cấp 1 + toàn bộ reply thành cụm.
  2. `trash_rule.is_trash_rule` đánh dấu rác (rác vẫn hiện trong cụm làm ngữ cảnh nhưng không gán nhãn; cụm toàn rác không gọi LLM).
  3. `prepare_event` → `request_planner.plan_requests` gom cụm vào request (tối đa 60 comment/request) → `prompts.build_label_prompt` (mã cục bộ `K<cụm>.<số>`, thụt lề theo cấp).
  4. `label_batch` gọi `MmoClient` (`mmo_client.py`, API mmodiary kiểu Responses, đọc SSE, model xoay "dùng tới khi lỗi", key đổi khi hết số dư) → `parse_label_response` (có `salvage_groups` vớt nhãn khi JSON hỏng). Quá 50% nhãn hỏng → `BadLabelResponse`: sự kiện không ghi file, response lưu `_bad_responses/`.
  5. `finalize_event`: gộp nhãn, (Giáo dục) thêm 1 request tổng hợp sự kiện, `result_builder.build_full/build_summary`; `write_outputs`.
- **Vào → ra:** JSON sự kiện định dạng B (vd. `data/sample/showbiz_068 (1).json`) → `<output>/full/<id>.json` (từng comment có nhãn) + `<output>/summary/<id>.json` (khóa giống bản cũ để `analyze_insights.py` đọc được) + `run_log.jsonl`.
- **Lưu ý:** key và model đọc từ `.env.local` dòng 4 và `model_list.txt`; chạy lại sự kiện đã có file thì bỏ qua (`is_done`). Đã chạy thật 1 sự kiện; console Windows cần `PYTHONUTF8=1`.

### `analysis/single/` (bản cũ, làm phẳng comment)
- **`analyze_education_async.py <input> <output>`** (Giáo dục) → `run` → `analyze_file`: `run_step1` (Groq, `build_prompt_step1`) gán stance từng lô, `run_step2` (`build_prompt_step2`) xử lý lại các comment ứng viên → `build_full_analyzed`, `build_summary`. Có `AccountManager` xoay key, `RunLogger`.
- **`analyze_comments.py <input> <output>`** (Showbiz): gọi Groq theo lô (`analyze_batch_async`) để gán `emotion` + `toxic` → full + summary. Hai file lặp một phần code (`is_trash_rule`, `KeyPool`…) — đã chép sang `analysis_new/trash_rule.py`.
- **`merge_final_data.py --web --edu_sum --show_sum --output`:** gộp `data_web.json` với summary theo `id_content`.
- **`analyze_insights.py --input ./output --output insights.json`:** đọc dữ liệu đã gộp (`education/`, `showbiz/`) → `analyze_education`/`analyze_showbiz`/`analyze_overall` → `insights.json`.
- **`Analyze keywords.py`:** PMI + n-gram (bản chuẩn để Spark đối chiếu). `main` đọc `education_comments.json`/`showbiz_comments.json` **cạnh file script**, tính `compute_pmi_scores`, xếp theo `freq × log2(1+PMI)` → `keyword_analysis_v4.json`.

### `analysis/spark/`
- **`pyspark_pmi_keywords.py`:** Parquet sạch → `add_tokens` (UDF tokenize) → `unigram_counts`/`ngram_counts` → `compute_bigram_pmi`/`compute_trigram_pmi` → `weighted_score` → `top_keywords` → JSON. **`verify_pmi_keywords.py`:** chạy baseline và so (Jaccard, top-5). Kết quả 2026-11-18: PASS.

---

## 4. Lấy mẫu và gán nhãn

### `sampling_labeling/`
Các script rời, chạy tay, đường dẫn viết cứng (nhiều chỗ lệch cấu trúc hiện tại).
- `aggregate_comments_v2.py`: gộp comment từ các thư mục `full` → file tổng. `count_comments.py`, `count_nontrash_comments.py`: đếm theo `id_content`.
- `sample_comments.py`: lấy mẫu phân tầng theo nhãn (`--seed`). `export_5k_for_verification.py`: `load_all` → `sample_showbiz`/`sample_education` (lấy hết lớp hiếm + bổ sung + rác) → xuất xlsx 5.000 dòng/lĩnh vực (seed 42) cho người điền `verified_label`.
- `map_id_content.py`: ghép `id_content` với sheet Google. Hướng dẫn gán nhãn cũ: `data_labels/labeling-guide.md`.
- **Dữ liệu đầu ra đang dùng** nằm ở `labeling data/verify_{education,showbiz}_5k_dedup.xlsx` (có cột `label`, `is_synthetic`), mô tả ở `docs/gan-nhan-va-tap-du-lieu.md`.

---

## 5. ML

### `ml/phobert/` (fine-tune PhoBERT; chưa chạy thật)
- **Điểm vào:** `phobert_finetune_colab.py --domain {showbiz,education} --data_path <xlsx|csv> [--eval_file ...] [--smoke]` (chạy Colab/GPU).
- **Thứ tự gọi:** `phobert_config.py` (nhãn từng lĩnh vực, tên cột, siêu tham số) → `phobert_data.prepare_dataframe` (nhãn cuối: cột `label` > `verified_label` > `is_trash` > nhãn LLM) → `split_data`/`_event_split` (chia **theo sự kiện**, thử 300 hoán vị chọn phân bố nhãn gần nhất) → `phobert_segmenter` (underthesea) → `CommentDataset` → `PhoBERTClassifier` (`phobert_model.py`) → `phobert_train.fit` (AMP, early stopping theo val F1-macro) → `test_report` → lưu checkpoint + `config.json`.
- **Suy luận:** `phobert-batch-inference.py` đọc `config.json` của checkpoint để dùng đúng segmenter/độ dài.
- **Làm giàu dữ liệu:** `augment_minority_labels.py` sinh bình luận nhãn thiểu số bằng Gemini (key từ `api.txt`).
- **Dòng sinh:** dòng `is_synthetic=True` chỉ vào train (chia trên dòng thật trước); `--no_synthetic` bỏ hẳn.

### `ml/gnn/` (GraphSAGE; tạm hoãn)
- **Thứ tự chạy tay:** `build_discussion_graph.py` (mỗi sự kiện một đồ thị; nút = comment không rác có nhãn, cạnh = `reply_to_id`) → đặc trưng: `extract_phobert_features.py` hoặc `extract_api_embeddings.py` (+ `embedding_api_client.py`, cache SQLite) và `extract_tfidf_features.py` → `concat_node_features.py` (1.071 chiều) → `train_gnn_node_classification.py --domain ... [--split event] [--model sage|mlp]` → checkpoint, `predictions_*.json`, `metrics_*.json` → `evaluate_gnn_vs_llm.py`.
- `model_graphsage_classifier.py`: SAGE (PyG hoặc thuần torch) và MLP baseline. `graph_db/load_graph_to_neo4j.py`: nạp đồ thị vào Neo4j (idempotent).
- **Lưu ý:** hoãn theo `DECISIONS.md` 2026-11-12/16; dữ liệu gán nhãn hiện không có cấu trúc reply.

---

## 6. Benchmark

### `benchmark/`
- `benchmark_apples_to_apples.py`: cùng input, đo `benchmark_python_single` vs `benchmark_spark` → `benchmark_apples.json`.
- `benchmark_pmi.py`: Spark ở nhiều mức `local[N]` so Python, dữ liệu x1/x3 → `benchmark_results.json`. Cả hai nạp baseline qua `load_baseline_module` rồi dùng `get_spark()`.

---

## 7. Phục vụ

### `serving/web_v2/backend/` (API sự kiện)
- **Dựng DB:** `build_db.py` (xóa và tạo lại bảng `events`, `actors`): `load_json(data_web.json)` + `insights.json` (`build_hot_lookup` xếp hạng hot) + `fetch_links_by_id` (Apps Script: `links`, `status`) → `content_extractor.extract_clean_content`, `platforms.resolve_platform`, `og_image_scraper.fetch_og_images_batch` → `events.db`. `repair-platforms.py` sửa `platform` cũ (mặc định xem trước, `--apply` mới ghi, có sao lưu).
- **Chạy API:** `app.py` (FastAPI): `get_conn` mở `events.db` → `/api/events` (lọc category/q, phân trang), `/api/hot`, `/api/event/{id}`, `/api/categories`, `/api/stats`.

### `serving/web_v2/frontend/` (website)
- `main.jsx` → `App.jsx` (routes `/`, `/news`, `/facebook`, `/events`, `/events/:id`, `/chat`; bọc `ChatHistoryProvider`) → `pages/*` → `services/api.js` (gọi FastAPI qua `VITE_API_BASE`, ánh xạ sang thẻ bài), `chat-api.js` (gọi agent qua `VITE_CHAT_API_URL`), `event-analysis-api.js`, `latest-events-api.js`.
- Chat: icon nổi `components/Chatbot` chuyển sang `/chat`; `ChatHistoryContext` giữ lịch sử trong RAM (mất khi tải lại trang); mỗi cuộc trò chuyện gửi `userId = <cookie>:<conversationId>`.

### `serving/dashboard/` (dashboard)
- `main.tsx` → `App.tsx` (state tab, theme, dữ liệu; tải insight mỗi 30 giây, fallback `constants.tsx`) → `components/views/{Overview,Sentiment,Interaction,System}View.tsx`. `InteractionView` tải history từ GitHub và gọi Gemini trực tiếp từ trình duyệt (khóa từ `/api.txt`).

### `serving/chat_agent/` (Python) và `serving/chat_agent_worker/` (Cloudflare Worker)
Hai bản cùng luồng (Worker là bản port, 129/129 câu khớp Python khi kiểm).
- **Điểm vào:** `app.py` (`uvicorn app:app --port 8010`, `POST /chat`, `GET /health`) hoặc `src/index.ts` (Worker; kiểm Origin/`X-Agent-Key`, giới hạn body 8 KB).
- **Thứ tự gọi (`chat_pipeline._route`):** (1) `intent_rules`: spam / chào / hỏi thông tin → trả câu cố định; (2) `event_store.match` khớp câu hỏi với sự kiện trong RAM (điểm từ vựng trọng số IDF, `text_normalizer` bỏ dấu/tách từ); (3) câu hỏi top/thống kê mà không khớp mạnh sự kiện → `insight_context` cắt lát `insights.json`; (4) câu nối tiếp ("vụ đó") → dùng sự kiện đang bàn trong `session_memory`; (5) không khớp → hỏi lại hoặc báo ngoài phạm vi; (6) có ngữ cảnh → **một** lần `llm_client.generate` (Groq, dự phòng Gemini, tự đổi key) với `answer_prompt`. Ghi thời gian từng bước.
- **Vào → ra:** `{user_id, message, source}` → `{reply, intent, event_ids, timings_ms}`.
- **Dữ liệu:** `data/raw/*.json` + `insights.json` (Worker nhúng sẵn qua `scripts/build_agent_data.py`); phiên lưu RAM (Python) hoặc Durable Object (Worker).
- **Messenger:** không nằm trong repo code; workflow n8n gọi Worker kèm `X-Agent-Key`.

---

## 8. Chưa kiểm chứng / lưu ý chung
- Mô tả trên từ đọc code, **chưa chạy lại** từng script. Chỗ nào ghi "đường dẫn viết cứng" cần kiểm lại trước khi chạy.
- Nhiều script phụ thuộc thư mục đang đứng, `.env.local`, `api.txt`, `model_list.txt` (xem `ISSUES.md`).
- Chưa có manifest Python chung ở gốc repo; Spark cần JDK 17 + `.venv-ml`.
