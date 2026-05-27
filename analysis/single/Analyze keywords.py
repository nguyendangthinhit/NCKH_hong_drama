"""
Drama Intelligence System - Keyword Frequency Analyzer v4
==========================================================
DRAMA INTELLIGENCE SYSTEM — KEYWORD FREQUENCY ANALYSIS v4
PMI min_count=3 | threshold=1.0 | ranking: freq × log2(1+PMI)

Cải tiến so v3:
  - Thêm stopwords: sao, nữa, tui, đừng, yêu, thích, tươi, hát...
  - Ranking mới: score = freq × log2(1 + PMI)  thay vì chỉ dùng freq
    → từ đặc trưng cao (PMI cao) dù tần suất vừa vẫn nổi lên top
    → "gian lận", "tống tiền", "phạt tiền" sẽ beat "nữa", "sao"
  - Lưu thêm cột PMI score trong output để dễ debug

Sử dụng: python analyze_keywords_v4.py
Input:   education_comments.json, showbiz_comments.json (cùng thư mục)
Output:  keyword_analysis_v4.txt
"""

import json
import re
import math
from collections import defaultdict, Counter
from pathlib import Path
from itertools import islice

try:
    from underthesea import word_tokenize
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "underthesea", "--break-system-packages", "-q"])
    from underthesea import word_tokenize


# ─── Stopwords v4 (mở rộng từ v3) ─────────────────────────────────────────
STOPWORDS = {
    # Hư từ / liên từ / giới từ
    "và", "của", "là", "có", "cho", "trong", "với", "được", "không",
    "này", "đó", "thì", "mà", "để", "hay", "hoặc", "những", "các", "một",
    "về", "như", "theo", "lại", "đã", "sẽ", "bị", "vì", "khi", "nếu",
    "còn", "cũng", "đây", "đâu", "từ", "ra", "vào", "lên", "xuống", "qua",
    "nên", "do", "vậy", "dù", "tuy", "nhưng", "song", "thế",
    "trước", "sau", "trên", "dưới", "giữa", "bên", "ngoài", "gần", "xa",
    # Đại từ nhân xưng
    "tôi", "mình", "bạn", "em", "anh", "chị", "họ", "người", "mọi",
    "ta", "chúng", "nó", "tụi", "bọn", "ai", "gì", "nào",
    "đây", "đó", "kia", "ấy",
    "tui", "tao", "mày", "nó", "hắn", "y",
    # Từ thân tộc / xưng hô chung
    "cháu", "chú", "cô", "bác", "ông", "bà", "thầy",
    "anh", "chị", "em", "con",
    # Phó từ / trạng từ vô nghĩa
    "rất", "quá", "thật", "thôi", "đi", "ơi", "nhỉ", "nhé", "ạ", "à",
    "ừ", "uh", "ok", "okay", "oke", "nha", "nè", "ne", "ha", "hả",
    "rồi", "nhiều", "mới", "mấy", "chứ", "lắm", "chưa", "giờ", "thêm",
    "luôn", "vẫn", "cũng", "đang", "đến", "đều", "chỉ", "cả", "hết",
    "thật", "thiệt", "thực", "đúng", "sai", "khác", "riêng",
    "cứ", "mỗi", "tất", "bao", "bất", "lần", "lúc",
    "nhau", "cùng", "xong", "xem",
    # ── MỚI thêm v4 ──
    "sao", "nữa", "nên", "đừng", "vẫn", "thôi", "vậy", "thế",
    "được", "rồi", "mà", "nha", "nhé", "ạ", "ừ",
    # Động từ / tính từ cảm xúc chung (không đặc trưng)
    "yêu", "thích", "ghét", "buồn", "vui", "sợ", "tức",
    "cười", "khóc", "nhìn", "nghe", "nói", "làm", "biết", "thấy",
    "nghĩ", "hiểu", "muốn", "cần", "phải",
    "hát", "chơi", "tươi", "đẹp", "xấu", "tốt", "kém",
    # Danh từ chung không mang insight
    "nhà", "lớp", "người", "việc", "cái", "con", "bài", "cách",
    "kiểu", "loại", "dạng", "chuyện", "điều",
    # Số đo / thời gian mơ hồ
    "năm", "tháng", "ngày", "hôm", "tuần",
    # Cảm thán
    "ôi", "wow", "haha", "hihi", "hehe", "hm", "hmm", "ừm",
    "ah", "oh", "ui", "ủa", "ờ", "ơ",
}


