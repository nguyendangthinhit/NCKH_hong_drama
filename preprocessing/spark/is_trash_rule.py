"""
Rule-based noise detector — phiên bản deterministic, không dùng LLM.

Thay thế cho `tienxuly_vietlaiorder.py` (gọi Gemini) bằng các rule:
  1. Quá ngắn (< 3 ký tự sau strip)
  2. Chỉ chứa emoji / ký tự đặc biệt
  3. Chỉ tag tên (toàn từ viết hoa, không có dấu câu / số / từ thường)
  4. Chuỗi ký tự lặp vô nghĩa ("hhh", "kkkk", "...")
  5. Chỉ chứa interjection ("ok", "oke", "haha", "hihi")

Hàm `is_trash(text)` thuần function (không I/O, không state) → safe cho Spark UDF.
"""

import re
import unicodedata


_TRASH_INTERJECTIONS = {
    "ok", "okay", "oke", "okê", "okie", "ko", "kk", "kkk",
    "haha", "hihi", "hehe", "huhu", "hoho", "hahaha", "hihihi",
    "uh", "ừ", "um", "ừm", "ờ", "ơ", "ạ", "à", "á",
    "hm", "hmm", "hmmm", "ah", "ahh", "oh", "ohh",
    "vâng", "dạ", "ừh", "ừa", "ờm",
    "thế", "vậy", "rồi", "thôi", "nhé", "nha", "nhỉ",
    "wow", "woa", "ui", "ối", "ôi",
}

_REPEATED_CHAR_RE = re.compile(r"^(.)\1{2,}$")
_PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_DIGIT_ONLY_RE = re.compile(r"^\d+$")
# Vietnamese capitalised name pattern: "Nguyễn Văn A" — mỗi token bắt đầu bằng chữ hoa
_NAME_TOKEN_RE = re.compile(r"^[A-ZÀ-Ỹ][a-zà-ỹ]*$")


def _strip_emoji(text: str) -> str:
    """Lọc bỏ ký tự thuộc category emoji / symbol để xét nội dung text thực."""
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in {"So", "Sk", "Sm", "Cn"}
    )


def _is_emoji_only(text: str) -> bool:
    """True nếu sau khi strip emoji + whitespace thì rỗng."""
    return not _strip_emoji(text).strip()


def _is_name_tag_only(text: str) -> bool:
    """True nếu toàn bộ token đều là tên người (chữ hoa đầu, không số, không câu)."""
    tokens = text.split()
    if len(tokens) == 0 or len(tokens) > 5:
        return False
    if not all(_NAME_TOKEN_RE.match(tok) for tok in tokens):
        return False
    # Có ít nhất 1 token >= 2 ký tự (loại "A B C" 1 chữ cái)
    return any(len(tok) >= 2 for tok in tokens)


def _is_repeated_chars(text: str) -> bool:
    """True nếu là chuỗi 1 ký tự lặp ('hhh', 'aaaa', '....')."""
    cleaned = re.sub(r"\s+", "", text.lower())
    return bool(_REPEATED_CHAR_RE.match(cleaned))


def is_trash(text) -> bool:
    """
    True nếu comment được coi là rác.

    Args:
        text: chuỗi comment. Có thể None hoặc không phải string.

    Returns:
        bool. Trả True khi text rỗng / quá ngắn / emoji / tag tên / lặp ký tự / interjection.
    """
    if text is None:
        return True
    if not isinstance(text, str):
        return True

    stripped = text.strip()

    if len(stripped) < 3:
        return True

    if _PUNCT_ONLY_RE.match(stripped):
        return True

    if _DIGIT_ONLY_RE.match(stripped):
        return True

    if _is_emoji_only(stripped):
        return True

    if _is_repeated_chars(stripped):
        return True

    if stripped.lower() in _TRASH_INTERJECTIONS:
        return True

    if _is_name_tag_only(stripped):
        return True

    return False


if __name__ == "__main__":
    cases = [
        ("Bộ giáo dục cần xử lý nghiêm các trường hợp gian lận.", False),
        ("Hhh", True),
        ("ok", True),
        (".", True),
        ("😍😍😍", True),
        ("Nguyễn Văn A", True),
        ("👍", True),
        ("12345", True),
        ("Đoàn Đức Thành", True),
        ("Trúc Phương bạn hiểu ý mình trứ 😌", False),
        ("", True),
        (None, True),
    ]
    fail = 0
    for text, expected in cases:
        got = is_trash(text)
        ok = got == expected
        print(f"{'OK ' if ok else 'FAIL'}  is_trash({text!r:50}) → {got} (expected {expected})")
        if not ok:
            fail += 1
    print(f"\n{len(cases) - fail}/{len(cases)} pass")
