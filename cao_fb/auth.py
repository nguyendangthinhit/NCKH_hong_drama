"""
auth.py
Xử lý đăng nhập Facebook và quản lý session cookies.
Session lưu vào file JSON để tái sử dụng, tránh đăng nhập lại mỗi lần chạy.
"""

import json
import os
import logging
from playwright.sync_api import Page, BrowserContext

import config

logger = logging.getLogger(__name__)


def save_session(context: BrowserContext) -> None:
    """Lưu cookies sau khi đăng nhập thành công."""
    os.makedirs(os.path.dirname(config.SESSION_FILE), exist_ok=True)
    cookies = context.cookies()
    with open(config.SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    logger.info(f"Session đã lưu → {config.SESSION_FILE}")


def load_session(context: BrowserContext) -> bool:
    """
    Load cookies từ file vào context.
    Trả về True nếu load thành công, False nếu file không tồn tại.
    """
    if not os.path.exists(config.SESSION_FILE):
        logger.info("Không tìm thấy session file → cần đăng nhập mới.")
        return False
    with open(config.SESSION_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    logger.info("Đã load session từ file.")
    return True


def is_logged_in(page: Page) -> bool:
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    
    # Log URL hiện tại để debug
    logger.debug(f"  is_logged_in check, URL: {page.url}")
    
    login_btn = page.query_selector('button[name="login"    ]')
    if login_btn:
        logger.debug("  → Thấy nút login → chưa đăng nhập")
        return False

    search = (
        page.query_selector('[aria-label="Tìm kiếm trên Facebook"]') or
        page.query_selector('[aria-label="Search Facebook"]') or
        page.query_selector('[aria-label="Search"]')
    )
    
    result = search is not None
    logger.debug(f"  → Search bar found: {result}")
    return result



def login(page: Page, context: BrowserContext) -> None:
    """
    Đăng nhập Facebook bằng email/password từ .env.
    Sau khi thành công → lưu session.
    Nếu gặp checkpoint/2FA → dừng lại cho user xử lý thủ công.
    """
    if not config.FB_EMAIL or not config.FB_PASSWORD:
        raise ValueError("Chưa cấu hình FB_EMAIL / FB_PASSWORD trong .env")

    logger.info("Đang mở trang đăng nhập Facebook...")
    page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    page.fill('input[name="email"]', config.FB_EMAIL)
    page.wait_for_timeout(500)
    page.fill('input[name="pass"]', config.FB_PASSWORD)
    page.wait_for_timeout(500)
    # Thử click tự động trước
    try:
        page.click('button[name="login"]', timeout=5000)
    except Exception:
        # Nếu không click được → nhờ user bấm thủ công
        logger.warning("Không tự click được nút Login (có thể do captcha).")
        input(">>> Hãy tự bấm nút Đăng nhập trên browser, xong nhấn Enter ở đây...")

    logger.info("Đã submit form, đang chờ redirect...")

    try:
        page.wait_for_url("https://www.facebook.com/", timeout=15_000)
    except Exception:
        logger.warning(
            "Không redirect sau login — có thể bị checkpoint hoặc 2FA.\n"
            "Hãy xử lý thủ công trên browser, sau đó nhấn Enter để tiếp tục."
        )
        input(">>> Nhấn Enter sau khi xử lý checkpoint...")

   # Chờ thêm 2s để trang ổn định sau khi user xử lý
    page.wait_for_timeout(2000)

    if not is_logged_in(page):
        # Thử navigate về home rồi check lại
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if not is_logged_in(page):
            raise RuntimeError("Đăng nhập thất bại. Kiểm tra lại email/password.")

    logger.info("Đăng nhập thành công!")
    save_session(context)


def ensure_logged_in(page: Page, context: BrowserContext) -> None:
    """
    Entry point: kiểm tra session → nếu chưa/hết hạn thì login lại.
    Gọi hàm này một lần trước khi bắt đầu scrape.
    """
    if load_session(context):
        if is_logged_in(page):
            logger.info("Session hợp lệ, bỏ qua đăng nhập.")
            return
        logger.warning("Session hết hạn → đăng nhập lại.")
    login(page, context)