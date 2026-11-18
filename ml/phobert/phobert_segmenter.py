"""Tách từ tiếng Việt cho PhoBERT (PhoBERT được huấn luyện trên văn bản đã tách từ, nối bằng "_").

Fine-tune và inference PHẢI dùng cùng segmenter; tên segmenter được lưu trong config.json.
- underthesea: pip install underthesea  (mặc định)
- none: không tách (chỉ dùng khi chủ ý, vd. test; chất lượng thường thấp hơn)
"""

import re

_WS = re.compile(r"\s+")


def clean_text(text) -> str:
    return _WS.sub(" ", str(text)).strip()


def get_segmenter(name: str):
    """Trả hàm str -> str. Báo lỗi rõ nếu thiếu thư viện (không âm thầm hạ cấp)."""
    if name == "none":
        return clean_text
    if name == "underthesea":
        try:
            from underthesea import word_tokenize
        except ImportError as e:
            raise ImportError("Thiếu underthesea: pip install underthesea "
                              "(hoặc chạy với --segmenter none)") from e
        return lambda t: word_tokenize(clean_text(t), format="text")
    raise ValueError(f"Segmenter không hỗ trợ: {name}")
