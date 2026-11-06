# Database và dữ liệu

Document loại 3/16 (xem `docs/doc-map.md`). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa; mục Supabase còn thiếu schema.**

Phạm vi: chỉ mô tả các kho dữ liệu đang có. Neo4j, bảng `jobs`, schema chuẩn đa nền tảng và các hạng mục làm sau nằm ở bảng "Việc làm sau" trong `doc-map.md`, chưa viết vào đây.
Luồng sinh ra từng file: loại 2. API đọc dữ liệu: loại 9, 10.

---

## 1. Các kho dữ liệu

| # | Kho | Công nghệ | Vị trí | Ai ghi | Ai đọc |
|---|---|---|---|---|---|
| A | File JSON thô và đã xử lý | JSON | `data/raw/`, `data/processed/`, `data/analysis-output/` | n8n, các script `analysis/`, `preprocessing/` | Script, dashboard (qua GitHub raw), `build_db.py` |
| B | Parquet (nhánh Spark) | Parquet (snappy) | `data/spark-output/clean/` | `pyspark_preprocessing.py` | `pyspark_pmi_keywords.py`, benchmark |
| C | SQLite `events.db` | SQLite | `serving/web_v2/backend/events.db` | `build_db.py` | FastAPI `app.py` |
| D | Vector DB | Supabase (PostgreSQL + pgvector) | Supabase (ngoài repo) | n8n | Retrieval Agent trong n8n |
| E | Đồ thị thảo luận (cho GNN) | pickle + numpy + parquet | `data/gnn/` | `ml/gnn/*` | `ml/gnn/*` |
| F | Google Sheets | Google Sheets + Apps Script | Google Drive (ngoài repo) | Nhóm, n8n | n8n, `build_db.py` (qua Apps Script) |
| G | Lịch sử hội thoại | JSON | `history.json` (gốc repo) | Chatbot / n8n | Dashboard (tab Interaction) |

Quy mô hiện tại (`insights.json`): 85 sự kiện (40 Giáo dục, 45 Showbiz), 668 liên kết (446 web, 222 Facebook); 36.078 bình luận thô, 29.622 sạch, 6.456 rác (17,9%). Chỉ **50 sự kiện đã phân tích** (20 Giáo dục + 30 Showbiz).

## 2. Kho A: file JSON

Khóa chung: **`id_content`** dạng `education_NNN` / `showbiz_NNN`, nối mọi file với nhau.

### 2.1 Dữ liệu sự kiện (báo chí)

