# Post Analyzer — phân tích 1 bài viết qua link (GĐ6)

Website độc lập: dán link bài Facebook → chọn số comment → hệ thống tự cào (tài khoản phụ) → phân tích LLM theo cụm → dashboard riêng của bài. Không liên quan dashboard chung (`serving/dashboard`) hay web_v2.

Code: `serving/post_analyzer/` (backend FastAPI + frontend Vite React). Plan: `plans/261123-1749-gd6-post-link-analyzer/plan.md`.

## 1. Luồng xử lý

```
Web (5180) ─POST /api/jobs─► FastAPI (8020) ─► SQLite jobs (queued)
                                   │ worker 1 thread, lần lượt từng job
                                   ├─ 1. Cào: FB_Crawl_skills/scripts/05_auto_scrape_cdp.py --target N
                                   │        (Chrome CDP cổng 9222, profile tài khoản phụ)
                                   ├─ 2. Chuyển định dạng: common.jsonl → cây reply lồng nhau (event.json)
                                   ├─ 3. LLM đoán lĩnh vực: showbiz | education (1 request)
                                   ├─ 4. Gán nhãn theo cụm: analysis_new (1 request / ~60 comment)
                                   └─ 5. Tổng hợp: full/ + summary/ → result_view → dashboard
Web hỏi GET /api/jobs/{id} mỗi 3s; xong thì GET /api/jobs/{id}/result.
```

| Bước | Module | Dùng lại code |
|---|---|---|
| Cào | `backend/post_crawler.py` | `ingestion/crawl_links_from_sheet.py` (reel→watch, thư mục bài, profile, mở Chrome) |
| Chuyển định dạng | `backend/post_to_event.py` | `ingestion/crawled_posts_to_analysis_events.py` (`build_tree`), `analysis_new/thread_loader.normalize_event` |
| Đoán lĩnh vực | `backend/domain_detector.py` | `analysis_new.request_planner.parse_json_loose`, `MmoClient` |
| Gán nhãn + tổng hợp | `backend/post_analysis_runner.py` | `analysis_new/event_pipeline.py` |
| Dữ liệu dashboard | `backend/result_view.py` | `analysis_new/config.py` (bộ nhãn) |
| Hàng đợi | `backend/job_store.py`, `backend/job_worker.py` | — |

Trạng thái job: `queued → crawling → analyzing → done | failed`. Mỗi lần chỉ 1 job (dùng chung 1 Chrome + tài khoản phụ); chỉ chạy **1 tiến trình** uvicorn (không `--workers`), nhận job bằng UPDATE có điều kiện nên 2 thread không lấy trùng.

Bảo vệ khi cào:
- Khoá `.crawl.lock` trong thư mục bài (chung với script cào sheet): bài đang được cào nơi khác → job báo lỗi, không cào trùng.
- Xoá `checkpoint.json` cũ của bài trước khi cào: job web luôn cào mới, không tiếp tục lần chạy dở.
- Timeout = số vòng × 15s + 5 phút; quá hạn thì dừng crawler, job `failed`.
- Khoá LLM được đọc trước khi cào: thiếu `.env.local` thì báo ngay.

## 2. Chạy

Yêu cầu: Windows có Chrome, `py -3.14` (Python 3.11 trên máy dev bị Application Control chặn `_ssl`), Node 20+, file khoá LLM `.env.local` + `model_list.txt` ở gốc repo (như `analysis_new`).

```powershell
# Backend (chỉ nghe 127.0.0.1 vì API không có đăng nhập)
cd serving/post_analyzer/backend
py -3.14 -m pip install -r requirements.txt   # lần đầu
py -3.14 -m uvicorn app:app --host 127.0.0.1 --port 8020

# Frontend (terminal khác)
cd serving/post_analyzer/frontend
npm install                                    # lần đầu
npm run dev                                    # mở http://127.0.0.1:5180
```

Biến môi trường (tuỳ chọn): `POST_ANALYZER_DATA_DIR` (mặc định `data/post-analyzer/`, gitignored), `POST_ANALYZER_CDP_PORT` (mặc định 9222).

