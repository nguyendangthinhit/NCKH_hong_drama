"""
gemini_summarizer.py
Gọi Gemini 2.5 Flash để tổng hợp nội dung bài post từ nhiều URL.

Hỗ trợ xoay API key tự động từ file api.txt khi bị rate limit (429).
File api.txt: mỗi dòng 1 key, dòng trống và # được bỏ qua.
"""

import logging
import time

from google import genai
from google.genai import errors as genai_errors

import config

logger = logging.getLogger(__name__)


# ─── API Key Manager ──────────────────────────────────────────────────────────

class KeyManager:
    """
    Đọc danh sách API key từ file api.txt, xoay vòng khi bị rate limit.
    Fallback về GEMINI_API_KEY trong .env nếu không có file.
    """

    def __init__(self, key_file: str = "api.txt"):
        self.keys  = self._load_keys(key_file)
        self.index = 0

        if not self.keys:
            if config.GEMINI_API_KEY:
                logger.warning("Không tìm thấy api.txt → dùng key từ .env")
                self.keys = [config.GEMINI_API_KEY]
            else:
                raise ValueError("Không có Gemini API key. Kiểm tra api.txt hoặc .env")

        logger.info(f"Đã load {len(self.keys)} API key")
        self._apply_current()

    def _load_keys(self, path: str) -> list[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [
                line.strip() for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]
        except FileNotFoundError:
            return []

    def _apply_current(self) -> None:
        key = self.keys[self.index]
        logger.debug(f"Dùng key [{self.index + 1}/{len(self.keys)}]: ...{key[-6:]}")

    def rotate(self) -> bool:
        """
        Chuyển sang key tiếp theo.
        Trả về False nếu đã xoay hết vòng.
        """
        next_index = self.index + 1
        if next_index >= len(self.keys):
            logger.error("Đã xoay hết tất cả keys.")
            return False
        self.index = next_index
        logger.warning(f"Rate limit → xoay sang key [{self.index + 1}/{len(self.keys)}]")
        self._apply_current()
        return True


# Khởi tạo một lần khi import
_key_manager = KeyManager()


# ─── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là trợ lý tổng hợp thông tin. Nhiệm vụ của bạn là:
1. Đọc nhiều bài đăng Facebook về cùng một sự kiện/drama
2. Tổng hợp thành 1 đoạn văn mạch lạc, đầy đủ thông tin
3. Giữ lại các chi tiết quan trọng, loại bỏ thông tin trùng lặp
4. Sắp xếp theo trình tự thời gian nếu có thể
5. Viết bằng tiếng Việt, khách quan, không thêm nhận xét cá nhân
6. Chỉ trả về nội dung tổng hợp, không thêm lời mở đầu hay kết thúc"""


# ─── Core call với retry + key rotation ──────────────────────────────────────

def _call_gemini(prompt: str, max_retries: int = 5) -> str:
    """
    Gọi Gemini với tự động retry và xoay key khi bị rate limit (429).
    """
    for attempt in range(max_retries):
        try:
            client = genai.Client(
                api_key=_key_manager.keys[_key_manager.index]
            )
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config={"system_instruction": SYSTEM_PROMPT},
            )
            return response.text.strip()

        except genai_errors.ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warning(f"Rate limit (lần {attempt + 1}/{max_retries})")
                rotated = _key_manager.rotate()
                if not rotated:
                    logger.error("Hết key. Chờ 60s rồi reset...")
                    time.sleep(60)
                    _key_manager.index = 0
            else:
                logger.error(f"Gemini ClientError: {e}")
                time.sleep(5)

        except Exception as e:
            logger.error(f"Lỗi không mong đợi: {e}")
            time.sleep(5)

    raise RuntimeError(f"Gemini thất bại sau {max_retries} lần thử.")


# ─── Public interface ─────────────────────────────────────────────────────────

def summarize_posts(
    event_name: str,
    raw_posts: list[dict],
) -> str:
    """
    Tổng hợp nhiều raw_post_text thành 1 post_content.

    Args:
        event_name: Tên sự kiện để Gemini có context
        raw_posts:  List { url, raw_post_text } từ scraper

    Returns:
        Chuỗi nội dung tổng hợp. Nếu lỗi → fallback ghép thủ công.
    """
    valid_posts = [p for p in raw_posts if p.get("raw_post_text")]

    if not valid_posts:
        logger.warning("Không có post nào có text để tổng hợp.")
        return ""

    if len(valid_posts) == 1:
        logger.info("Chỉ có 1 post → dùng trực tiếp, không gọi Gemini.")
        return valid_posts[0]["raw_post_text"]

    posts_text = ""
    for i, post in enumerate(valid_posts, start=1):
        posts_text += f"\n\n--- Bài đăng {i} ---\n{post['raw_post_text']}"

    prompt = (
        f"Sự kiện: {event_name}\n\n"
        f"Dưới đây là {len(valid_posts)} bài đăng Facebook về cùng sự kiện:\n"
        f"{posts_text}\n\n"
        f"Hãy tổng hợp thành 1 đoạn văn mạch lạc, đầy đủ, không trùng lặp."
    )

    try:
        logger.info(f"Gọi Gemini tổng hợp {len(valid_posts)} bài post...")
        result = _call_gemini(prompt)
        logger.info("✓ Gemini tổng hợp xong.")
        return result

    except Exception as e:
        logger.error(f"Gemini thất bại hoàn toàn: {e} → fallback ghép thủ công.")
        return "\n\n".join(p["raw_post_text"] for p in valid_posts)