def is_valid_token(token: str) -> bool:
    token = token.strip()
    if len(token) < 3:
        return False
    if token.lower() in STOPWORDS:
        return False
    if token.startswith("http") or token.startswith("www"):
        return False
    if re.fullmatch(r"[\d\W_]+", token):
        return False
    return True


def extract_id_content(comment_id: str) -> str:
    stripped = re.sub(r"^cmt_", "", comment_id)
    parts = stripped.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return stripped


def base_tokenize(text: str) -> list[str]:
    try:
        raw = word_tokenize(text, format="text").split()
    except Exception:
        raw = text.split()
    result = []
    for tok in raw:
        tok_clean = tok.replace("_", " ").lower().strip()
        tok_clean = re.sub(r"[^\w\s]", "", tok_clean).strip()
        if tok_clean:
            result.append(tok_clean)
    return result


def sliding_window(seq, n):
    it = iter(seq)
    result = tuple(islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result


# ─── PMI computation (trả về cả score, không chỉ boolean) ─────────────────

def compute_pmi_scores(all_tokens: list[list[str]],
                       min_count: int = 5,
                       min_pmi: float = 1.0) -> dict[str, float]:
    """
    Tính PMI cho bigram và trigram.
    Trả về {phrase: pmi_score} cho các phrase vượt ngưỡng.
    """
    unigram_count: Counter = Counter()
    bigram_count:  Counter = Counter()
    trigram_count: Counter = Counter()
    total_uni = 0
    total_bi  = 0
    total_tri = 0

    for tokens in all_tokens:
        for tok in tokens:
            unigram_count[tok] += 1
            total_uni += 1
        for bi in sliding_window(tokens, 2):
            bigram_count[" ".join(bi)] += 1
            total_bi += 1
        for tri in sliding_window(tokens, 3):
            trigram_count[" ".join(tri)] += 1
            total_tri += 1

    if total_uni == 0:
        return {}

    pmi_scores: dict[str, float] = {}

    # Bigram PMI
    for phrase, cnt in bigram_count.items():
        if cnt < min_count:
            continue
        w1, w2 = phrase.split(" ", 1)
        if w1 in STOPWORDS or w2 in STOPWORDS:
            continue
        if not is_valid_token(w1) or not is_valid_token(w2):
            continue
        p12 = cnt / total_bi
        p1  = unigram_count[w1] / total_uni
        p2  = unigram_count[w2] / total_uni
        if p1 > 0 and p2 > 0:
            pmi = math.log2(p12 / (p1 * p2))
            if pmi >= min_pmi:
                pmi_scores[phrase] = pmi

    # Trigram: chỉ lấy nếu cả 2 bigram con đều có PMI tốt
    for phrase, cnt in trigram_count.items():
        if cnt < min_count:
            continue
        parts = phrase.split(" ")
        if parts[0] in STOPWORDS or parts[-1] in STOPWORDS:
            continue
        if not all(is_valid_token(p) for p in parts):
            continue
        bi1 = " ".join(parts[:2])
        bi2 = " ".join(parts[1:])
        if bi1 in pmi_scores and bi2 in pmi_scores:
            pmi_scores[phrase] = (pmi_scores[bi1] + pmi_scores[bi2]) / 2

    return pmi_scores


def analyze_file(filepath: str,
                 pmi_min_count: int = 5,
                 pmi_threshold: float = 1.0) -> dict:
    """
    Trả về {token: {"counter": Counter, "pmi": float}}
    """
    with open(filepath, encoding="utf-8") as f:
        comments = json.load(f)

    # Pass 1: tokenize
    print("  Pass 1/2: Tokenize ...")
    all_tokens: list[list[str]] = []
    meta: list[tuple[str, list[str]]] = []
    total = len(comments)

    for idx, item in enumerate(comments, 1):
        if idx % 1000 == 0 or idx == total:
            print(f"    [{idx}/{total}]")
        cid  = item.get("comment_id", "")
        text = item.get("text", "")
        if not text.strip():
            continue
        tokens = base_tokenize(text)
        all_tokens.append(tokens)
        meta.append((extract_id_content(cid), tokens))

    print("  Tính PMI scores ...")
    pmi_scores = compute_pmi_scores(all_tokens, pmi_min_count, pmi_threshold)
    print(f"  → {len(pmi_scores)} ngram vượt ngưỡng PMI")

    high_pmi_set = set(pmi_scores.keys())
    suppressed   = {w for phrase in high_pmi_set for w in phrase.split()}

    # Pass 2: đếm
    print("  Pass 2/2: Đếm token ...")
    # {token: Counter}
    freq_map: dict[str, Counter] = defaultdict(Counter)

    for id_content, tokens in meta:
        matched: set[int] = set()

        for i, tri in enumerate(sliding_window(tokens, 3)):
            phrase = " ".join(tri)
            if phrase in high_pmi_set:
                freq_map[phrase][id_content] += 1
                matched.update([i, i+1, i+2])

        for i, bi in enumerate(sliding_window(tokens, 2)):
            phrase = " ".join(bi)
            if phrase in high_pmi_set:
                freq_map[phrase][id_content] += 1
                matched.update([i, i+1])

        for i, tok in enumerate(tokens):
            if i in matched or tok in suppressed:
                continue
            if is_valid_token(tok):
                freq_map[tok][id_content] += 1

    # Gộp PMI vào result
    result = {}
    for token, counter in freq_map.items():
        result[token] = {
            "counter": counter,
            "pmi": pmi_scores.get(token, 0.0),   # unigram PMI = 0
        }

    return result


def weighted_score(freq: int, pmi: float) -> float:
    """
    score = freq × log2(1 + PMI)
    - Unigram: PMI=0 → log2(1)=0 → score=0 (bị đẩy xuống rất thấp)
    - Bigram PMI=2: log2(3)≈1.58 → score = freq × 1.58
    - Bigram PMI=4: log2(5)≈2.32 → score = freq × 2.32
    Từ đặc trưng cao tự nhiên nổi lên top.
    """
    return freq * math.log2(1 + max(pmi, 0))


def top_keywords(result: dict, top_n: int = 10) -> list[tuple]:
    scored = []
    for token, data in result.items():
        freq  = sum(data["counter"].values())
        pmi   = data["pmi"]
        score = weighted_score(freq, pmi)
        scored.append((token, freq, pmi, score))
    return sorted(scored, key=lambda x: x[3], reverse=True)[:top_n]


def format_output(label: str, result: dict, top_n: int = 10) -> str:
    lines = [
        f"{'='*65}",
        f"  TOP {top_n} TỪ/CỤM TỪ — {label.upper()}  (score = freq × log2(1+PMI))",
        f"{'='*65}\n",
    ]
    top = top_keywords(result, top_n)

    for rank, (token, freq, pmi, score) in enumerate(top, 1):
        counter    = result[token]["counter"]
        detail     = ", ".join(
            f"{k}: {v}"
            for k, v in sorted(counter.items(), key=lambda x: x[1], reverse=True)
        )
        n_articles = len(counter)
        ngram_type = ["unigram", "bigram", "trigram"][min(len(token.split())-1, 2)]
        pmi_str    = f"{pmi:.2f}" if pmi > 0 else "—"

        lines.append(f"{rank:>2}. \"{token}\"  [{ngram_type}]")
        lines.append(
            f"    Tổng: {freq} lần | {n_articles} bài | PMI: {pmi_str} | Score: {score:.1f}"
        )
        lines.append(f"    Chi tiết: [{detail}]")
        lines.append("")

    return "\n".join(lines)


def main():
    base = Path(__file__).parent

    edu_path  = base / "education_comments.json"
    show_path = base / "showbiz_comments.json"

    missing = [p for p in [edu_path, show_path] if not p.exists()]
    if missing:
        print(f"[LỖI] Không tìm thấy: {[str(m) for m in missing]}")
        return

    # Điều chỉnh nếu cần:
    # - PMI_MIN_COUNT thấp hơn (vd 3) → bắt được từ hiếm như "tống tiền"
    # - PMI_THRESHOLD thấp hơn (vd 0.8) → giữ thêm bigram ít phổ biến
    PMI_MIN_COUNT = 3
    PMI_THRESHOLD = 1.0

    print("📊 Education ...")
    edu_result = analyze_file(str(edu_path), PMI_MIN_COUNT, PMI_THRESHOLD)

    print("\n📊 Showbiz ...")
    show_result = analyze_file(str(show_path), PMI_MIN_COUNT, PMI_THRESHOLD)

    output_lines = [
        "DRAMA INTELLIGENCE SYSTEM — KEYWORD FREQUENCY ANALYSIS v4",
        f"PMI min_count={PMI_MIN_COUNT} | threshold={PMI_THRESHOLD} | ranking: freq × log2(1+PMI)\n",
        format_output("Education", edu_result, top_n=10),
        "",
        format_output("Showbiz", show_result, top_n=10),
    ]
    result_text = "\n".join(output_lines)

    out_path = base / "keyword_analysis_v4.txt"
    out_path.write_text(result_text, encoding="utf-8")
    print(f"\n✅ Đã lưu → {out_path}")
    print("\n" + result_text)


if __name__ == "__main__":
    main()