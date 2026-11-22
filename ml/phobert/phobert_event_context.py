"""Ngữ cảnh sự kiện cho PhoBERT: input = cặp câu (tên + tóm tắt sự kiện, bình luận).

Nhãn (nhất là stance Giáo dục) là thái độ của bình luận ĐỐI VỚI sự kiện, nên model cần biết
sự kiện là gì. File ngữ cảnh là JSON phẳng {event_id: "tên sự kiện. đoạn đầu nội dung"},
dựng một lần từ data/processed/outputnew/{domain}/*.json rồi gửi kèm gói Colab:

    python ml/phobert/phobert_event_context.py --src data/processed/outputnew/education \
        --out "labeling data/event_contexts_education.json"
"""

import argparse
import json
import re
from pathlib import Path

DEFAULT_CONTEXT_CHARS = 400  # ~100-130 token sau tách từ: chừa chỗ cho bình luận trong max_length


_NESTED_CONTENT = re.compile(r'"content"\s*:\s*"(.*?)"\s*,\s*"(?:actor_related|time_event)"', re.S)


def _inner(value):
    """Vài file lưu `content` là chuỗi JSON lồng cả object sự kiện -> lấy object trong.
    Một số chuỗi đó là JSON hỏng (dấu " trong nội dung không escape): rút `content` bằng regex."""
    if not (isinstance(value, str) and value.lstrip().startswith("{")):
        return None
    try:
        inner = json.loads(value)
        return inner if isinstance(inner, dict) else None
    except json.JSONDecodeError:
        m = _NESTED_CONTENT.search(value)
        return {"content": m.group(1)} if m else None


def event_context_text(event: dict, max_chars: int = DEFAULT_CONTEXT_CHARS) -> str:
    """Tên sự kiện + đoạn đầu nội dung, cắt theo ký tự (không cắt giữa từ nếu tránh được)."""
    inner = _inner(event.get("content"))
    if inner:
        event = {**inner, **{k: v for k, v in event.items() if k != "content"}}
        event["content"] = inner.get("content", "")
    title = " ".join(str(event.get("ten_su_kien") or "").split())
    body = " ".join(str(event.get("content") or "").split())
    text = f"{title}. {body}" if title and body else title or body
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    return cut[: cut.rfind(" ")] if " " in cut else cut


def build_event_contexts(src_dir: str, max_chars: int = DEFAULT_CONTEXT_CHARS) -> dict:
    """Đọc mọi {event_id}.json trong thư mục -> {event_id: văn bản ngữ cảnh}."""
    out = {}
    for path in sorted(Path(src_dir).glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            event = json.load(fh)
        text = event_context_text(event, max_chars)
        if text:
            out[str(event.get("id_content") or path.stem)] = text
    return out


def load_event_contexts(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: cần JSON dạng {{event_id: văn bản}}")
    return {str(k): str(v) for k, v in data.items()}


def row_contexts(event_ids, contexts: dict, seg) -> tuple[list[str], int]:
    """Ngữ cảnh (đã tách từ bằng `seg`, mỗi sự kiện tách 1 lần) cho từng dòng + số dòng thiếu.
    Dòng có event_id không có trong file -> ngữ cảnh rỗng (model vẫn chạy, chỉ thiếu thông tin)."""
    cache, out, missing = {}, [], 0
    for e in event_ids:
        key = str(e)
        if key not in contexts:
            missing += 1
            out.append("")
            continue
        if key not in cache:
            cache[key] = seg(contexts[key])
        out.append(cache[key])
    return out, missing


def main():
    ap = argparse.ArgumentParser(description="Dựng file ngữ cảnh sự kiện cho PhoBERT")
    ap.add_argument("--src", required=True, help="thư mục {event_id}.json (data/processed/outputnew/<domain>)")
    ap.add_argument("--out", required=True, help="file JSON đầu ra")
    ap.add_argument("--max_chars", type=int, default=DEFAULT_CONTEXT_CHARS)
    a = ap.parse_args()
    contexts = build_event_contexts(a.src, a.max_chars)
    if not contexts:
        raise SystemExit(f"Không tìm thấy sự kiện nào trong {a.src}")
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(contexts, fh, ensure_ascii=False, indent=1)
    print(f"Đã ghi {len(contexts)} sự kiện -> {a.out}")


if __name__ == "__main__":
    main()
