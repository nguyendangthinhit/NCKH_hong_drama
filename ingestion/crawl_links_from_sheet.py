"""Cào lần lượt từng link Facebook có trạng thái pending trong bảng (mặc định FB_Crawl_skills/data/cao.xlsx).

Mỗi link gọi crawler FB_Crawl_skills/scripts/05_auto_scrape_cdp.py qua Chrome CDP. Cào xong và có
common.jsonl -> ghi "done" vào bảng ngay (dừng giữa chừng không mất tiến độ). Lỗi -> giữ "pending".

    python ingestion/crawl_links_from_sheet.py                 # cào mọi link pending
    python ingestion/crawl_links_from_sheet.py --event showbiz_064 --limit 1
    python ingestion/crawl_links_from_sheet.py --list          # chỉ xem trạng thái

Chạy SONG SONG: mỗi terminal một --port khác nhau (mỗi cổng = 1 cửa sổ Chrome + 1 profile riêng):
    terminal 1: python ingestion/crawl_links_from_sheet.py                        (trên xuống, cổng 9222)
    terminal 2: python ingestion/crawl_links_from_sheet.py --reverse --port 9223  (dưới lên, profile -9223)
Link đang cào được giữ bằng file khoá <thư mục bài>/.crawl.lock nên 2 terminal không cào trùng.

Kết quả mỗi link: FB_Crawl_skills/data/posts/<slug>/{common.jsonl, post.json, raw.json}.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRAWLER_DIR = ROOT / "FB_Crawl_skills"
sys.path[:0] = [str(Path(__file__).resolve().parent), str(CRAWLER_DIR / "scripts")]

from _browser import BrowserConfig  # noqa: E402  (crawler)
from _data_paths import POSTS_DIR, sanitize_url  # noqa: E402  (crawler)
from crawl_sheet_io import DONE, PENDING, CrawlSheet  # noqa: E402

CRAWLER = CRAWLER_DIR / "scripts" / "05_auto_scrape_cdp.py"
SESSIONS = CRAWLER_DIR / "sessions"
MAIN_PORT = 9222
DEFAULT_SHEET = CRAWLER_DIR / "data" / "cao.xlsx"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def crawl_url(url: str) -> str:
    """Link thật đưa cho crawler. Trang reel/<id> không hiện comment cho crawler (0 comment),
    còn watch/?v=<id> của cùng video thì hiện (thử 2026-11-22: 66 comment) -> đổi reel sang watch."""
    m = re.search(r"facebook\.com/reel/(\d+)", url)
    return f"https://www.facebook.com/watch/?v={m.group(1)}" if m else url


def post_folder(url: str) -> Path:
    """Thư mục crawler ghi kết quả cho một link (cùng quy tắc với _data_paths.post_dir)."""
    return POSTS_DIR / sanitize_url(crawl_url(url))


def latest_common(folder: Path):
    """common.jsonl mới nhất của một bài. Crawler không ghi đè file cũ mà ghi common_<giờ>.jsonl."""
    files = sorted(folder.glob("common*.jsonl"), key=lambda f: f.stat().st_mtime)
    return files[-1] if files else None


def profile_for(port: int) -> Path:
    name = "chrome-crawler-profile" if port == MAIN_PORT else f"chrome-crawler-profile-{port}"
    return SESSIONS / name


def cdp_alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def ensure_browser(port: int, wait_s: int = 30) -> None:
    """Mở Chrome (profile riêng của cổng này) với CDP nếu chưa mở. Profile mới thì phải đăng nhập FB 1 lần."""
    if cdp_alive(port):
        return
    profile = profile_for(port)
    first_time = not profile.exists()
    cfg = BrowserConfig(name="google-chrome", path=str(CHROME), user_data_dir=str(profile), port=port).resolve()
    print(f"🌐 Mở Chrome cổng {port} (profile {profile.name}) ...")
    subprocess.Popen([cfg["path"]] + cfg["args"] + ["https://www.facebook.com/"])
    for _ in range(wait_s):
        time.sleep(1)
        if cdp_alive(port):
            break
    else:
        sys.exit(f"❌ Chrome không mở cổng CDP {port} sau {wait_s}s")
    if first_time:
        input("🔑 Profile mới: đăng nhập Facebook trong cửa sổ Chrome vừa mở, xong bấm Enter để bắt đầu cào...")


def keep_awake() -> None:
    """Không cho Windows ngủ / tắt màn hình khi đang cào (tự hết hiệu lực khi script thoát).
    Máy ngủ giữa chừng làm Chrome treo -> crawler báo lỗi (đã gặp 2026-11-22, mất bài 27k comment)."""
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
    print("☕ Giữ máy không ngủ trong lúc cào")


def max_rounds_for(n_comments: int, cap: int) -> int:
    """Số vòng bấm/cuộn tối đa: ~8 comment mỗi vòng (đo trên bài 248 comment / 19 vòng), tối thiểu 50.
    Crawler tự dừng sớm khi đã tới đáy nên đặt dư không tốn thêm thời gian."""
    rounds = max(50, n_comments // 8)
    return min(rounds, cap) if cap else rounds


def count_lines(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def try_lock(url: str, port: int):
    """Giữ link bằng file khoá (tạo nguyên tử). Trả đường dẫn khoá, hoặc None nếu terminal khác đang giữ."""
    lock = post_folder(url) / ".crawl.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(fd, f"port={port} pid={os.getpid()} at={time.strftime('%Y-%m-%d %H:%M:%S')}".encode())
    os.close(fd)
    return lock


def crawl_one(row: dict, rounds_cap: int, port: int = MAIN_PORT) -> int:
    """Chạy crawler cho 1 link; trả số comment trong common.jsonl mới ghi (0 = thất bại)."""
    started = time.time()
    cmd = [sys.executable, "-X", "utf8", str(CRAWLER), crawl_url(row["url"]),
           "--event-id", row["event_id"], "--target", str(row["n_comments"]),
           "--max-rounds", str(max_rounds_for(row["n_comments"], rounds_cap)),
           "--user-data-dir", str(profile_for(port))]
    env = {**os.environ, "FB_CDP_HTTP": f"http://127.0.0.1:{port}"}
    code = subprocess.run(cmd, cwd=CRAWLER_DIR, env=env).returncode
    if code != 0:
        print(f"   ❌ crawler thoát mã {code}")
        return 0
    out = latest_common(post_folder(row["url"]))
    if out is None or out.stat().st_mtime < started:  # không có file mới -> không tính
        print(f"   ❌ không thấy common*.jsonl mới tại {post_folder(row['url'])}")
        return 0
    return count_lines(out)


def print_status(rows: list) -> None:
    for r in rows:
        lock = " (đang cào)" if (post_folder(r["url"]) / ".crawl.lock").exists() else ""
        print(f"  [{r['status']:7}] {r['event_id']:13} {r['n_comments']:>6} cmt  {r['url']}{lock}")
    n_done = sum(r["status"] == DONE for r in rows)
    print(f"📋 {n_done}/{len(rows)} link done, {len(rows) - n_done} pending")


def pending_rows(sheet_path, event, reverse=False) -> list:
    rows = [r for r in CrawlSheet.load(sheet_path).rows()
            if r["status"] == PENDING and (not event or r["event_id"] == event)]
    return rows[::-1] if reverse else rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(DEFAULT_SHEET))
    ap.add_argument("--event", help="Chỉ cào các link của mã sự kiện này")
    ap.add_argument("--limit", type=int, default=0, help="Cào tối đa N link rồi dừng")
    ap.add_argument("--reverse", action="store_true", help="Cào từ dòng cuối bảng lên")
    ap.add_argument("--port", type=int, default=MAIN_PORT, help="Cổng CDP; mỗi terminal song song 1 cổng")
    ap.add_argument("--max-rounds-cap", type=int, default=0,
                    help="Trần số vòng cho mỗi link (0 = không giới hạn; mỗi vòng ~4s)")
    ap.add_argument("--list", action="store_true", help="Chỉ in trạng thái, không cào")
    args = ap.parse_args()

    sheet = CrawlSheet.load(args.sheet)
    if args.list:
        return print_status(sheet.rows())
    if not sheet.has_status_col:
        sheet.save()  # lần đầu: thêm cột "Trang thai" (pending)
    if not pending_rows(args.sheet, args.event):
        return print_status(sheet.rows())
    ensure_browser(args.port)
    keep_awake()

    results, tried = [], set()
    while not args.limit or len(results) < args.limit:
        # đọc lại bảng mỗi vòng: terminal khác có thể vừa cào xong link
        todo = [r for r in pending_rows(args.sheet, args.event, args.reverse) if r["url"] not in tried]
        lock = row = None
        for r in todo:
            tried.add(r["url"])
            lock = try_lock(r["url"], args.port)
            if lock:
                row = r
                break
            print(f"⏭️  Terminal khác đang cào: {r['url']}")
        if not row:
            break
        print(f"\n=== [cổng {args.port}] {row['event_id']} | {row['page']} | ~{row['n_comments']} cmt\n{row['url']}")
        try:
            n = crawl_one(row, args.max_rounds_cap, args.port)
        except KeyboardInterrupt:
            print("\n⏹  Dừng theo yêu cầu; link này vẫn pending.")
            break
        finally:
            lock.unlink(missing_ok=True)
        if n:
            CrawlSheet.mark(args.sheet, row["url"], DONE)
            print(f"   ✅ done: {n} comment (FB hiển thị {row['n_comments']})")
        results.append({"event_id": row["event_id"], "url": row["url"], "comments": n,
                        "status": DONE if n else PENDING})
    print("\n" + json.dumps(results, ensure_ascii=False, indent=1))
    print_status(CrawlSheet.load(args.sheet).rows())


if __name__ == "__main__":
    main()
