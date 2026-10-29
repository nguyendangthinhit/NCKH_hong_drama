"""
config.py
Tập trung toàn bộ cấu hình hệ thống.
Đọc từ .env, không hardcode giá trị nhạy cảm.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Facebook ────────────────────────────────────────────────────────────────
FB_EMAIL    = os.getenv("FB_EMAIL", "")
FB_PASSWORD = os.getenv("FB_PASSWORD", "")

# ─── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
# ─── Google Sheets ───────────────────────────────────────────────────────────
GOOGLE_SHEETS_ID       = os.getenv("GOOGLE_SHEETS_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SHEET_NAME_TEST        = os.getenv("SHEET_NAME_TEST", "Sheet_Test")
SHEET_NAME_REAL        = os.getenv("SHEET_NAME_REAL", "Sheet_Real")

# Tên các cột trong sheet (đúng với header bạn đã tạo)
COL_CATEGORY   = "Danh mục"
COL_ID_CONTENT = "id_content"
COL_EVENT_NAME = "Tên sự kiện"
COL_LINKS      = "Links"

# ─── Session ─────────────────────────────────────────────────────────────────
SESSION_FILE = "session/fb_session.json"

# ─── Output ──────────────────────────────────────────────────────────────────
OUTPUT_DIR  = "output"
RAW_DIR     = f"{OUTPUT_DIR}/raw"
OUTPUT_FILE = f"{OUTPUT_DIR}/data_cao_fb.json"   # File JSON tổng hợp cuối cùng

# ─── Scraping behaviour ──────────────────────────────────────────────────────
SORT_MODE= "all_comments"
SCROLL_PAUSE_MS      = 2500
LOAD_MORE_TIMEOUT_MS = 10_000
MAX_RETRIES          = 3
HEADLESS             = False   # False = hiện browser để dễ debug

# ─── Browser ─────────────────────────────────────────────────────────────────
VIEWPORT   = {"width": 1280, "height": 900}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
