# Facebook Comment Scraper
## Drama Intelligence System — Data Collection Module

---

## Cấu trúc project

```
fb_scraper/
├── main.py                # Entry point
├── config.py              # Cấu hình toàn hệ thống
├── auth.py                # Đăng nhập Facebook + quản lý session
├── sheets_reader.py       # Đọc Google Sheets → danh sách task
├── scraper.py             # Core: mở URL, scroll, expand, thu thập
├── parser.py              # Parse DOM → dict theo schema
├── gemini_summarizer.py   # Gọi Gemini tổng hợp nội dung post
├── storage.py             # Lưu/load data_cao_fb.json
├── requirements.txt
├── .env.example
├── credentials.json       # (bạn tự thêm) Google Service Account
├── session/               # (tự tạo) Lưu cookies FB session
└── output/
    ├── data_cao_fb.json   # File output chính
    └── raw/               # Thư mục dự phòng
```

---

## Cài đặt

```bash
# 1. Tạo môi trường ảo
python -m venv venv
venv\Scripts\activate

# 2. Cài dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Tạo file .env
New-Item .env -ItemType File
notepad .env
```

Nội dung `.env`:
```env
FB_EMAIL=your_fb_email
FB_PASSWORD=your_fb_password
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_SHEETS_ID=your_sheet_id_from_url
GOOGLE_CREDENTIALS_FILE=credentials.json
SHEET_NAME_TEST=tên_sheet_test
SHEET_NAME_REAL=tên_sheet_thật
```

---

## Cấu trúc Google Sheets

| Danh mục | id_content | Tên sự kiện | links |
|---|---|---|---|
| showbiz | showbiz_001_20250601 | Vụ XYZ | https://fb.com/... https://fb.com/... |
| educate | educate_001_20250601 | Vụ ABC | (trống = không có FB post) |

- Cột `links`: nhiều URL cách nhau bằng **dấu cách**
- Row không có links → bỏ qua tự động

---

## Chạy

```bash
python main.py
```

Sẽ hỏi bạn chọn sheet test hay thật, sau đó tự động:
1. Đọc Google Sheets
2. Đăng nhập Facebook (lần đầu) hoặc load session (lần sau)
3. Cào từng sự kiện
4. Tổng hợp với Gemini
5. Lưu vào `output/data_cao_fb.json`

---

## Output schema

```json
[
  {
    "id_content": "showbiz_001_20250601",
    "category": "showbiz",
    "event_name": "Vụ XYZ",
    "post_content": "Nội dung tổng hợp từ Gemini",
    "source_urls": ["https://fb.com/...", "https://fb.com/..."],
    "sort_mode": "most_recent",
    "comments": [
      {
        "comment_id": "cmt_showbiz0010_0001",
        "order": 1,
        "text": "Nội dung comment",
        "likes": 120,
        "reply_count": 5,
        "url_source": "https://fb.com/...",
        "replies": [
          {
            "comment_id": "cmt_showbiz0010_0001_r01",
            "order": 1,
            "reply_to_id": "cmt_showbiz0010_0001",
            "text": "Nội dung reply",
            "likes": 30
          }
        ]
      }
    ],
    "_scraped_at": "2025-06-01T10:30:00"
  }
]
```

---

## Xử lý sự cố

| Vấn đề | Giải pháp |
|---|---|
| Checkpoint / 2FA | Browser dừng, xử lý thủ công, Enter để tiếp |
| Session hết hạn | Xóa `session/fb_session.json`, chạy lại |
| Selector bị break | Inspect DevTools, cập nhật selector trong `scraper.py` |
| Gemini lỗi | Tự động fallback ghép thủ công, không crash |
| Crash giữa chừng | Output đã lưu sự kiện trước, chạy lại tiếp từ chỗ dừng |
