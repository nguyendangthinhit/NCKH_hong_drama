"""Nhận diện ý định bằng luật (không gọi LLM) và các câu trả lời cố định."""
import re

from text_normalizer import normalized

INFO_REPLY = (
    "Mình là Drama Intelligence Bot 🎭 Mình có thể giúp bạn: tìm hiểu diễn biến các drama "
    "Giáo dục & Showbiz nổi bật, xem dư luận cộng đồng phản ứng thế nào, và xem thống kê "
    "toàn hệ thống. Bạn muốn tìm hiểu sự kiện nào?"
)
GREETING_REPLY = (
    "Chào bạn 👋 Mình là Drama Intelligence Bot, chuyên tổng hợp các drama Giáo dục và "
    "Showbiz. Bạn muốn tìm hiểu sự kiện nào, hay xem các vụ đang được quan tâm nhất?"
)
SPAM_REPLY = "Mình xin phép không phản hồi nội dung này. Nếu bạn muốn tìm hiểu drama nào, cứ hỏi mình nhé."
UNRELATED_REPLY = (
    "Câu này nằm ngoài phạm vi của mình rồi. Mình chỉ hỗ trợ thông tin về các drama Giáo dục "
    "và Showbiz cùng phản ứng dư luận. Bạn muốn hỏi sự kiện nào?"
)
CLARIFY_REPLY = (
    "Bạn có thể cho mình biết cụ thể tên nhân vật hoặc sự kiện bạn đang tìm không? "
    "Hiện mình chưa thấy thông tin khớp trong dữ liệu."
)


def _phrases(text: str) -> list[str]:
    return [p.strip() for p in text.strip().splitlines() if p.strip()]


GREETING_WORDS = set("hello hi hey alo chao xin ban nhe a oi bot ad admin ha lo".split())
INFO_PHRASES = _phrases("""
ban la ai
ban la gi
ban lam duoc gi
ban giup duoc gi
ban co the lam gi
chuc nang
huong dan su dung
gioi thieu ve ban
""")
# Tục tĩu: so trên chữ thường CÒN dấu để tránh nhầm (vd. "lớn" và từ tục).
PROFANITY = re.compile(
    r"(?<!\w)(đm|đmm|dmm|dcm|đcm|vcl|vkl|vl|cc|clm|đéo|địt|đụ|lồn|cặc|buồi|óc chó|ngu như)(?!\w)"
)
TOP_PHRASES = _phrases("""
top
hot
noi bat
quan tam nhat
nhieu nhat
gay bao
danh sach
co drama
co nhung drama
co vu nao
co su kien nao
drama nao
vu nao dang
su kien nao dang
""")
STATS_PHRASES = _phrases("""
thong ke
tong so
bao nhieu su kien
bao nhieu vu
ty le
ti le
binh luan rac
toan he thong
so lieu
""")
OPINION_PHRASES = _phrases("""
du luan
cam xuc
phan ung
cong dong
dan mang
nghi gi
nghi sao
binh luan
tich cuc
tieu cuc
thai do
""")
FOLLOWUP_PHRASES = _phrases("""
vu do
vu nay
su kien do
su kien nay
nguoi do
nguoi nay
anh ay
co ay
ong ay
ba ay
ho
sau do
roi sao
the con
ket qua
tiep theo
chi tiet hon
cu the hon
noi them
""")
DRAMA_PHRASES = _phrases("""
drama
su kien
vu
scandal
on ao
phot
to
tranh cai
bi bat
khoi to
lum xum
bi che
showbiz
giao duc
ca si
""")
EDUCATION_HINTS = _phrases("giao duc\ntruong\nhoc sinh\nsinh vien\ngiao vien\nthi")
SHOWBIZ_HINTS = _phrases("showbiz\ngiai tri\nca si\ndien vien\nnghe si\nkol\ntiktoker\nstreamer\nrapper")


def _has_phrase(norm: str, phrases: list[str]) -> bool:
    padded = f" {norm} "
    return any(f" {p} " in padded for p in phrases)


def is_spam(message: str) -> bool:
    text = message.lower()
    return not normalized(message) or bool(PROFANITY.search(text))


def is_greeting_only(message: str) -> bool:
    toks = normalized(message).split()
    return 0 < len(toks) <= 5 and all(t in GREETING_WORDS for t in toks)


def is_info(message: str) -> bool:
    return _has_phrase(normalized(message), INFO_PHRASES)


def is_top_request(message: str) -> bool:
    return _has_phrase(normalized(message), TOP_PHRASES)


def is_stats_request(message: str) -> bool:
    return _has_phrase(normalized(message), STATS_PHRASES)


def is_opinion_request(message: str) -> bool:
    return _has_phrase(normalized(message), OPINION_PHRASES)


def is_followup(message: str) -> bool:
    return _has_phrase(normalized(message), FOLLOWUP_PHRASES)


def mentions_drama(message: str) -> bool:
    return _has_phrase(normalized(message), DRAMA_PHRASES)


def category_hint(message: str) -> str | None:
    """Trả "education" / "showbiz" nếu câu hỏi nói rõ lĩnh vực, ngược lại None."""
    norm = normalized(message)
    edu = _has_phrase(norm, EDUCATION_HINTS)
    show = _has_phrase(norm, SHOWBIZ_HINTS)
    if edu == show:
        return None
    return "education" if edu else "showbiz"