**`data/raw/data_web.json`**: object có hai khóa `showbiz` (45 sự kiện) và `giáo dục` (40).

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id_content` | str | Mã sự kiện |
| `ten_su_kien` | str | Tên sự kiện; cũng là từ khóa tìm kiếm khi thu thập |
| `danh_muc` | str | Nhóm (chủ yếu "Giải trí" / "Giáo dục"; vài giá trị khác như "Pháp luật", "Xã hội", "Thời sự") |
| `content` | str | Nội dung do LLM tổng hợp từ nhiều bài báo. Có dòng bị lồng JSON hoặc lỗi cú pháp (xem `content_extractor.py`) |
| `actor_related` | list\|null | Danh sách `{name, role}` nhân vật liên quan (NER). Giáo dục: 16/40 sự kiện là `null` |
| `time_event` | str | Thời điểm sự kiện (LLM lấy mốc sớm nhất trong các bài) |
| `parse_error` | str | Chỉ có ở một số sự kiện Giáo dục (4 dòng); LLM trả JSON lỗi |

**`data/raw/data_Sukien.json`**: danh sách tên sự kiện (`ten_su_kien`, Showbiz thêm `actor_related`); danh sách gốc để tra cứu khớp sự kiện (Dispatcher n8n).

### 2.2 Bình luận (cây thảo luận)

**`cleaned_data_input/*.json`, `input_clean_data/*.json`**: mỗi file một sự kiện.

| Trường | Ý nghĩa |
|---|---|
| `id_content`, `event_name`, `sort_mode`, `post_content` | Sự kiện và bài đăng gốc |
| `comments[]` | Bình luận gốc: `comment_id` (`cmt_{id_content}_{NNNN}`), `order`, `text`, `likes`, `reply_count`, `replies[]` |
| `replies[]` | `comment_id`, `order`, `reply_to_id` (khóa ngoại tới bình luận cha), `text`, `likes` |

Cây chỉ có **hai cấp** (gốc và reply). `reply_to_id` là chìa khóa dựng đồ thị thảo luận (kho E).

**`analyzed_data*/full/*.json`**: cây trên thêm trường phân tích.

| Lĩnh vực | Trường thêm vào mỗi bình luận |
|---|---|
| Giáo dục | `is_trash` (bool), `stance` (tích cực / tiêu cực / trung lập / ý kiến riêng), `thread_stats {total, stances, controversial}` |
| Showbiz | `is_trash`, `emotion` (Phẫn nộ / Cà khịa / Đồng cảm / Ủng hộ / Trung lập), `toxic`, `toxic_type`, `thread_stats {total, emotions, toxic_count, controversial}` |

**`analyzed_data*/summary/*.json`**: thống kê một sự kiện.
- Giáo dục: `comment_counts {total, tích_cực, tiêu_cực, trung_lập, ý_kiến_riêng, rác}`, `analysis{<stance>: {count, percent, summary, examples}}`, `conclusion {focus, trend}`.
- Showbiz: `total_comments`, `emotion_stats`, `toxic_stats {total_toxic, chửi bới, công kích cá nhân, công kích người thân}`, `top_comments {most_popular, by_emotion, notable_opinions}`, `controversial_threads[]`.

**`run_log.jsonl`** (trong `analyzed_dataa/`, `analyzed_data/`): mỗi dòng một phiên chạy LLM (`session_id`, thời gian, số file xong / còn lại, `stop_reason`).

### 2.3 Dữ liệu đã gộp và tổng hợp

| File | Cấu trúc |
|---|---|
| `data/processed/outputnew/{education,showbiz}/*.json` | `id_content, ten_su_kien, content, actor_related, time_event, analyzed{...}` (nội dung `analyzed` giống `summary/`). 40 + 45 file; sự kiện chưa phân tích thì không có số liệu |
| `data/analysis-output/insights.json` | `overall {total_events, total_events_with_analysis, total_events_without_analysis, total_links, total_links_website, total_links_facebook, total_comments{raw,clean,trash,trash_rate}, by_category}`; `education {category, total_events, events_with_analysis, comment_stats, stance_distribution, top_events_by_comments[], events_by_year}`; `showbiz {…, emotion_distribution, toxic_stats, top_events_by_comments[], events_by_year}`. Mỗi phần tử `top_events_by_comments`: `id_content, ten_su_kien, time_event, total, clean, trash` |
| `data/analysis-output/keyword_analysis_v4.json` | `{EDUCATION: [...], SHOWBIZ: [...]}`; mỗi phần tử: `keyword, ngram_type, total_frequency, total_articles, pmi_score, score, details{id_content: tần suất}` |
| `data/test-sets/*.json` | Tập mẫu bình luận cho đánh giá (loại 5, 8) |

## 3. Kho B: Parquet

`data/spark-output/clean/` (8 part snappy): mỗi dòng một bình luận **đã lọc rác**, phẳng.
Cột: `id_content, event_name, comment_id, parent_comment_id, order, text, likes, depth` (`depth` 0 = bình luận gốc, 1 = reply). Nguồn: `preprocessing/spark/pyspark_preprocessing.py:98-149`.

## 4. Kho C: SQLite `events.db`

Dựng lại hoàn toàn mỗi lần chạy `build_db.py` (có `DROP TABLE` rồi tạo mới). Hiện có **85 sự kiện, 189 nhân vật**.

### 4.1 Bảng `events` (khóa chính `id_content`)

| Cột | Kiểu | Nguồn | Ghi chú |
|---|---|---|---|
| `id_content` | TEXT PK | `data_web.json` | |
| `ten_su_kien` | TEXT NOT NULL | `data_web.json` | |
| `danh_muc` | TEXT | khóa `showbiz`→"Giải trí", `giáo dục`→"Giáo dục" | Không dùng `danh_muc` gốc của từng dòng. 40 / 45 dòng |
| `platform` | TEXT | cố định `"news"` | Hiện **85/85 dòng đều là `news`** |
| `content_full` | TEXT | `content` đã bóc JSON lồng (`extract_clean_content`) | |
| `excerpt` | TEXT | cắt từ `content_full` (`make_excerpt`) | |
| `time_event` | TEXT | `data_web.json` | |
| `links` | TEXT (JSON array) | Apps Script, theo `id_content` | 83/85 dòng có link; lỗi gọi API thì rỗng `[]` |
| `status` | TEXT | Apps Script | Giá trị thật: `Done` (44), `done` (33), `pending` (2), rỗng (6). Có lẫn hoa/thường |
| `image_url` | TEXT | `og:image` của link đầu tiên (ưu tiên link web, link Facebook sau cùng) | 40/85 dòng có ảnh |
| `total_comments`, `clean_comments`, `trash_comments` | INTEGER | `insights.json` → `top_events_by_comments` | Chỉ những sự kiện nằm trong top mới có số; còn lại = 0 |
| `hot_rank` | INTEGER | thứ hạng trong top của lĩnh vực | NULL nếu ngoài top |
| `is_hot` | INTEGER | 1 nếu có `hot_rank` | 19 dòng |

Chỉ mục: `idx_events_cat(danh_muc)`, `idx_events_hot(total_comments DESC)`.

### 4.2 Bảng `actors`

| Cột | Ghi chú |
|---|---|
| `id_content` | FK → `events.id_content` (khai báo; SQLite không bật ràng buộc mặc định) |
| `name`, `role` | Từ `actor_related`; chỉ lấy phần tử có `name` |

Quan hệ: `events 1 — n actors`. Không có khóa chính hay chỉ mục trên `actors`.

### 4.3 Dùng bởi

5 endpoint FastAPI (`app.py`): `/api/events`, `/api/hot`, `/api/event/{id}`, `/api/categories`, `/api/stats`. Không có bảng nào lưu bình luận hay cảm xúc.

## 5. Kho D: Supabase (vector)

**Chưa có thông tin schema** — repo không chứa file DDL, migration hay ảnh chụp bảng; user sẽ cung cấp khi làm đến mục này. Những gì báo cáo nghiệm thu nêu (chưa đối chiếu với Supabase thật):

- Hai luồng dữ liệu riêng cho `education` và `showbiz`; mô tả "Rows trong Supabase: 40 cột (education) và 45 cột (showbiz)" (báo cáo chương 2.2, dòng 668 của bản trích) — nhiều khả năng ý là 40 và 45 **dòng** theo số sự kiện, cần xác nhận.
- Embedding 3072 chiều từ Gemini embedding; truy vấn là cosine similarity, lấy top-10 chunk rồi rerank (Cohere).
- Nguồn nạp: JSON trên GitHub → node Code chuyển thành chuỗi → Supabase Vector Store (n8n) → chunking → embedding.
- Hình 2.30 trong báo cáo `.docx` minh họa bảng.

Cần user cung cấp: danh sách bảng, cột, kiểu, hàm tìm kiếm (ví dụ `match_documents`), quy ước đặt tên, cột chưa dùng. ERD sẽ vẽ ở đây khi có.

## 6. Kho E: đồ thị thảo luận cho GNN

`ml/gnn/build_discussion_graph.py` dựng **một đồ thị cho mỗi sự kiện** từ `analyzed_data*/full`:
- Nút = bình luận không rác và có nhãn hợp lệ (Giáo dục: `stance`; Showbiz: `emotion`).
- Cạnh có hướng `con → cha` theo `reply_to_id` (chỉ nối khi cả hai nút còn trong đồ thị).

| File (`data/gnn/`) | Nội dung |
|---|---|
| `graphs_{domain}.pkl` | `list[dict]`, mỗi phần tử: `event_id, node_ids, texts, labels, edges [(src,dst)], structural{depth, in_degree, sibling_count}, n_nodes, n_edges` (education: 20 đồ thị) |
| `nodes_meta_{domain}.parquet` | Bảng phẳng để gỡ lỗi (nhãn, độ sâu, bậc vào…) |
| `tfidf_{domain}.npz`, `tfidf_vocab_*.json`, `tfidf_node_ids_*.json` | TF-IDF 300 chiều |
| `metrics_{domain}.json` | `n_classes, label_names, n_train/val/test, test_f1_macro, confusion_matrix, classification_report`… |
| `eval_gnn_vs_llm_{domain}.json`, `eval_summary.md` | So GNN với nhãn LLM |

Đặc trưng nút khi huấn luyện: PhoBERT 768 + TF-IDF 300 + cấu trúc 3 = 1071 chiều (`concat_node_features.py`, đầu ra `node_features_{domain}.npy`). Các file `.npy` này không nằm trực tiếp trong `data/gnn/` hiện tại; đã tìm thấy tại `data/gnn-result/content/drive/MyDrive/NCKH/NCKH_hong_drama/data/gnn/` (đối chiếu local 2026-10-29).
Kết quả hiện có (`metrics_*.json`): Giáo dục test F1-macro 0,524 (train/val/test = 3759/805/806 nút); Showbiz 0,217 (14280/3060/3060). Phân tích: loại 6, 8.

## 7. Kho F: Google Sheets / Apps Script

Theo báo cáo nghiệm thu (chưa kiểm tra trực tiếp trên Google):
- Tệp "Drama 2025-Đầu 2026" có sheet **Web** và sheet **Facebook**; cột gồm `id_content`, tên sự kiện, `Links` (nhiều link phân cách bằng dấu phẩy), danh mục, thể loại, `Status` (`pending` → `done`).
- n8n chỉ xử lý dòng `pending`; cập nhật thành `done` sau khi lưu (đảm bảo lũy đẳng).
- Apps Script trả JSON `{posts: [{id, links[], status}]}`; `build_db.py` đọc để điền `links`, `status`. URL Apps Script viết cứng trong `build_db.py:41-44`.
- Báo cáo còn nêu ghi câu hỏi thiếu dữ liệu vào Google Sheets (vòng phản hồi dữ liệu); sheet đó chưa có thông tin cấu trúc.
- `sampling_labeling/map_id_content.py` ghi `id_content` vào sheet bằng service account.

## 8. Kho G: lịch sử hội thoại

- `history.json`: danh sách bản ghi (hiện 34): `user_id, question, answer, source_type, the_loai, su_kien, timestamp`. `source_type` hiện đều là `database`; `the_loai` gồm `education` (13), `showbiz` (5), `none` (6), rỗng (10).
- `QA.json`: danh sách rỗng.
- Dashboard đọc `history.json` qua GitHub raw và `/api.txt` (tab Interaction).

## 9. Quy ước đặt tên

- Mã sự kiện: `education_NNN`, `showbiz_NNN`; mã bình luận: `cmt_{id_content}_{NNNN}` do `tienxuly_vietlaiorder.py` gán.
- Khóa JSON dùng tiếng Việt không dấu (`ten_su_kien`, `danh_muc`, `actor_related` lẫn Anh–Việt); nhãn giữ tiếng Việt có dấu.
- Hai lĩnh vực có schema phân tích **khác nhau** (stance 4 lớp và emotion 5 lớp kèm toxic), nên các script thường rẽ nhánh theo lĩnh vực.
- Thư mục: Giáo dục `analyzed_dataa` (hai chữ `a`), Showbiz `analyzed_data`.

## 10. Chỗ lệch và bất thường

| # | Vấn đề | Bằng chứng |
|---|---|---|
| 1 | `platform` luôn là `news`: trang Facebook và trang tin tức trên web hiện cùng hiển thị toàn bộ 85 sự kiện (hàm `getPaginatedPosts` bỏ qua tham số `platform`) | `build_db.py` (`"news"`); `api.js` (`getPaginatedPosts`) |
| 2 | `status` lẫn `Done` / `done` | Truy vấn `events.db` |
| 3 | Cột `image_url` NULL ở 45/85 sự kiện | Truy vấn `events.db` |
| 4 | `total_comments` bằng 0 với sự kiện ngoài top, dù sự kiện có bình luận | `build_db.py:build_hot_lookup` |
| 5 | Dashboard đọc `main/data/insights.json` trên GitHub; trong repo file nằm ở `data/analysis-output/insights.json` | `App.tsx:17` |
| 6 | Báo cáo ghi 32.076 bình luận thô và 2.454 rác ở phần tổng kết, nhưng `insights.json` ghi 36.078 và 6.456 (trùng Hình 3.12 trong báo cáo) | `drama-intelligence-du-an.md`; `insights.json` |
| 7 | Báo cáo mô tả mọi dữ liệu web nằm trên Google Sheets/Apps Script; thực tế web đọc `events.db` | `app.py` |

## 11. Bảng / cột chưa dùng

- `events.content_full`, `events.excerpt` hiện chỉ phục vụ hiển thị; `actors.role` chưa thấy dùng trong `app.py` ngoài trả về chi tiết sự kiện (cần xác nhận).
- `data/archive/`, `data/raw/education.json`, `showbiz.json`, `total_comments.json`: chưa xác định đang được script nào dùng.

## 12. Câu hỏi mở

1. Schema Supabase (user sẽ đưa khi làm mục 5).
2. "40 cột / 45 cột" trong báo cáo là cột hay dòng?
3. `data/raw/education.json`, `showbiz.json`, `total_comments.json` và `data/archive/workspace` còn dùng không?
4. Đã xác định file `node_features_{domain}.npy` và `phobert_{domain}.npy` tại cây `data/gnn-result/` nêu ở mục 6; chưa xác minh đây có phải bộ artifact mới nhất hay không.
5. Sheet "câu hỏi thiếu dữ liệu" tên gì, cột nào?
