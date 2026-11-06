"""
storage.py
Quản lý file output data_cao_fb.json.

Cấu trúc file:
[
    {
        "id_content": "showbiz_001_20250601",
        "category": "showbiz",
        "event_name": "Vụ XYZ",
        "post_content": "Nội dung tổng hợp từ Gemini",
        "source_urls": ["https://...", "https://..."],
        "comments": [
            {
                "comment_id": "...",
                "order": 1,
                "text": "...",
                "likes": 120,
                "reply_count": 5,
                "url_source": "https://...",
                "replies": [...]
            }
        ],
        "_scraped_at": "2025-06-01T10:30:00"
    }
]

Mỗi lần scrape xong 1 sự kiện → append vào file ngay
(không chờ xong hết mới lưu → tránh mất data nếu crash giữa chừng)
"""

import json
import os
import logging
from datetime import datetime

import config

logger = logging.getLogger(__name__)


def _ensure_dirs() -> None:
    os.makedirs(config.RAW_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)


def load_all() -> list[dict]:
    """Load toàn bộ data từ file output (để check đã scrape chưa)."""
    _ensure_dirs()
    if not os.path.exists(config.OUTPUT_FILE):
        return []
    with open(config.OUTPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _clean_event(data: dict) -> dict:
    data.pop("source_urls", None)
    data.pop("category", None)
    data.pop("_scraped_at", None)
    for c in data.get("comments", []):
        c.pop("url_source", None)
        for r in c.get("replies", []):
            r.pop("url_source", None)
    return data

def get_scraped_ids() -> set[str]:
    """Trả về set id_content đã được scrape."""
    data = load_all()
    return {item["id_content"] for item in data}


def append_event(event_data: dict) -> None:
    """
    Append 1 sự kiện vào file data_cao_fb.json.
    Nếu id_content đã tồn tại → ghi đè (update).
    """
    _ensure_dirs()

    # Thêm timestamp
    event_data["_scraped_at"] = datetime.now().isoformat()

    # Load data hiện có
    all_data = load_all()

    # Kiểm tra đã có chưa → update nếu có
    existing_ids = {item["id_content"]: i for i, item in enumerate(all_data)}
    id_content = event_data["id_content"]

    if id_content in existing_ids:
        all_data[existing_ids[id_content]] = event_data
        logger.info(f"  Updated [{id_content}] trong {config.OUTPUT_FILE}")
    else:
        all_data.append(event_data)
        logger.info(f"  Appended [{id_content}] vào {config.OUTPUT_FILE}")
    
    event_data = _clean_event(event_data   )
    # Ghi lại file
    with open(config.OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    # Log stats
    total_comments = len(event_data.get("comments", []))
    total_replies  = sum(
        len(c.get("replies", []))
        for c in event_data.get("comments", [])
    )
    logger.info(
        f"  └─ {total_comments} comments, {total_replies} replies | "
        f"{len(event_data.get('source_urls', []))} URLs"
    )
