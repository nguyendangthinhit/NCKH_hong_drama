"""
Drama Intelligence System - Keyword Frequency Analyzer
=======================================================
Phân tích từ/cụm từ xuất hiện nhiều nhất trong bình luận
Sử dụng: python analyze_keywords.py
Input:  education_comments.json, showbiz_comments.json (cùng thư mục)
Output: keyword_analysis.txt
"""

import json
import re
from collections import defaultdict, Counter
from pathlib import Path

# ─── Cài underthesea nếu chưa có ───────────────────────────────────────────
try:
    from underthesea import word_tokenize
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "underthesea", "--break-system-packages", "-q"])
    from underthesea import word_tokenize


# ─── Stopwords tiếng Việt ───────────────────────────────────────────────────
STOPWORDS = {
    "và", "của", "là", "có", "cho", "trong", "với", "được", "không",
    "này", "đó", "thì", "mà", "để", "hay", "hoặc", "những", "các", "một",
    "về", "như", "theo", "lại", "đã", "sẽ", "bị", "vì", "khi", "nếu",
    "còn", "cũng", "đây", "đâu", "từ", "ra", "vào", "lên", "xuống", "qua",
    "tôi", "mình", "bạn", "em", "anh", "chị", "họ", "người", "mọi",
    "rất", "quá", "thật", "thì", "nhưng", "mà", "dù", "dù", "tuy",
    "nên", "do", "vậy", "thôi", "đi", "ơi", "nhỉ", "nhé", "ạ", "à",
    "ừ", "uh", "ok", "okay", "oke", "nha", "nè", "ne", "ha", "hả",
    "cái", "con", "cái", "bài", "thế", "vẫn", "đang", "đến", "đi",
    "sau", "trước", "trên", "dưới", "giữa", "bên", "ngoài",
    "làm", "nói", "biết", "thấy", "muốn", "cần", "phải", "hết",
    "ai", "gì", "sao", "nào", "bao", "bất", "cứ", "mỗi", "tất", "cả",
    "đều", "chỉ", "chỉ", "chỉ", "chỉ", "bao", "nhiêu", "lần", "lúc",
    "kia", "đó", "thế", "vậy", "như", "vậy", "thôi", "luôn", "cũng",
}

# Lọc thêm: từ quá ngắn (< 3 ký tự) hoặc chỉ số/emoji
def is_valid_token(token: str) -> bool:
    token = token.strip()
    if len(token) < 3:
        return False
    if token.lower() in STOPWORDS:
        return False
    # Bỏ URL
    if token.startswith("http") or token.startswith("www"):
        return False
    # Bỏ chuỗi chỉ toàn số hoặc ký tự đặc biệt
    if re.fullmatch(r"[\d\W_]+", token):
        return False
    # Bỏ cụm từ quá dài (> 4 âm tiết, thường do lỗi tokenizer)
    if len(token.split()) > 4:
        return False
    return True


def extract_id_content(comment_id: str) -> str:
    """
    Trích id_content từ comment_id.
    VD: "cmt_education_001_0002"  → "education_001"
         "cmt_showbiz_003_r01"    → "showbiz_003"
    """
    # Bỏ prefix "cmt_"
    stripped = re.sub(r"^cmt_", "", comment_id)
    # Lấy 2 phần đầu: domain + số
    parts = stripped.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return stripped


def tokenize_text(text: str) -> list[str]:
    """Tokenize tiếng Việt, trả về list cụm từ hợp lệ (lowercase)."""
    try:
        tokens = word_tokenize(text, format="text").split()
    except Exception:
        # fallback: tách thô theo khoảng trắng
        tokens = text.split()
    # Chuẩn hoá: nối lại token có dấu gạch dưới của underthesea (cụm từ)
    result = []
    for tok in tokens:
        tok_clean = tok.replace("_", " ").lower().strip()
        if is_valid_token(tok_clean):
            result.append(tok_clean)
    return result


def analyze_file(filepath: str) -> dict:
    """
    Đọc file json, đếm từng từ/cụm từ theo id_content.
    Trả về: {token: {id_content: count}}
    """
    with open(filepath, encoding="utf-8") as f:
        comments = json.load(f)

    token_map: dict[str, Counter] = defaultdict(Counter)

    for item in comments:
        cid = item.get("comment_id", "")
        text = item.get("text", "")
        id_content = extract_id_content(cid)

        tokens = tokenize_text(text)
        for tok in tokens:
            token_map[tok][id_content] += 1

    return token_map


def top_keywords(token_map: dict, top_n: int = 10) -> list[tuple]:
    """Lấy top N từ theo tổng số lần xuất hiện."""
    totals = {tok: sum(counter.values()) for tok, counter in token_map.items()}
    return sorted(totals.items(), key=lambda x: x[1], reverse=True)[:top_n]


def format_output(label: str, token_map: dict, top_n: int = 10) -> str:
    lines = [f"{'='*60}", f"  TOP {top_n} TỪ/CỤM TỪ — {label.upper()}", f"{'='*60}\n"]
    top = top_keywords(token_map, top_n)

    for rank, (token, total) in enumerate(top, 1):
        detail_parts = [f"{id_c}: {cnt}" for id_c, cnt
                        in sorted(token_map[token].items(),
                                  key=lambda x: x[1], reverse=True)]
        detail_str = ", ".join(detail_parts)
        lines.append(f"{rank:>2}. \"{token}\"")
        lines.append(f"    Tổng: {total} lần | Chi tiết: [{detail_str}]")
        lines.append("")

    return "\n".join(lines)


def main():
    base = Path(__file__).parent

    edu_path = base / "education_comments.json"
    show_path = base / "showbiz_comments.json"

    missing = [p for p in [edu_path, show_path] if not p.exists()]
    if missing:
        print(f"[LỖI] Không tìm thấy file(s): {[str(m) for m in missing]}")
        print("Hãy đặt education_comments.json và showbiz_comments.json cùng thư mục với script.")
        return

    print("📊 Đang phân tích education_comments.json ...")
    edu_map = analyze_file(edu_path)

    print("📊 Đang phân tích showbiz_comments.json ...")
    show_map = analyze_file(show_path)

    output = []
    output.append("DRAMA INTELLIGENCE SYSTEM — KEYWORD FREQUENCY ANALYSIS")
    output.append("Phân tích từ/cụm từ xuất hiện nhiều nhất trong bình luận\n")
    output.append(format_output("Education", edu_map, top_n=10))
    output.append("\n")
    output.append(format_output("Showbiz", show_map, top_n=10))

    result_text = "\n".join(output)

    out_path = base / "keyword_analysis.txt"
    out_path.write_text(result_text, encoding="utf-8")
    print(f"\n✅ Đã lưu kết quả vào: {out_path}")
    print("\n" + result_text)


if __name__ == "__main__":
    main()