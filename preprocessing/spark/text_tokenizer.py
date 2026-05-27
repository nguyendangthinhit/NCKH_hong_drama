"""
Tokenizer module — wrap `underthesea.word_tokenize` thành function thuần.

Trả về list[str] tokens đã lowercase + clean punctuation.
Giữ logic giống `Analyze keywords.py::base_tokenize` để đảm bảo PMI Spark
match Python baseline.

Tách module riêng vì:
  1. Spark UDF cần function picklable
  2. `underthesea` import lazy (cache trong worker process) tránh load trên driver
"""

from __future__ import annotations

import re

# Lazy import: chỉ load khi UDF chạy lần đầu trong từng worker
_word_tokenize = None


def _get_tokenizer():
    global _word_tokenize
    if _word_tokenize is None:
        from underthesea import word_tokenize as _wt
        _word_tokenize = _wt
    return _word_tokenize


# Pattern tag tên đầu comment Facebook: 2-4 token, mỗi token bắt đầu chữ hoa
# (có dấu tiếng Việt). Vd: "Thùy Vân", "Đoàn Đức Thành", "Lê Thành Đạt".
# Giới hạn 4 token để không cắt câu hoàn chỉnh "Bộ Giáo dục Đào tạo".
_NAME_TAG_PREFIX_RE = re.compile(
    r"^((?:[A-ZĐÀ-Ỹ][a-zđà-ỹ]+\s+){1,3}[A-ZĐÀ-Ỹ][a-zđà-ỹ]+)\b"
)

# Họ tiếng Việt phổ biến — dùng làm anchor để phân biệt tag tên người
# vs cụm danh từ riêng ("Bộ Giáo dục", "Sở GD&ĐT").
_VN_SURNAMES = {
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ",
    "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đoàn", "Lương", "Mai",
    "Trịnh", "Đinh", "Cao", "Tạ", "Tô", "Trương", "Kim", "Đào", "Đậu", "Lưu",
    "Tôn", "Diệp", "Nông", "Quách", "Khổng", "Lâm", "Thái", "Châu", "Chu",
    "La", "Hà", "Thân", "Trang", "Vương", "Văn", "Thùy", "Trúc", "Tuyết",
}

# Tên phổ biến (first name) — lo case "Thùy Vân" mà không có họ
_VN_COMMON_FIRSTNAMES_PREFIX = {
    "Thùy", "Trúc", "Tuyết", "Nguyệt", "Hằng", "Mai", "Linh", "Như",
    "Ngọc", "Phương", "Ánh", "Vân", "Yến", "Hồng", "Hà", "Quỳnh",
}


def strip_name_tag_prefix(text: str) -> str:
    """
    Loại tag tên đứng đầu comment.

    Heuristic 2 lớp:
      1. Match pattern 2-4 token Title-case ở đầu.
      2. CHỈ strip nếu token đầu là họ Việt phổ biến HOẶC tên Việt phổ biến
         → tránh false positive với cụm danh từ ("Bộ Giáo dục", "Sở GD&ĐT").

    Comment thuần tag tên ("Đoàn Đức Thành") đã bị `is_trash` lọc trước nên
    ở đây chỉ xử lý case "Thùy Vân + nội dung".
    """
    if not isinstance(text, str):
        return text
    m = _NAME_TAG_PREFIX_RE.match(text)
    if not m:
        return text
    matched = m.group(1)
    first_token = matched.split()[0]
    if (
        first_token not in _VN_SURNAMES
        and first_token not in _VN_COMMON_FIRSTNAMES_PREFIX
    ):
        return text
    rest = text[m.end():].lstrip()
    if len(rest) >= 3:
        return rest
    return text


def tokenize(text, strip_names: bool = False) -> list[str]:
    """
    Tokenize Vietnamese text → list of lowercase tokens.

    Logic match `Analyze keywords.py::base_tokenize`:
      - (option) strip name-tag prefix Facebook
      - underthesea word segmentation (compound joined by `_`)
      - replace `_` → space, lowercase
      - strip punctuation
      - giữ token không rỗng

    Args:
        text: comment string.
        strip_names: True nếu muốn loại tag tên đầu comment trước khi tokenize.
    """
    if text is None or not isinstance(text, str):
        return []
    if strip_names:
        text = strip_name_tag_prefix(text)
    try:
        wt = _get_tokenizer()
        raw = wt(text, format="text").split()
    except Exception:
        raw = text.split()

    out = []
    for tok in raw:
        cleaned = tok.replace("_", " ").lower().strip()
        cleaned = re.sub(r"[^\w\s]", "", cleaned, flags=re.UNICODE).strip()
        if cleaned:
            out.append(cleaned)
    return out


def tokenize_strip(text) -> list[str]:
    """Alias `tokenize(text, strip_names=True)` — picklable cho Spark UDF."""
    return tokenize(text, strip_names=True)


if __name__ == "__main__":
    samples = [
        "Bộ Giáo dục cần xử lý nghiêm gian lận thi cử.",
        "Thùy Vân không dám ra cổng luôn",
        "Đoàn Đức Thành",  # đã bị is_trash lọc, nhưng test edge
        "Trúc Phương bạn hiểu ý mình trứ",
        "Lê Thành Đạt buồn không anh",
    ]
    for s in samples:
        print(f"  raw:    {s}")
        print(f"  no:     {tokenize(s)}")
        print(f"  strip:  {tokenize(s, strip_names=True)}")
        print()

