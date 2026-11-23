"""LLM đoán lĩnh vực (showbiz / education) của 1 bài viết từ nội dung bài + vài comment đầu.

Hai lĩnh vực dùng bộ nhãn và summary khác nhau trong analysis_new, nên phải chốt trước khi gán nhãn.
"""

import settings  # noqa: F401  (thêm gốc repo vào sys.path)
from analysis_new.config import DOMAINS  # noqa: E402
from analysis_new.request_planner import parse_json_loose  # noqa: E402

DEFAULT_DOMAIN = "showbiz"
POST_CHARS = 1500
SAMPLE_COMMENTS = 15
COMMENT_CHARS = 150

PROMPT = """Bạn phân loại một bài viết mạng xã hội tiếng Việt vào đúng 1 lĩnh vực:
- "showbiz": giải trí, nghệ sĩ, người nổi tiếng, KOL, phim, nhạc, đời tư người của công chúng, drama mạng.
- "education": giáo dục, trường học, thi cử, giáo viên, học sinh/sinh viên, chính sách giáo dục.
Nếu không rõ, chọn lĩnh vực gần nhất.

NỘI DUNG BÀI:
{post}

MỘT SỐ BÌNH LUẬN:
{comments}

Chỉ trả JSON một dòng: {{"domain": "showbiz" hoặc "education", "reason": "<tối đa 20 từ>"}}"""


def build_prompt(event: dict) -> str:
    post = (event.get("post_title") or event.get("name") or "").strip()[:POST_CHARS] or "(không lấy được nội dung bài)"
    texts = [str(c.get("text") or "").strip() for c in event.get("comments", [])]
    sample = [t[:COMMENT_CHARS] for t in texts if t][:SAMPLE_COMMENTS]
    comments = "\n".join(f"- {t}" for t in sample) or "(không có)"
    return PROMPT.format(post=post, comments=comments)


def parse_domain(text: str) -> tuple:
    """Trả (domain, reason). Không đọc được thì (None, lý do)."""
    data = parse_json_loose(text)
    if isinstance(data, dict):
        d = str(data.get("domain", "")).strip().lower()
        if d in DOMAINS:
            return d, str(data.get("reason", "")).strip()
    low = (text or "").lower()  # model trả chữ thường thay vì JSON
    hits = [d for d in DOMAINS if d in low]
    if len(hits) == 1:
        return hits[0], ""
    return None, f"không đọc được lĩnh vực từ trả lời LLM: {(text or '')[:80]!r}"


def detect_domain(client, event: dict) -> dict:
    """{domain, reason, source}. LLM trả lời hỏng -> mặc định showbiz, source='default'."""
    text, model = client.complete(build_prompt(event))
    domain, reason = parse_domain(text)
    if domain:
        return {"domain": domain, "reason": reason, "source": f"llm:{model}"}
    return {"domain": DEFAULT_DOMAIN, "reason": reason, "source": "default"}
