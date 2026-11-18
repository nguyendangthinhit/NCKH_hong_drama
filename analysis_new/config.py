"""Cấu hình chung cho analysis_new: đường dẫn, bộ nhãn theo lĩnh vực, giới hạn gom request."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# API mmodiary: dòng 4 của .env.local là "API_key=<key1>,<key2>", dòng 5 là "Base URL=..."
ENV_FILE = PROJECT_ROOT / ".env.local"
MODEL_FILE = PROJECT_ROOT / "model_list.txt"
ENV_KEY_LINE = 4
ENV_BASE_URL_LINE = 5
DEFAULT_BASE_URL = "https://api.mmodiary.com/v1"
RESPONSES_PATH = "/responses"

# Tham số thêm vào body request. Để trống cho tới khi xác nhận proxy hỗ trợ
# (ví dụ "max_output_tokens", "temperature").
EXTRA_BODY: dict = {}
REQUEST_TIMEOUT_S = 600  # đo thật 2026-11-17: 60 comment ~130s (model suy luận nhiều)
MAX_429_WAIT_S = 30
# Streaming (SSE): tránh server/proxy ngắt kết nối khi request chạy lâu (HTTP 0 đo thật 2026-11-17).
STREAM = True

# API tính tiền theo REQUEST (DECISIONS.md 2026-11-13): gom nhiều cụm vào một request.
# Đo thật 2026-11-17 (deepseek-v4.1-flash): 60 comment ~130s, đủ nhãn. Lô 150 từng ra nhãn méo chữ, nhưng
# lô 60 cũng có lần bị (lỗi ngẫu nhiên của model, đã chặn bằng mã nhãn ASCII); chưa thử lại 150.
MAX_COMMENTS_PER_REQUEST = 60
MAX_TEXT_CHARS = 300
MAX_POST_CHARS = 2000

CONTROVERSIAL_RATIO = 0.7

# LLM trả nhãn bằng MÃ ASCII (đo thật 2026-11-17: model đôi khi làm méo chữ có dấu, vd "Trung立"),
# code đổi mã -> nhãn tiếng Việt. "labels" giữ nguyên tên tiếng Việt cho đầu ra.
DOMAINS = {
    "showbiz": {
        "label_field": "emotion",
        "codes": {"PN": "Phẫn nộ", "CK": "Cà khịa", "DC": "Đồng cảm", "UH": "Ủng hộ", "TL": "Trung lập"},
        "fallback": "Trung lập",
        "toxic": True,
    },
    "education": {
        "label_field": "stance",
        "codes": {"TC": "tích cực", "TI": "tiêu cực", "TL": "trung lập", "YK": "ý kiến riêng"},
        "fallback": "trung lập",
        "toxic": False,
    },
}
for _cfg in DOMAINS.values():
    _cfg["labels"] = list(_cfg["codes"].values())
TOXIC_CODES = {"CB": "chửi bới", "CN": "công kích cá nhân", "NT": "công kích người thân"}
TOXIC_TYPES = list(TOXIC_CODES.values())


def decode(value, codes: dict):
    """Mã ("CK") hoặc nhãn đầy đủ ("Cà khịa") -> nhãn tiếng Việt; không nhận ra thì None."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v.upper() in codes:
        return codes[v.upper()]
    return v if v in codes.values() else None


def domain_cfg(domain: str) -> dict:
    """Trả cấu hình lĩnh vực; báo lỗi rõ ràng nếu tên lĩnh vực sai."""
    if domain not in DOMAINS:
        raise ValueError(f"domain phải là một trong {list(DOMAINS)}, nhận '{domain}'")
    return DOMAINS[domain]
