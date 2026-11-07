"""Chuẩn hoá tiếng Việt để so khớp: bỏ dấu, chữ thường, tách từ, sinh bigram."""
import re
import unicodedata

# Viết tắt hay gặp trong câu hỏi người dùng -> dạng đầy đủ xuất hiện trong dữ liệu.
ABBREVIATIONS = {
    "khkt": "khoa hoc ky thuat",
    "tphcm": "ho chi minh",
    "hcm": "ho chi minh",
    "gv": "giao vien",
    "hs": "hoc sinh",
    "sv": "sinh vien",
    "dh": "dai hoc",
    "bgd": "bo giao duc",
    "j97": "jack",
}

# Từ chức năng / từ hỏi: không mang thông tin để phân biệt sự kiện.
STOPWORDS = set(
    """
    a ah ai anh ay ban bao biet bi bo cac cai cho chu chuyen co cua cung da dang
    day de den di do drama duoc gi gioi hay hien ho hoi khi khong kia la lam lai luc
    ma minh mot moi nao nay ne neu nghe nguoi nha nhe nhieu nhu nhung o oi ra roi sao
    se su kien tai the thi thong tin toi tu va ve vi viec voi vu xay xin
    top hot nhat chao hello hi tin tuc cap nhat
    """.split()
)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, đổi đ -> d, chữ thường."""
    text = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize(text: str, drop_stopwords: bool = True) -> list[str]:
    """Trả danh sách token đã bỏ dấu, mở rộng viết tắt."""
    raw = _NON_WORD.split(strip_accents(text))
    tokens: list[str] = []
    for tok in raw:
        if not tok:
            continue
        tokens.extend(ABBREVIATIONS.get(tok, tok).split())
    if drop_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


def terms(text: str) -> set[str]:
    """Tập unigram + bigram dùng để chấm điểm khớp."""
    toks = tokenize(text, drop_stopwords=False)
    unigrams = {t for t in toks if t not in STOPWORDS}
    bigrams = {
        f"{a} {b}"
        for a, b in zip(toks, toks[1:])
        if not (a in STOPWORDS and b in STOPWORDS)
    }
    return unigrams | bigrams


def normalized(text: str) -> str:
    """Chuỗi đã bỏ dấu, gộp khoảng trắng: dùng cho so khớp cụm từ khoá."""
    return " ".join(_NON_WORD.split(strip_accents(text))).strip()