## 3. Đăng nhập tài khoản phụ

Backend dùng profile Chrome `FB_Crawl_skills/sessions/chrome-crawler-profile` (cổng 9222; cổng khác là `chrome-crawler-profile-<port>`), chung với script cào sheet. Chrome chưa mở thì backend tự mở. Profile **chưa từng đăng nhập** thì job báo lỗi; đăng nhập 1 lần bằng tay:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 `
  --user-data-dir="FB_Crawl_skills\sessions\chrome-crawler-profile" https://www.facebook.com/
```

Đăng nhập tài khoản phụ trong cửa sổ đó, giữ cửa sổ mở (không thu nhỏ: FB ngừng tải comment khi tab bị ẩn).

## 4. Số comment và thời gian

Người dùng chọn 50 (gợi ý) / 100 / 200 / 300 / 400 / 500 / Toàn bộ. Crawler `--target N` dừng khi đủ N comment (tính cả reply) và cắt còn N; "Toàn bộ" cuộn tới khi hết (tối đa 1.000 vòng, tự dừng sau 8 vòng không thêm comment).

Ước tính trên web: cào ~6s / 8 comment; LLM ~2–3 phút / request, 1 request / ~60 comment + 1 request đoán lĩnh vực (+1 request tổng hợp với Giáo dục). Số comment lấy được có thể ít hơn số FB hiển thị (FB giới hạn theo tài khoản).

## 5. API

| Method | Đường dẫn | Ghi chú |
|---|---|---|
| GET | `/api/options` | `comment_choices`, `comments_per_request` |
| POST | `/api/jobs` | body `{url, max_comments, force?}`; chỉ nhận link facebook.com / fb.watch (chặn `l.facebook.com`); cùng bài (khoá = tên thư mục bài của crawler, bỏ query kiểu `?mibextid=`) + cùng số comment, job chưa lỗi và còn file kết quả → trả job cũ, `reused: true`, trừ khi `force` |
| GET | `/api/jobs` | 30 job gần nhất |
| GET | `/api/jobs/{id}` | trạng thái, `stage`, `progress_done/total` (request LLM), `queue_position` |
| GET | `/api/jobs/{id}/result` | dữ liệu dashboard; 409 nếu chưa xong |

Kết quả mỗi job: `data/post-analyzer/jobs/<id>/{crawl.log, event.json, full/, summary/, error.log?}`. Server bị tắt giữa chừng → lần khởi động sau job dở chuyển `failed`, gửi lại link để chạy lại.

## 6. Dashboard

Thông tin bài + lĩnh vực (kèm lý do LLM đoán); thẻ số: comment, cấp 1 / reply, cụm, cụm tranh cãi, rác, độc hại (Showbiz); biểu đồ phân bố cảm xúc (Showbiz) / quan điểm (Giáo dục); loại độc hại (Showbiz) hoặc nhận định chung (Giáo dục); comment tiêu biểu theo nhãn; 15 cụm thảo luận lớn nhất kèm tóm tắt LLM.

Crawler không lấy số like → comment tiêu biểu chọn theo độ dài, không theo lượt thích.

## 7. Test

```powershell
cd serving/post_analyzer/backend; py -3.14 -m pytest tests -q   # offline: crawler + LLM giả
cd serving/post_analyzer/frontend; npm run build
```

## 8. Giới hạn bản 1

Chỉ Facebook; chưa có YouTube/TikTok, đồ thị nhỏ, RAG tìm sự kiện tương tự, SSE (đang dùng polling). Chỉ chạy local, không có đăng nhập (API chỉ nhận Host 127.0.0.1/localhost); không nên chạy đồng thời với script cào sheet trên cùng cổng CDP (khoá chỉ chặn trùng bài, 2 crawler vẫn tranh 1 Chrome).

Job lỗi ở cuối (vd LLM hết key ở request cuối) thì "Gửi lại" cào + gán nhãn lại từ đầu, chưa dùng lại `event.json`/nhãn đã có.
