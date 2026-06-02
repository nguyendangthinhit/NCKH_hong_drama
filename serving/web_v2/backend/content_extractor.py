"""Trích xuất text mô tả sạch từ field `content` của data_web.json.

Field `content` có 2 dạng:
  1. Plain text (đa số showbiz)  -> trả về nguyên văn.
  2. Chuỗi JSON lồng (một số education/showbiz, đôi khi lỗi cú pháp)
     -> cố parse lấy key "content"; nếu lỗi thì regex bóc field "content".
"""

import json
import re

_CONTENT_RE = re.compile(r'"content"\s*:\s*"(.*?)"\s*,\s*"[a-z_]+"\s*:', re.DOTALL)


def extract_clean_content(raw: str) -> str:
    """Trả về đoạn mô tả sự kiện ở dạng text thuần."""
    if not raw or not isinstance(raw, str):
        return ""

    stripped = raw.strip()

    # Dạng plain text -> dùng luôn
    if not stripped.startswith("{"):
        return stripped

    # Dạng JSON lồng -> thử parse chuẩn
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and obj.get("content"):
            return str(obj["content"]).strip()
    except (json.JSONDecodeError, ValueError):
        pass

    # Parse lỗi -> regex bóc field "content"
    match = _CONTENT_RE.search(stripped)
    if match:
        text = match.group(1)
        # giải mã escape cơ bản
        text = text.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
        return text.strip()

    # Fallback: bỏ ký tự JSON, trả phần đọc được
    fallback = re.sub(r'[{}"\[\]]', " ", stripped)
    return re.sub(r"\s+", " ", fallback).strip()


def make_excerpt(text: str, max_len: int = 220) -> str:
    """Cắt đoạn tóm tắt ngắn cho card."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + "…"
