"""Cấu hình chung của post_analyzer: đường dẫn, cổng, lựa chọn số comment.

Đổi bằng biến môi trường khi cần (không cần sửa code):
    POST_ANALYZER_DATA_DIR   thư mục lưu jobs.db + kết quả (mặc định data/post-analyzer)
    POST_ANALYZER_CDP_PORT   cổng Chrome CDP của tài khoản phụ (mặc định 9222, dùng chung profile cào sheet)
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INGESTION_DIR = PROJECT_ROOT / "ingestion"

# Helper cào/analysis in emoji; stdout của server ghi ra file trên Windows dùng cp1252 -> UnicodeEncodeError
# (gặp khi chạy thật 2026-11-23). Ép UTF-8, ký tự lạ thay thế thay vì làm job lỗi.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# analysis_new và ingestion là thư mục code ở gốc repo, không phải package cài đặt
for _p in (PROJECT_ROOT, INGESTION_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DATA_DIR = Path(os.environ.get("POST_ANALYZER_DATA_DIR", PROJECT_ROOT / "data" / "post-analyzer"))
DB_PATH = DATA_DIR / "jobs.db"
JOBS_DIR = DATA_DIR / "jobs"
CDP_PORT = int(os.environ.get("POST_ANALYZER_CDP_PORT", "9222"))

# Lựa chọn hiện trên web; 0 = cào toàn bộ
COMMENT_CHOICES = [50, 100, 200, 300, 400, 500, 0]
ALL_COMMENTS_ROUNDS = 1000  # "toàn bộ": crawler tự dừng khi tới đáy / 8 vòng không thêm comment

# Số lần thử lại 1 request khi LLM trả nhãn hỏng (client đã xoay sang model khác)
LABEL_RETRIES = 2
