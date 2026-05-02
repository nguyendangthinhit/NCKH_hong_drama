"""
scraper.py
Core scraping logic cho từng URL Facebook.
"""

import re
import os
import logging
from playwright.sync_api import Page

import config
from parser import parse_comment

logger = logging.getLogger(__name__)


# ─── Selectors ───────────────────────────────────────────────────────────────
COMMENT_ITEM_SELECTOR = 'div[role="article"]'

SORT_BUTTON_LABELS = [
    "Sắp xếp bình luận",
    "Sort comments",
]

SORT_RECENT_LABELS = [
    "Tất cả bình luận",
    "All comments",
    "Mới nhất",
    "Most recent",
    "Newest",
]

POPUP_CLOSE_LABELS = [
    "Đóng", "Close",
    "Không phải bây giờ", "Not now",
]

POST_TEXT_SELECTORS = [
    '[data-ad-preview="message"]',
    'div[data-testid="post_message"]',
    '[data-ad-comet-preview="message"]',
    'div[class*="userContent"]',
]

VIDEO_SELECTORS = [
    'video',
    '[data-testid="video-container"]'
]

SPAM_KEYWORDS = [
    "Rất tiếc, đã xảy ra lỗi",
    "butuni.com",
    "fanpage chính thức",
    "free ship",
    "thương lượng",
    "tham khảo tại",
    "inbox mình",
    "ib mình",
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _dismiss_popups(page: Page) -> None:
    for label in POPUP_CLOSE_LABELS:
        try:
            btn = page.query_selector(f'[aria-label="{label}"]')
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass


def _debug_buttons(page: Page) -> None:
    """In ra tất cả button text liên quan đến comments để debug."""
    try:
        all_btns = page.query_selector_all('div[role="button"], span[role="button"]')
        for b in all_btns:
            try:
                t = b.inner_text().strip()
                if t and len(t) < 60 and any(
                    kw in t.lower() for kw in ["xem", "view", "more", "comment", "bình luận", "phản hồi"]
                ):
                    logger.debug(f"    BUTTON TEXT: '{t}'")
            except Exception:
                pass
    except Exception:
        pass
def _filter_comment_articles(page: Page, all_articles) -> list:
    """
    Lọc ra chỉ những article elements thực sự là comments,
    loại bỏ article wrapper của bài post (xuất hiện khi post có ảnh/video).
    Post article nhận diện được vì có cả Share + React + Comment button bên trong,
    và KHÔNG có ancestor ul/li.
    """
    if not all_articles:
        return []

    comment_els = []
    for el in all_articles:
        try:
            is_comment = page.evaluate("""(el) => {
                // Comment article luôn nằm trong ul/li
                let node = el.parentElement;
                let depth = 0;
                while (node && depth < 8) {
                    const tag = node.tagName ? node.tagName.toLowerCase() : '';
                    if (tag === 'li' || tag === 'ul' || tag === 'ol') return true;
                    if (node.getAttribute && node.getAttribute('aria-label') &&
                        (node.getAttribute('aria-label').includes('bình luận') ||
                         node.getAttribute('aria-label').toLowerCase().includes('comment'))) {
                        return true;
                    }
                    depth++;
                    node = node.parentElement;
                }
                // Không có ul/li ancestor → kiểm tra dấu hiệu post article
                const hasShareBtn = el.querySelector('[aria-label*="Chia sẻ"], [aria-label*="Share"]');
                const hasReactBar = el.querySelector('[aria-label*="Thả tim"], [aria-label*="Like"], [aria-label*="React"]');
                const hasCommentBtn = el.querySelector('[aria-label="Bình luận"], [aria-label="Comment"]');
                if (hasShareBtn && hasReactBar && hasCommentBtn) return false;
                return true;
            }""", el)
            if is_comment:
                comment_els.append(el)
        except Exception:
            comment_els.append(el)  # Lỗi JS → giữ lại để an toàn

    return comment_els

def _open_comment_section(page: Page) -> None:
    """Click nút Bình luận để scroll xuống comment section nếu cần."""
    # KHÔNG dùng aria-label="Bình luận" vì match nhầm nút nav/video player
    # Chỉ tìm nút có text dạng "X bình luận" — đây mới là nút mở comment section
    try:
        all_btns = page.query_selector_all('div[role="button"], span[role="button"]')
        for btn in all_btns:
            try:
                text = btn.inner_text().strip()
                if re.match(r'^[\d,.]+[KkMm]?\s*bình luận$', text, re.IGNORECASE):
                    logger.info(f"  Click mở comment section: '{text}'")
                    btn.scroll_into_view_if_needed(timeout=3000)
                    btn.click(timeout=3000)
                    page.wait_for_timeout(3000)
                    return
            except Exception:
                continue
    except Exception:
        pass
# ─── Post content ─────────────────────────────────────────────────────────────

def extract_post_text(page: Page) -> str | None:
    for sel in VIDEO_SELECTORS:
        found = page.query_selector(sel) is not None
        logger.debug(f"  VIDEO selector '{sel}': {found} | url: {page.url}")

    has_video = any(
        page.query_selector(sel) is not None
        for sel in VIDEO_SELECTORS
    )
    if has_video:
        logger.warning("  Post có video → chỉ lấy text, bỏ qua phần video.")

    for sel in POST_TEXT_SELECTORS:
        el = page.query_selector(sel)
        if el:
            text = el.inner_text().strip()
            if text:
                return text

    try:
        og_desc = page.query_selector('meta[property="og:description"]')
        if og_desc:
            content = og_desc.get_attribute("content")
            if content and len(content) > 80:
                return content.strip()
    except Exception:
        pass

    if has_video:
        logger.warning("  Không lấy được text post (có video) → tiếp tục cào comments.")
    else:
        logger.warning("  Không lấy được text post → tiếp tục cào comments.")
    return None


# ─── Sort ─────────────────────────────────────────────────────────────────────

def set_sort_most_recent(page: Page) -> None:
    try:
        sort_btn = None
        for label in SORT_BUTTON_LABELS:
            sort_btn = page.query_selector(f'[aria-label="{label}"]')
            if sort_btn:
                break
        if not sort_btn:
            return

        sort_btn.click()
        page.wait_for_timeout(1000)

        for label in SORT_RECENT_LABELS:
            option = page.query_selector(
                f'[role="menuitemradio"][aria-label*="{label}"]'
            )
            if not option:
                option = page.get_by_text(label).first
            if option:
                option.click()
                logger.info("  Đã set sort → All Comments.")
                page.wait_for_timeout(1500)
                return
    except Exception as e:
        logger.debug(f"set_sort lỗi (không nghiêm trọng): {e}")


def _find_comment_container(page: Page):
    try:
        js_handle = page.evaluate_handle("""() => {
            // Thử cách 1: tìm qua overflow của ancestor
            const articles = document.querySelectorAll('div[role="article"]');
            for (const art of articles) {
                let el = art.parentElement;
                let depth = 0;
                while (el && el !== document.body && depth < 15) {
                    const style = window.getComputedStyle(el);
                    const ov = style.overflowY;
                    if (ov === 'scroll' || ov === 'auto' || ov === 'clip') {
                        return el;
                    }
                    el = el.parentElement;
                    depth++;
                }
            }
            // Thử cách 2: tìm div có scrollHeight > clientHeight (đang bị overflow thật sự)
            const divs = document.querySelectorAll('div');
            for (const div of divs) {
                if (div.scrollHeight > div.clientHeight + 100 && div.clientHeight > 200) {
                    const style = window.getComputedStyle(div);
                    if (style.position !== 'fixed') {
                        return div;
                    }
                }
            }
            return null;
        }""")
        element = js_handle.as_element()
        if element:
            logger.debug("  Tìm thấy comment container qua JS")
            return element
    except Exception as e:
        logger.debug(f"  _find_comment_container lỗi: {e}")
    return None
def load_all_comments(page: Page, post_id: str = "") -> None:
    """
    Scroll xuống liên tục để trigger infinite scroll load comments.
    Facebook không còn nút 'Xem thêm bình luận' — chỉ dùng scroll.
    """
    logger.info("  Đang load toàn bộ comments...")
    prev_count   = 0
    no_new_count = 0
    max_no_new   = 8
    debug_done   = False

    comment_container = _find_comment_container(page)
    logger.debug(f"  comment_container found: {comment_container}")  # ← ĐẶT Ở ĐÂY

    while True:
        # Scroll 1: window chính
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass

        # Scroll 2: comment container (quan trọng nhất)

        if comment_container:
            try:
                page.evaluate(
                    "(el) => el.scrollTo(0, el.scrollHeight)",
                    comment_container
                )
            except Exception:
                comment_container = None  # Stale element → bỏ

        # Scroll 3: kéo comment cuối cùng vào view
        try:
            last_comments = page.query_selector_all(COMMENT_ITEM_SELECTOR)
            if last_comments:
                last_comments[-1].scroll_into_view_if_needed()
        except Exception:
            pass

        # Scroll 4: nhấn End
        try:
            page.keyboard.press("End")
        except Exception:
            pass

        page.wait_for_timeout(config.SCROLL_PAUSE_MS)

        # Click nút "Xem thêm bình luận" nếu vẫn còn (Facebook đôi khi vẫn show)
        try:
            all_btns = page.query_selector_all('div[role="button"], span[role="button"]')
            for btn in all_btns:
                try:
                    t = btn.inner_text().strip()
                    if re.match(r'.*(xem thêm bình luận|view more comments).*', t, re.IGNORECASE):
                        if btn.is_visible():
                            btn.scroll_into_view_if_needed()
                            btn.click(timeout=3000)
                            page.wait_for_timeout(1500)
                            logger.debug(f"  Click nút load more: '{t}'")
                except Exception:
                    continue
        except Exception:
            pass

        # ... (giữ nguyên phần debug screenshot và đếm current)

        page.wait_for_timeout(config.SCROLL_PAUSE_MS)

        # Debug + screenshot lần đầu
        if not debug_done:
            _debug_buttons(page)
            if post_id:
                try:
                    os.makedirs("output", exist_ok=True)
                    page.screenshot(
                        path=f"output/debug_{post_id}.png",
                        full_page=False
                    )
                    logger.debug(f"  Screenshot: output/debug_{post_id}.png")
                except Exception as e:
                    logger.debug(f"  Screenshot lỗi: {e}")
            debug_done = True
        page.wait_for_timeout(config.SCROLL_PAUSE_MS)

        current = len(page.query_selector_all(COMMENT_ITEM_SELECTOR))
        logger.debug(f"  [scroll] current articles: {current}")  # dùng lại biến current
        if current == prev_count:
            no_new_count += 1
            if no_new_count >= max_no_new:
                break
        else:
            no_new_count = 0
            logger.debug(f"    Comments trong DOM: {current}")

        prev_count = current
    logger.debug(f"  comment_container found: {comment_container}")
    logger.info(f"  Load xong. Tổng elements: {prev_count}")


def expand_all_replies(page: Page) -> None:
    """
    Click tất cả nút 'Xem 1 phản hồi' hoặc 'Xem tất cả X phản hồi'.
    Dùng regex để match chính xác, tránh click nhầm nút khác.
    """
    logger.info("  Đang mở rộng replies...")

    for round_n in range(20):
        clicked = 0
        try:
            all_btns = page.query_selector_all('div[role="button"], span[role="button"]')
            for btn in all_btns:
                try:
                    text = btn.inner_text().strip()
                    if re.match(r'^Xem (1|tất cả \d+) phản hồi$', text):
                        if btn.is_visible():
                            btn.scroll_into_view_if_needed(timeout=3000)
                            btn.click(timeout=3000)
                            clicked += 1
                            page.wait_for_timeout(800)
                except Exception:
                    continue
        except Exception:
            pass

        if clicked == 0:
            break
        logger.debug(f"    Round {round_n + 1}: {clicked} nút reply")
        page.wait_for_timeout(config.SCROLL_PAUSE_MS)


# ─── Main scrape function ─────────────────────────────────────────────────────

def scrape_url(page: Page, url: str, post_id: str, order_offset: int = 0) -> dict:
    """
    Scrape 1 URL Facebook.
    Returns: { url, raw_post_text, comments }
    """
    logger.info(f"  → Mở: {url}")
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(7000)
    logger.debug(f"  URL sau goto+wait: {page.url}")
    # Scroll nhẹ để trigger lazy load
    try:
        page.evaluate("window.scrollBy(0, 500)")
    except Exception:
        pass
    page.wait_for_timeout(2000)

    _dismiss_popups(page)

    # Mở comment section nếu cần (video page, post cần click)
    _open_comment_section(page)

    # Lấy text bài post
    raw_post_text = extract_post_text(page)
    logger.debug(f"  URL hiện tại sau extract_post_text: {page.url}")

    # Sort comments
    set_sort_most_recent(page)
    logger.debug(f"  URL hiện tại sau set_sort: {page.url}")

    # Load + expand
    load_all_comments(page, post_id=post_id)
    logger.debug(f"  URL hiện tại sau load_all_comments: {page.url}")


    expand_all_replies(page)

    # Parse comments
    all_article_els = page.query_selector_all(COMMENT_ITEM_SELECTOR)
    comment_els = _filter_comment_articles(page, all_article_els)
    logger.info(f"  Parse {len(comment_els)} comment elements (từ {len(all_article_els)} articles tổng)...")

    comments      = []
    seen_texts    = set()
    order_counter = 1 + order_offset

    for el in comment_els:
        try:
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
        except Exception:
            pass

        parsed = parse_comment(el, post_id, order_counter, url_source=url)
        if not parsed:
            continue

        is_spam = any(kw.lower() in parsed["text"].lower() for kw in SPAM_KEYWORDS)
        if is_spam:
            logger.debug(f"  Skip spam: {parsed['text'][:50]}")
            continue

        if parsed["text"] in seen_texts:
            continue

        seen_texts.add(parsed["text"])
        parsed["order"] = order_counter
        comments.append(parsed)
        order_counter += 1

    logger.info(f"  ✓ {len(comments)} comments hợp lệ")

    return {
        "url":           url,
        "raw_post_text": raw_post_text,
        "comments":      comments,
    }