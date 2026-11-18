"""Rule lọc rác trước khi gọi LLM. Giữ nguyên logic `is_trash_rule` của analysis/single
(analyze_comments.py / analyze_education_async.py) để kết quả lọc rác tương đương bản cũ."""

import re

_SPAM_KEYWORDS = ["lụm về share", "lụm", "share", "quảng cáo",
                  "inbox mình", "inbox em", "tag ", "bit.ly"]
_EMOJI_TAIL_RE = re.compile(r'[=:;<>()\-\/\\🫨😂😭😅😆🥲👍👎❤️🔥💀🙄😑😐🤣\s]+')


def _looks_like_name_word(w: str) -> bool:
    if not w or not w[0].isupper():
        return False
    if len(w) > 1 and not w[1:].islower():
        return False
    return not any(c.isdigit() for c in w)


def _looks_like_name(s: str) -> bool:
    words = s.strip().split()
    return 2 <= len(words) <= 5 and all(_looks_like_name_word(w) for w in words)


def is_trash_rule(text) -> bool:
    """True nếu bình luận chắc chắn là rác (quá ngắn, emoji, link, spam, chỉ tag tên)."""
    if not isinstance(text, str):
        return True
    raw = text.strip()
    t = raw.lower()

    if len(t.replace(" ", "")) < 4:
        return True
    if not re.search(r'[a-zàáâãèéêìíòóôõùúăđĩũơ]', t):
        return True
    if re.fullmatch(r'(h+|k+|ok+e*|lol+|haha+|he+|hi+|uh+|ah+|ew+|hehe+)', t):
        return True
    if re.search(r'https?://', t):
        return True
    if re.search(r'\b(thpt|thcs|hocmai|fanpage)\b', t):
        return True
    if re.search(r'\b(trường thpt|trường thcs|trường đh|trường đại học)\b', t):
        return True
    if re.search(r'[a-z]+\.vn\b', t):
        return True
    if "@" in t and len(raw.split()) <= 4:
        return True
    if any(k in t for k in _SPAM_KEYWORDS):
        return True
    if _looks_like_name(raw):
        return True

    words = raw.split()
    for name_len in range(4, 1, -1):
        if len(words) >= name_len and _looks_like_name(" ".join(words[:name_len])):
            remaining = " ".join(words[name_len:]).strip()
            if not remaining or len(remaining) < 30 or _EMOJI_TAIL_RE.fullmatch(remaining):
                return True
            break
    return False
