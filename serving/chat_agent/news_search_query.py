"""Dựng câu tìm tin cho Firecrawl/Google News. Câu hỏi văn nói ("drama nào đang hot gần đây")
gần như không ra kết quả, nên rút về từ khoá (giữ dấu, giữ tên riêng).
Port của serving/chat_agent_worker/src/news-search-query.ts (giữ cùng hành vi).
"""
import re
import unicodedata

from intent_rules import category_hint
from text_normalizer import strip_accents

# Cụm hỏi/chỉ thời gian (đã bỏ dấu) bị cắt khỏi câu tìm. Bỏ theo CỤM để không xoá nhầm tên riêng
# (vd "hiện" trong "Hiền Hồ", "nhật" trong "Nhật Kim Anh").
STOP_PHRASES = [p.split() for p in """moi nhat|gan day|gan nhat|moi day|vua roi|vua xay ra|hom nay|hom qua
|tuan nay|thang nay|dao nay|hien tai|hien gio|bay gio|luc nay|tin moi|co gi moi|cap nhat|dien bien moi
|dang hot|ra sao roi|the nao roi|the nao|ra sao|su kien|tin tuc|thong tin|quan tam nhat|noi bat|gay bao
|on ao|lum xum|tren mang|dan mang|cho minh|cho toi|cho hoi""".replace("\n", "").split("|")]
# Từ đơn để bỏ: so CÓ DẤU (chữ thường) vì bỏ dấu thì "có" trùng "cô" (cô giáo), "bị" trùng "Bí"...
STOP_WORDS = set(
    "à ạ ai ấy bị biết các có của đang đó drama được gì hay hot không ko là mới này nào nè nhé những "
    "nữa ơi phốt rồi scandal thế thêm thì tin về với vậy vụ xem".split()
)
GENERIC_QUERY = {"showbiz": "ồn ào showbiz Việt", "education": "giáo dục gây xôn xao"}
MAX_QUERY_WORDS = 6  # câu tìm dài (cả tiêu đề) thì Google News gần như không trả kết quả

_EDGE_PUNCT = re.compile(r"^[^\w]+|[^\w]+$")


def _norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", strip_accents(tok))


def search_keywords(message: str) -> str:
    """Từ khoá giữ dấu của câu hỏi, đã bỏ cụm hỏi/chỉ thời gian."""
    toks = [t for t in (_EDGE_PUNCT.sub("", w) for w in message.split()) if t]
    norms = [_norm(t) for t in toks]
    keep, i = [], 0
    while i < len(toks):
        phrase = next((p for p in STOP_PHRASES if norms[i:i + len(p)] == p), None)
        if phrase:
            i += len(phrase)
            continue
        if unicodedata.normalize("NFC", toks[i].lower()) not in STOP_WORDS:
            keep.append(toks[i])
        i += 1
    return " ".join(keep)


def _only_category(kw: str) -> bool:
    return not kw or (category_hint(kw) is not None and len(kw.split()) <= 2)


def is_generic_question(message: str) -> bool:
    """Câu hỏi không nêu chủ thể cụ thể (chỉ còn tên lĩnh vực hoặc không còn gì)."""
    return _only_category(search_keywords(message))


def build_search_query(message: str) -> str:
    """Câu tìm cho câu hỏi không khớp sự kiện local. Chỉ còn tên lĩnh vực -> câu tìm chung."""
    kw = search_keywords(message)
    return GENERIC_QUERY[category_hint(message) or "showbiz"] if _only_category(kw) else kw


def title_subject(title: str) -> str:
    """Chủ thể của tiêu đề: phần trước "–"/":" và tối đa 6 từ, vd "Jack (J97) – ..." -> "Jack J97"."""
    subject = re.split(r"\s[–-]\s|:", title)[0]
    subject = re.sub(r"[()\"“”'‘’]", " ", subject)
    return " ".join(subject.split()[:MAX_QUERY_WORDS])


def event_search_query(title: str, message: str | None = None) -> str:
    """Câu tìm cho sự kiện có sẵn. message = câu hỏi khớp trực tiếp sự kiện: dùng từ khoá của nó
    nếu gọn; câu nối tiếp ("có gì mới không") thì không truyền -> chủ thể tiêu đề."""
    kw = search_keywords(message) if message else ""
    if not _only_category(kw) and len(kw.split()) <= MAX_QUERY_WORDS:
        return kw
    return title_subject(title)
