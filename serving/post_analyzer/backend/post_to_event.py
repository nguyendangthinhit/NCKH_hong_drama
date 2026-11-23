"""common.jsonl của 1 bài -> sự kiện định dạng chính thức (cây reply lồng nhau) -> dạng nội bộ analysis_new.

Dùng lại build_tree / read_jsonl / post_text của ingestion/crawled_posts_to_analysis_events.py.
"""

from pathlib import Path

import settings  # noqa: F401  (thêm ingestion/ + gốc repo vào sys.path)
from crawled_posts_to_analysis_events import SORT_MODE, build_tree, count_nodes, post_text, read_jsonl  # noqa: E402
from analysis_new.thread_loader import normalize_event  # noqa: E402

NAME_CHARS = 80


def event_name_from(post_content: str, url: str) -> str:
    """Tên hiển thị: dòng đầu nội dung bài (cắt ngắn), không có thì dùng link."""
    first = next((line.strip() for line in post_content.splitlines() if line.strip()), "")
    if not first:
        return url
    return first if len(first) <= NAME_CHARS else first[:NAME_CHARS].rstrip() + "…"


def build_official_event(common_path: Path, folder: Path, event_id: str, url: str) -> dict:
    """Định dạng chính thức {id_content, event_name, sort_mode, post_content, comments[]}."""
    post_content = post_text(folder, "Facebook")
    tree = build_tree(read_jsonl(common_path))
    return {"id_content": event_id, "event_name": event_name_from(post_content.removeprefix("[Facebook] "), url),
            "sort_mode": SORT_MODE, "post_content": post_content, "source_url": url, "comments": tree}


def to_internal(official: dict) -> dict:
    """Dạng nội bộ mà event_pipeline dùng (event_id, name, post_title, comments phẳng có level)."""
    return normalize_event(official, official["id_content"])


def total_comments(official: dict) -> int:
    return count_nodes(official["comments"])
