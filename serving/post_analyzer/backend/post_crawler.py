"""Cào 1 link Facebook bằng crawler FB_Crawl_skills (Chrome CDP + profile tài khoản phụ).

Dùng lại helper của ingestion/crawl_links_from_sheet.py (đổi reel -> watch, thư mục bài, profile theo cổng,
file khoá .crawl.lock). Crawler `--target N` tự dừng khi đủ N comment (comment + reply) và cắt còn N;
N = 0 là cào toàn bộ.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import settings  # noqa: F401  (thêm ingestion/ vào sys.path)
import crawl_links_from_sheet as cls  # noqa: E402

FB_HOSTS = ("facebook.com", "fb.watch", "fb.com")
# l.facebook.com/lm.facebook.com là trang chuyển hướng ra web ngoài, không phải bài viết
BLOCKED_HOSTS = ("l.facebook.com", "lm.facebook.com")
SECONDS_PER_ROUND_LIMIT = 15  # 1 vòng thực tế ~4–6s; quá ~15s/vòng coi như crawler treo
TIMEOUT_MARGIN_S = 300


class CrawlError(RuntimeError):
    """Cào thất bại; thông điệp hiện thẳng cho người dùng."""


def validate_url(url: str) -> str:
    """Chỉ nhận link http(s) của Facebook; trả link đã bỏ khoảng trắng."""
    url = (url or "").strip()
    p = urlparse(url)
    host = (p.hostname or "").lower()
    ok_host = any(host == h or host.endswith("." + h) for h in FB_HOSTS) and host not in BLOCKED_HOSTS
    if p.scheme not in ("http", "https") or not ok_host or p.path.strip("/") == "":
        raise ValueError("Bản hiện tại chỉ nhận link bài viết Facebook (facebook.com / fb.watch).")
    return url


def cache_key(url: str) -> str:
    """Khoá dùng lại kết quả: tên thư mục bài của crawler (bỏ query rác kiểu ?mibextid=)."""
    return cls.post_folder(url).name


def ensure_logged_in_browser(port: int) -> None:
    """Mở Chrome CDP của tài khoản phụ nếu chưa mở. Profile chưa từng đăng nhập thì báo lỗi rõ,
    vì bước đăng nhập lần đầu cần người thao tác (ensure_browser sẽ chờ input())."""
    if cls.cdp_alive(port):
        return
    profile = cls.profile_for(port)
    if not profile.exists():
        raise CrawlError(f"Chưa có profile Chrome cho cổng {port} ({profile.name}). Cần đăng nhập tài "
                         "khoản phụ 1 lần: xem docs/post-analyzer.md mục 'Đăng nhập tài khoản phụ'.")
    try:
        cls.ensure_browser(port)
    except SystemExit as e:  # ensure_browser dùng sys.exit khi Chrome không mở cổng
        raise CrawlError(str(e)) from None


def rounds_for(max_comments: int, all_rounds: int) -> int:
    return cls.max_rounds_for(max_comments, 0) if max_comments else all_rounds


def allow_sleep() -> None:
    """Trả lại chế độ ngủ cho Windows sau khi cào (keep_awake gắn theo thread worker sống lâu)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS


def clear_checkpoint(folder: Path) -> None:
    """Crawler tiếp tục từ checkpoint.json của lần chạy dở trước (cùng thư mục bài). Job web luôn cào mới:
    checkpoint cũ có vòng >= --max-rounds sẽ làm vòng bấm chạy 0 lần."""
    (folder / "checkpoint.json").unlink(missing_ok=True)


def crawl_post(url: str, max_comments: int, event_id: str, port: int, log_path: Path,
               all_rounds: int = 1000) -> Path:
    """Chạy crawler cho 1 link, ghi log ra log_path; trả đường dẫn common*.jsonl vừa ghi."""
    ensure_logged_in_browser(port)
    lock = cls.try_lock(url, port)  # cùng khoá với script cào sheet -> không cào trùng 1 bài
    if lock is None:
        raise CrawlError("Bài này đang được cào ở nơi khác (script cào sheet hoặc job khác); thử lại sau.")
    rounds = rounds_for(max_comments, all_rounds)
    cmd = [sys.executable, "-X", "utf8", str(cls.CRAWLER), cls.crawl_url(url),
           "--event-id", event_id, "--target", str(max_comments), "--max-rounds", str(rounds),
           "--user-data-dir", str(cls.profile_for(port))]
    env = {**os.environ, "FB_CDP_HTTP": f"http://127.0.0.1:{port}", "PYTHONIOENCODING": "utf-8"}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        clear_checkpoint(cls.post_folder(url))
        cls.keep_awake()
        started = time.time()
        with open(log_path, "w", encoding="utf-8") as log:
            code = subprocess.run(cmd, cwd=cls.CRAWLER_DIR, env=env, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=rounds * SECONDS_PER_ROUND_LIMIT + TIMEOUT_MARGIN_S).returncode
    except subprocess.TimeoutExpired:  # run() đã kill tiến trình con
        raise CrawlError("Crawler chạy quá lâu (treo Chrome/Facebook?); đã dừng. Thử lại hoặc chọn ít comment hơn.")
    finally:
        allow_sleep()
        lock.unlink(missing_ok=True)
    if code != 0:
        raise CrawlError(f"Crawler thoát mã {code}; xem log {log_path.name}.")
    out = cls.latest_common(cls.post_folder(url))
    if out is None or out.stat().st_mtime < started:
        raise CrawlError("Crawler chạy xong nhưng không ghi được comment nào (bài riêng tư, bị chặn "
                         "hoặc link sai?).")
    return out
