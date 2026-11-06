"""
main.py
Entry point của Facebook scraper.

Luồng hoạt động:
  1. Chọn sheet (test / thật)
  2. Đọc Google Sheets → danh sách task (id_content + urls)
  3. Lọc bỏ các sự kiện đã scrape rồi
  4. Đăng nhập Facebook (load session hoặc login mới)
  5. Với mỗi sự kiện:
     a. Cào từng URL → raw_post_text + comments
     b. Sau khi cào xong hết URLs → gọi Gemini tổng hợp post_content
     c. Lưu vào data_cao_fb.json ngay
  6. Tiếp tục sự kiện tiếp theo

Cách chạy:
  python main.py
  → Sẽ hỏi bạn muốn chạy sheet test hay thật
"""

import logging
import sys
import os
import colorlog
from playwright.sync_api import sync_playwright

import config
import auth
import scraper
import storage
import gemini_summarizer
from sheets_reader import read_tasks


# ─── Logging ─────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        },
    ))
    logging.basicConfig(level=logging.DEBUG, handlers=[handler])


# ─── Sheet selector ──────────────────────────────────────────────────────────

def choose_sheet() -> str:
    """Hỏi user muốn chạy sheet test hay thật."""
    print("\n" + "="*60)
    print("  Facebook Comment Scraper — Drama Intelligence System")
    print("="*60)
    print(f"  [1] Sheet TEST  → '{config.SHEET_NAME_TEST}'")
    print(f"  [2] Sheet THẬT  → '{config.SHEET_NAME_REAL}'")
    print("="*60)

    while True:
        choice = input("Chọn sheet (1/2): ").strip()
        if choice == "1":
            return config.SHEET_NAME_TEST
        if choice == "2":
            return config.SHEET_NAME_REAL
        print("  Nhập 1 hoặc 2.")


# ─── Process 1 sự kiện ───────────────────────────────────────────────────────

def process_event(page, task: dict) -> dict | None:
    """
    Scrape toàn bộ URLs của 1 sự kiện, gọi Gemini tổng hợp,
    trả về dict event hoàn chỉnh.
    """
    id_content = task["id_content"]
    event_name = task["event_name"]
    urls       = task["urls"]
    category   = task["category"]

    # post_id ngắn để tạo comment_id
    post_id = id_content.replace("_", "")[:12]

    logger.info(f"\n{'─'*55}")
    logger.info(f"Sự kiện: [{id_content}] {event_name}")
    logger.info(f"  {len(urls)} URLs cần cào")

    raw_results  = []   # [{ url, raw_post_text, comments }]
    all_comments = []   # Gộp comments từ tất cả URLs

    # ── Cào từng URL ──
    order_offset = 0
    for i, url in enumerate(urls, start=1):
        logger.info(f"\n  URL {i}/{len(urls)}")
        retries = 0
        result  = None

        while retries < config.MAX_RETRIES:
            try:
                result = scraper.scrape_url(page, url, post_id,order_offset)
                break
            except Exception as e:
                retries += 1
                logger.error(f"  Lỗi scrape URL (lần {retries}): {e}")
                if retries >= config.MAX_RETRIES:
                    logger.error(f"  Bỏ qua URL này sau {retries} lần thất bại.")
                else:
                    page.wait_for_timeout(3000)

        if result:
            raw_results.append({
                "url":           result["url"],
                "raw_post_text": result["raw_post_text"],
                
            })
            all_comments.extend(result["comments"])
            order_offset += len(result["comments"])

    if not raw_results:
        logger.error(f"  Không cào được URL nào cho [{id_content}]. Bỏ qua.")
        return None

    # ── Gọi Gemini tổng hợp ──
    logger.info(f"\n  Tổng hợp nội dung với Gemini...")
    post_content = gemini_summarizer.summarize_posts(event_name, raw_results)

    # ── Build event document ──
    event_doc = {
        "id_content":   id_content,
        "category":     category,
        "event_name":   event_name,
        "post_content": post_content,
        "source_urls":  [r["url"] for r in raw_results],
        "sort_mode":    config.SORT_MODE,
        "comments":     all_comments,
    }

    return event_doc


# ─── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    setup_logging()
    global logger
    logger = logging.getLogger("main")

    # 1. Chọn sheet
    sheet_name = choose_sheet()

    # 2. Đọc tasks từ Google Sheets
    try:
        tasks = read_tasks(sheet_name)
    except Exception as e:
        logger.critical(f"Không đọc được Google Sheets: {e}")
        sys.exit(1)

    if not tasks:
        logger.info("Không có task nào để scrape.")
        return

    # 3. Lọc task đã scrape rồi
    scraped_ids = storage.get_scraped_ids()
    pending = [t for t in tasks if t["id_content"] not in scraped_ids]

    logger.info(f"\nTổng sự kiện có links: {len(tasks)}")
    logger.info(f"Đã scrape trước đó:    {len(scraped_ids)}")
    logger.info(f"Sẽ scrape mới:         {len(pending)}")

    if not pending:
        logger.info("Tất cả sự kiện đã được scrape. Không có gì để làm.")
        return

    # 4. Khởi động browser + đăng nhập
    with sync_playwright() as pw:
        browser = pw.firefox.launch(
            headless=config.HEADLESS,
        )
        context = browser.new_context(
            viewport=config.VIEWPORT,
            user_agent=config.USER_AGENT,
            locale="vi-VN",
        )
        page = context.new_page()

        try:
            auth.ensure_logged_in(page, context)
        except Exception as e:
            logger.critical(f"Không thể đăng nhập Facebook: {e}")
            browser.close()
            sys.exit(1)

        # 5. Scrape từng sự kiện
        success, failed = 0, 0

        for i, task in enumerate(pending, start=1):
            logger.info(f"\n{'='*55}")
            logger.info(f"Task {i}/{len(pending)}")

            try:
                event_doc = process_event(page, task)
                if event_doc:
                    storage.append_event(event_doc)
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Lỗi không mong đợi: {e}")
                failed += 1

        browser.close()

    # 6. Tổng kết
    logger.info(f"\n{'='*55}")
    logger.info(f"Hoàn thành!")
    logger.info(f"  ✓ Thành công: {success} sự kiện")
    logger.info(f"  ✗ Thất bại:  {failed} sự kiện")
    logger.info(f"  Output: {os.path.abspath(config.OUTPUT_FILE)}")


if __name__ == "__main__":
    run()
