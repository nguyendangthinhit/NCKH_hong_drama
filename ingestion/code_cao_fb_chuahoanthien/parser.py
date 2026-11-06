"""
parser.py
Parse các element HTML từ Playwright thành dict đúng schema.

Schema comment:
{
    "comment_id": "cmt_<post_id>_<order>",
    "order": 1,
    "text": "...",
    "likes": 120,
    "reply_count": 5,
    "url_source": "https://fb.com/...",
    "replies": [
        {
            "comment_id": "cmt_<post_id>_<order>_r<reply_order>",
            "order": 1,
            "reply_to_id": "cmt_<post_id>_<order>",
            "text": "...",
            "likes": 30
        }
    ]
}
"""

import re
import logging
from playwright.sync_api import ElementHandle

logger = logging.getLogger(__name__)

# Tên người thường ngắn, dùng để lọc — hạ xuống 5 để giữ comments ngắn
MIN_TEXT_LEN = 15

# Các chuỗi chắc chắn là tên người / UI element, không phải comment
SKIP_PATTERNS = [
    r"^[\w\s]{1,40}$",  # Chỉ chữ cái và khoảng trắng, ngắn → có thể là tên
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_count(raw: str) -> int:
    """Chuyển chuỗi số Facebook ('1,2K', '3.5K', '120') thành int."""
    if not raw:
        return 0
    raw = raw.strip().replace(",", ".")
    try:
        if "K" in raw.upper():
            return int(float(raw.upper().replace("K", "")) * 1000)
        if "M" in raw.upper():
            return int(float(raw.upper().replace("M", "")) * 1_000_000)
        nums = re.findall(r"[\d.]+", raw)
        return int(float(nums[0])) if nums else 0
    except Exception:
        return 0


def _safe_text(el: ElementHandle | None) -> str:
    if el is None:
        return ""
    try:
        return el.inner_text().strip()
    except Exception:
        return ""


def _get_text(el: ElementHandle) -> str:
    """
    Lấy text comment từ các [dir="auto"] bên trong element.
    Ưu tiên text dài nhất (tránh lấy tên người).
    Hạ ngưỡng xuống MIN_TEXT_LEN để giữ comments ngắn như 'Đồng ý', '+1'.
    """
    try:
        text_els = el.query_selector_all('[dir="auto"]')
        texts = []
        for t_el in text_els:
            try:
                t = t_el.inner_text().strip()
                if t:
                    texts.append(t)
            except Exception:
                continue

        # Lọc text đủ dài
        content_texts = [t for t in texts if len(t) >= MIN_TEXT_LEN]

        if content_texts:
            return max(content_texts, key=len)

        # Fallback: lấy text dài nhất kể cả ngắn
        if texts:
            return max(texts, key=len)

    except Exception:
        pass
    return ""


def _get_likes(el: ElementHandle) -> int:
    """
    Lấy số likes từ aria-label của reaction button.
    Facebook render dạng:
      - aria-label="5 người đã thả tim"
      - aria-label="12 lượt thích"
      - aria-label="1,2K reactions"
    """
    # Bước 1: Tìm tất cả [aria-label] ngắn có chứa số
    try:
        candidates = el.query_selector_all('[aria-label]')
        for candidate in candidates:
            try:
                label = candidate.get_attribute("aria-label") or ""
                if not label or len(label) > 60:
                    continue

                # Log để debug
                logger.debug(f"    aria-label: '{label}'")

                nums = re.findall(r'[\d,.]+', label)
                if nums:
                    val = _parse_count(nums[0])
                    if 0 < val < 10_000_000:
                        return val
            except Exception:
                continue
    except Exception:
        pass

    # Bước 2: Fallback — tìm span số thuần túy gần nút Thích/Like
    try:
        like_zone = (
            el.query_selector('[aria-label*="Thích"]') or
            el.query_selector('[aria-label*="Like"]') or
            el.query_selector('[aria-label*="thích"]')
        )
        if like_zone:
            spans = like_zone.query_selector_all('span')
            for span in spans:
                try:
                    text = span.inner_text().strip()
                    if text and re.match(r'^[\d,.]+[KkMm]?$', text):
                        return _parse_count(text)
                except Exception:
                    continue
    except Exception:
        pass

    return 0


def _make_comment_id(post_id: str, order: int) -> str:
    return f"cmt_{post_id}_{order:04d}"


def _make_reply_id(comment_id: str, reply_order: int) -> str:
    return f"{comment_id}_r{reply_order:02d}"


# ─── Parse reply ─────────────────────────────────────────────────────────────

def parse_reply(
    reply_el: ElementHandle,
    parent_comment_id: str,
    reply_order: int,
) -> dict | None:
    try:
        text = _get_text(reply_el)
        if not text:
            return None

        likes    = _get_likes(reply_el)
        reply_id = _make_reply_id(parent_comment_id, reply_order)

        return {
            "comment_id":  reply_id,
            "order":       reply_order,
            "reply_to_id": parent_comment_id,
            "text":        text,
            "likes":       likes,
        }
    except Exception as e:
        logger.debug(f"Lỗi parse reply: {e}")
        return None


# ─── Parse comment ────────────────────────────────────────────────────────────

def parse_comment(
    comment_el: ElementHandle,
    post_id: str,
    order: int,
    url_source: str,
) -> dict | None:
    try:
        text = _get_text(comment_el)
        if not text:
            return None

        likes = _get_likes(comment_el)

        # Reply count từ nút "X phản hồi"
        reply_btn = (
            comment_el.query_selector('[aria-label*="phản hồi"]') or
            comment_el.query_selector('[aria-label*="repl"]')
        )
        reply_count = _parse_count(_safe_text(reply_btn))

        comment_id = _make_comment_id(post_id, order)

        # Parse replies đã load trong DOM
        # Parse replies đã load trong DOM (hỗ trợ nhiều cấu trúc FB)
        reply_els = comment_el.query_selector_all('ul > li[role="article"]')
        if not reply_els:
            reply_els = comment_el.query_selector_all('div[role="article"] div[role="article"]')
        replies = []
        for r_order, reply_el in enumerate(reply_els, start=1):
            parsed = parse_reply(reply_el, comment_id, r_order)
            if parsed:
                replies.append(parsed)

        return {
            "comment_id":  comment_id,
            "order":       order,
            "text":        text,
            "likes":       likes,
            "reply_count": max(reply_count, len(replies)),
            "url_source":  url_source,
            "replies":     replies,
        }
    except Exception as e:
        logger.debug(f"Lỗi parse comment #{order}: {e}")
        return None