"""
Auto-scrape Facebook post comments qua Chrome DevTools Protocol (CDP).

Approach:
  - Connect to existing Chromium via CDP (port 9222)
  - Reuse already-logged-in session (cookies từ user data dir)
  - Navigate current tab tới post URL
  - Scroll để load comments
  - Extract comments bằng JS evaluation qua CDP
  - Save raw JSON
  - Write run manifest + checkpoint (see scripts/_run_manifest.py)

Không cần Playwright/Selenium — chỉ dùng websocket-client + curl.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent))
from _run_manifest import RunManifest, manifest_path, checkpoint_path  # noqa: E402
from _common_schema import (filter_to_post, parse_comment_link,  # noqa: E402
                            to_common_rows, write_common_jsonl)


class BrowserDisconnected(RuntimeError):
    """Raised when the CDP websocket / HTTP endpoint is unreachable.

    Covers the browser app crashing mid-crawl (renderer OOM, system kill,
    segfault) and the tab/page going away. Callers may recover by waiting for
    the browser to come back (or relaunching it) and resuming from checkpoint.
    """

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)


CDP_HTTP = os.environ.get("FB_CDP_HTTP", "http://127.0.0.1:9222")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


CDP_RECV_TIMEOUT = float(os.environ.get("FB_CDP_TIMEOUT", "30"))
BROWSER_DISCONNECT_EXIT_CODE = 75


async def cdp_send(ws, method: str, params: dict = None, msg_id: int = 1):
    """Send CDP command and wait for response.

    Raises BrowserDisconnected if the browser/tab doesn't answer within
    CDP_RECV_TIMEOUT (default 30s, override with FB_CDP_TIMEOUT) or the
    websocket drops — both signal a crashed browser that callers can recover
    from. Without this guard, a wedged tab (e.g. from an aborted Page.navigate)
    leaves the CDP command pipe stuck and the whole crawl hangs forever.
    """
    msg = {"id": msg_id, "method": method, "params": params or {}}
    try:
        await ws.send(json.dumps(msg))
    except Exception as e:
        raise BrowserDisconnected(f"CDP send failed (browser down?): {e}") from e
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=CDP_RECV_TIMEOUT)
        except asyncio.TimeoutError:
            raise BrowserDisconnected(
                f"no CDP response within {CDP_RECV_TIMEOUT}s (browser wedged/crashed?)")
        except websockets.exceptions.ConnectionClosed as e:
            raise BrowserDisconnected(f"CDP connection closed (browser crashed?): {e}") from e
        except Exception as e:
            raise BrowserDisconnected(f"CDP recv failed: {e}") from e
        resp = json.loads(raw)
        if resp.get("method") in {"Inspector.targetCrashed", "Target.targetCrashed"}:
            status = resp.get("params", {}).get("status") or "unknown"
            raise BrowserDisconnected(f"Chrome renderer crashed (status: {status})")
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error: {resp['error']}")
            return resp.get("result", {})
        # Skip events


# ---------------------------------------------------------------------------
# Login-wall handling (logged-out / "Xem thêm trên Facebook" overlay)
# ---------------------------------------------------------------------------
# Facebook renders a fixed-position overlay (form#login_popup_cta_form) on top of
# post content when the session is not authenticated. Empirically (2026-07-12),
# FB STILL renders a PARTIAL comment set behind the wall — a fresh logged-out
# chromium pulled 6 of 10 comments from a public post after dismissing it. So
# dismissing the overlay is now a real (partial) crawl path, not a dead end.
# Cookie auth (see _browser.inject_cookies) remains the way to get the FULL set
# (all comments, not just the top/visible ones FB ships to logged-out sessions).

LOGIN_WALL_JS = """
(function() {
    const form = document.getElementById('login_popup_cta_form');
    if (form && form.offsetParent !== null) return true;  // visible wall
    if (document.querySelector('form[action*="/login/device-based/"]')) return true;
    if (document.querySelector('[role="dialog"] [aria-label="Đăng nhập vào Facebook"], [role="dialog"] [aria-label="Log In to Facebook"]')) return true;
    return false;
})()
"""

DISMISS_WALL_JS = """
(function() {
    const WALL = 'form#login_popup_cta_form, form[action*="/login/device-based/"], '
               + '[role="dialog"], [aria-modal="true"], div[style*="position: fixed"]';
    const form = document.getElementById('login_popup_cta_form')
        || document.querySelector('form[action*="/login/device-based/"]');
    const hasWall = !!form || !!document.querySelector('[role="dialog"]')
        || document.querySelector('div[style*="position: fixed"]');

    // Inject a persistent stylesheet that hides the login overlay. Facebook's
    // React app re-inserts/re-renders the wall, so a one-shot .remove() is
    // undone — instead we hide it via CSS (overlay stays in DOM but is gone
    // visually and for pointer events, exposing content behind it).
    const styleId = '__fb_wall_hide__';
    let style = document.getElementById(styleId);
    if (!style) {
        style = document.createElement('style');
        style.id = styleId;
        document.head.appendChild(style);
    }
    style.textContent = WALL + '{ display:none !important; visibility:hidden !important; '
        + 'pointer-events:none !important; position:static !important; z-index:-9999 !important; }';

    // Keep hiding if FB re-mounts the wall (MutationObserver re-applies the rule).
    if (!window.__fb_wall_observer__) {
        window.__fb_wall_observer__ = new MutationObserver(() => {
            const s = document.getElementById(styleId);
            if (s) s.textContent = WALL + '{ display:none !important; visibility:hidden !important; '
                + 'pointer-events:none !important; position:static !important; z-index:-9999 !important; }';
        });
        window.__fb_wall_observer__.observe(document.documentElement, {childList: true, subtree: true});
    }

    // Release body/html scroll lock.
    if (document.body) { document.body.style.position = ''; document.body.style.overflow = ''; }
    if (document.documentElement) { document.documentElement.style.position = ''; document.documentElement.style.overflow = ''; }

    // Verify the overlay is now visually hidden (offsetParent null) — not removed,
    // but functionally dismissed so content behind is interactable.
    const probe = document.getElementById('login_popup_cta_form')
        || document.querySelector('form[action*="/login/device-based/"]');
    const visuallyGone = !probe || probe.offsetParent === null;
    const behind = (document.body && document.body.innerText || '').trim();
    return {was_wall: hasWall, removed: visuallyGone, behind_text_len: behind.length,
            note: 'wall hidden via CSS (React re-mounts it; CSS persists)'};
})()
"""


async def detect_login_wall(ws, msg_id: int = 1) -> bool:
    """Return True if FB's logged-out login overlay is present."""
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": LOGIN_WALL_JS, "returnByValue": True},
                         msg_id=msg_id)
    return bool(res.get("result", {}).get("value", False))


async def dismiss_login_wall(ws, msg_id: int = 1) -> dict:
    """Remove FB's login overlay via CDP. Returns {was_wall, removed, behind_text_len}."""
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": DISMISS_WALL_JS, "returnByValue": True},
                         msg_id=msg_id)
    val = res.get("result", {}).get("value", {})
    if not isinstance(val, dict):
        return {"was_wall": False, "removed": False, "behind_text_len": 0}
    return val


REEL_COMMENTS_JS = r"""
(function(reelId, clicked) {
    const path = location.pathname.match(/^\/reels?\/(\d+)\/?$/);
    if (!path || path[1] !== reelId) return 'waiting-for-reel';

    const visible = el => {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0
            && rect.bottom > 0 && rect.top < innerHeight
            && getComputedStyle(el).visibility === 'visible';
    };
    const comment = /^(comment by |reply by |bình luận dưới tên |phản hồi bình luận của )/iu;
    const sort = /^(most relevant|all comments|newest|phù hợp nhất|tất cả bình luận|mới nhất)$/iu;
    const composer = /comment|bình luận/iu;
    if (Array.from(document.querySelectorAll('[aria-label]')).some(el =>
            comment.test(el.getAttribute('aria-label')) && visible(el))
        || Array.from(document.querySelectorAll('span')).some(el =>
            sort.test(el.textContent.trim()) && el.querySelector('svg') && visible(el))
        || Array.from(document.querySelectorAll('[contenteditable="true"]')).some(el =>
            composer.test(el.getAttribute('aria-label') || '') && visible(el))) {
        return 'open';
    }
    if (clicked) return 'waiting-for-comments';

    const main = document.querySelector('main, [role="main"]');
    if (!main) return 'waiting-for-reel';
    const label = /^(?:view\s+)?(?:comments?|bình luận)(?:\s*[,(:]|\s*$)/iu;
    const buttons = Array.from(main.querySelectorAll('button, [role="button"]'))
        .filter(el => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true'
            && label.test((el.getAttribute('aria-label') || el.getAttribute('title')
                || el.textContent || '').trim()));
    // The directly navigated Reel is the first card. Avoid scrolling into later Reels.
    buttons.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    if (!buttons.length) return 'waiting-for-button';
    buttons[0].click();
    return 'clicked';
})
"""


async def open_reel_comments(ws, next_id, reel_id):
    clicked = False
    state = "waiting-for-reel"
    for _ in range(15):
        expression = f"{REEL_COMMENTS_JS}({json.dumps(reel_id)}, {json.dumps(clicked)})"
        result = await cdp_send(ws, "Runtime.evaluate",
                                {"expression": expression, "returnByValue": True},
                                msg_id=next_id())
        state = result.get("result", {}).get("value", "evaluation-error")
        if state == "open":
            print("  Reel comment panel: open", flush=True)
            return
        if state == "clicked":
            clicked = True
            print("  Reel comment button: clicked", flush=True)
        await asyncio.sleep(1)
    raise RuntimeError(f"Could not open Reel comment panel ({state})")


async def await_cdp_ready(timeout: float = 300.0, poll: float = 3.0) -> None:
    """Block until the CDP HTTP endpoint (127.0.0.1:9222) answers again.

    Used during crash recovery: after the browser app crashes (or is killed by a
    watchdog and relaunched), the WS is gone but CDP may come back up. This waits
    for it without spinning the CPU.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            with urllib.request.urlopen(f"{CDP_HTTP}/json/version", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        if asyncio.get_event_loop().time() >= deadline:
            raise BrowserDisconnected(f"CDP not ready after {timeout}s (browser never came back)")
        await asyncio.sleep(poll)


def find_main_fb_page(pages) -> Optional[dict]:
    """Pick the main FB page target from a /json listing (type=page).

    We intentionally do NOT require "facebook.com" already in the URL: a fresh
    logged-out/headless session starts on about:blank (or any URL), and we then
    navigate to the post via Page.navigate. Requiring facebook.com here would make
    the crawler fail to attach to a fresh browser. Pick the first type=page tab;
    Page.navigate will move it to the post.
    """
    fb_pages = [p for p in pages if p.get("type") == "page"
                and "facebook.com" in p.get("url", "")]
    if fb_pages:
        return fb_pages[0]
    # Fallback: first page-type target (fresh session on about:blank etc.)
    for p in pages:
        if p.get("type") == "page":
            return p
    return None


def detect_user_data_dir() -> Optional[str]:
    """Best-effort: find the user-data-dir of a running chromium (for relaunch).

    Greps the chromium process cmdline for --user-data-dir=. Returns None if it
    can't be determined (caller should then skip auto-relaunch).
    """
    try:
        out = subprocess.run(["pgrep", "-af", "chromium"], capture_output=True, text=True)
    except Exception:
        return None
    for line in out.stdout.splitlines():
        if "--user-data-dir=" in line:
            # format: <pid> <path> --user-data-dir=/foo ...
            idx = line.find("--user-data-dir=")
            rest = line[idx + len("--user-data-dir="):].strip()
            # take up to next whitespace
            udd = rest.split()[0] if rest.split() else ""
            if udd:
                return udd
    return None


def relaunch_browser(post_url: str, user_data_dir: Optional[str],
                     browser: str = "auto") -> int:
    """Relaunch Chromium (preserving session via user_data_dir) and open post_url.

    Returns the new browser PID. Backs off on failure so a crash-loop doesn't
    hammer the system. Used by the watchdog-style auto-recover path.
    """
    from _browser import BrowserConfig
    cfg = BrowserConfig(name=browser, user_data_dir=user_data_dir or "",
                        port=int(CDP_HTTP.split(":")[-1]), headless=False).resolve()
    args = [cfg["path"]] + cfg["args"] + [post_url]
    log = f"/tmp/fb-browser-{cfg['port']}.log"
    with open(log, "ab") as fh:
        proc = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT,
                                start_new_session=True)
    return proc.pid


async def no_auth_fallback(post_url: str, current_url: str, post_folder,
                           manifest) -> Optional[str]:
    """Best-effort no-auth path when logged-out AND 0 comments rendered.

    Normally the logged-out pipeline (dismiss wall → sort → click-loop → extract)
    already returns the PARTIAL comment set FB renders behind the overlay (verified
    2026-07-12: 6 of 10 comments). This fallback only fires when that rendered ZERO
    comments — then we try FB's lightweight public post-text endpoint (?__a=1) to
    salvage the public post body. Comments are partial logged-out; cookie auth is
    the only path to the full set. Returns the path to the partial raw.json, or None
    if unavailable.
    """
    print("\n⚠ 0 comments. Có thể:")
    print("  - Post không có comments")
    print("  - FB DOM đã thay đổi → snippet selector cần update")
    print("  - Tab không phải post (current URL:", current_url, ")")
    try:
        from _lightweight import try_public_post
        res = try_public_post(post_url)
        if res.available and res.text:
            print("\n→ No-auth fallback (__a=1): got public post text")
            print(f"   {res.text[:200]}")
            out = post_folder / "raw.json"
            out.write_text(
                json.dumps([
                    {"post_url": current_url, "auth": "none",
                     "comments": [], "post_text": res.text}
                ], ensure_ascii=False, indent=2),
                encoding="utf-8")
            # Also write the post-body sidecar for a consistent shape with the
            # success path (so list_posts / downstream readers find it in one place).
            post_json_path = post_folder / "post.json"
            post_body_out = {
                "author": None, "text": res.text, "images": [],
                "timestamp": None, "reactions": None, "comments_count": None,
                "shares": None, "post_url": current_url,
                "scraped_at": datetime.now().isoformat(),
                "source": "no_auth_fallback_?__a=1",
            }
            post_json_path.write_text(
                json.dumps(post_body_out, ensure_ascii=False, indent=2),
                encoding="utf-8")
            manifest.count("comments", 0)
            manifest.count("no_auth_post_text_chars", len(res.text))
            manifest.count("post_text_chars", len(res.text))
            manifest.output("raw", out)
            manifest.output("post_body", post_json_path)
            manifest.output("post_url", current_url)
            manifest.checkpoint({"phase": "done", "round": 0,
                                 "comments_extracted": 0,
                                 "no_auth": True}, persist_every=1)
            manifest.finish(status="partial_no_auth")
            cp = checkpoint_path(post_folder)
            if cp.exists():
                cp.unlink()
            return out
        else:
            print(f"\n→ No-auth fallback unavailable: {res.note}")
            print("  Login required to access this post's content.")
    except Exception as e:
        print(f"\n→ No-auth fallback error: {e}")
    return None


# ---------------------------------------------------------------------------
# Post body extraction (the MAIN post content, not comments)
# ---------------------------------------------------------------------------
# The comment extractor keys on aria-label ^= "Comment by " / "Reply by ". The
# main post is the top [role="article"] that has NEITHER of those labels. We read
# its author (first profile link in the header), the largest dir="auto" text
# block (post message), the permalink timestamp, post-level user images, and a
# best-effort engagement bar (reactions / comments / shares). Every field is
# nullable — a selector miss must never abort the crawl.

# Which [role=dialog] holds the target post. FB keeps several dialogs mounted
# ("Thông báo", ghost dialogs of previously opened posts), so pick the one with the
# most comment articles; else one with a post message; else null (permalink page).
# Shared by post-body and comment extraction so both read the SAME post.
PICK_POST_DIALOG_JS = """
function __pickPostDialog() {
    const CMT = '[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]';
    const dlgs = Array.from(document.querySelectorAll('[role="dialog"]'));
    let best = null, bestN = 0;
    for (const d of dlgs) {
        const n = d.querySelectorAll(CMT).length;
        if (n > bestN) { bestN = n; best = d; }
    }
    return best || dlgs.find(d => d.querySelector('[data-ad-rendering-role="story_message"]')) || null;
}
"""

# Click the post-level "See more" / "Xem thêm" so long posts are captured full.
POST_SEEMORE_JS = PICK_POST_DIALOG_JS + """
(function() {
    let clicked = 0;
    // Only within the main post article (not comment articles)
    const articles = Array.from(document.querySelectorAll('[role="article"]'));
    const postArt = articles.find(a => {
        const al = a.getAttribute('aria-label') || '';
        return !al.startsWith('Comment by ') && !al.startsWith('Reply by ') && !al.startsWith('Bình luận dưới tên ') && !al.startsWith('Phản hồi bình luận của ') && !al.includes(' đáp lại phản hồi của ');
    });
    const scope = __pickPostDialog() || postArt || document;
    scope.querySelectorAll('[role="button"], span, div').forEach(el => {
        const t = (el.textContent || '').trim();
        if (/^(see more|xem thêm|see more…|xem thêm…)$/i.test(t)) {
            try { el.click(); clicked++; } catch(e) {}
        }
    });
    return clicked;
})()
"""

POST_BODY_JS = PICK_POST_DIALOG_JS + """
(function() {
    const USER_IMG = /scontent\\.[^/]+\\.fbcdn\\.net\\/v\\/t(39|45|51)/;
    const SKIP_IMG = /static\\.xx\\.fbcdn\\.net\\/rsrc|images\\.emoji\\.php|lookaside/i;

    // The main post = top article WITHOUT a Comment/Reply aria-label.
    const articles = Array.from(document.querySelectorAll('[role="article"]'));
    let postArt = articles.find(a => {
        const al = a.getAttribute('aria-label') || '';
        return !al.startsWith('Comment by ') && !al.startsWith('Reply by ') && !al.startsWith('Bình luận dưới tên ') && !al.startsWith('Phản hồi bình luận của ') && !al.includes(' đáp lại phản hồi của ');
    });
    // Fallback: article with the longest text (posts usually longest on a permalink)
    if (!postArt && articles.length) {
        postArt = articles.slice().sort((a, b) =>
            (b.innerText || '').length - (a.innerText || '').length)[0];
    }
    // Post opened as a modal: the post is NOT a labelled article and the feed
    // behind holds empty ghost articles, so scope to the post dialog instead.
    const dlg = __pickPostDialog();
    const scope = dlg || postArt || document.body;

    // Author: prefer header link (h2/h3/strong), else first profile link.
    let author = null, profileUrl = null;
    const hdr = scope.querySelector('[data-ad-rendering-role="profile_name"] a, h2 a, h3 a, strong a');
    if (hdr && (hdr.textContent || '').trim()) {
        author = hdr.textContent.trim();
        profileUrl = hdr.href.split('?')[0];
    }
    const links = author ? [] : scope.querySelectorAll('a[href*="facebook.com/"], a[role="link"][href]');
    for (const link of links) {
        const txt = (link.textContent || '').trim();
        if (txt && txt.length >= 2 && txt.length < 60
            && !/^(Xem|View|Thêm|More|Like|Thích|Reply|Trả lời|Share|Chia sẻ|Comment|Bình luận|\\d)/i.test(txt)) {
            author = txt;
            profileUrl = link.href.split('?')[0];
            break;
        }
    }

    // Post text: largest dir="auto" block inside the article (post message).
    let text = null;
    let maxLen = 0;
    scope.querySelectorAll('[data-ad-rendering-role="story_message"]').forEach(div => {
        const t = (div.innerText || '').trim();
        if (t.length > maxLen && t.length < 20000) { maxLen = t.length; text = t; }
    });
    if (!text) scope.querySelectorAll('div[dir="auto"]').forEach(div => {
        // Skip blocks that live inside a nested comment article
        const inComment = div.closest('[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]');
        if (inComment) return;
        const t = (div.textContent || '').trim();
        if (t.length > maxLen && t.length >= 2 && t.length < 20000) {
            maxLen = t.length;
            text = t;
        }
    });

    // Timestamp: permalink-style link (posts/permalink/story) with time text/title.
    let timestamp = null;
    const timeLink = scope.querySelector(
        'a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"], abbr, time');
    if (timeLink) {
        timestamp = (timeLink.getAttribute('title') || timeLink.getAttribute('aria-label')
            || timeLink.textContent || '').trim() || null;
    }

    // Post-level user images (filter FB UI assets + emoji sprites).
    let images = [];
    if (INCLUDE_IMAGES) {
        const seenSrc = new Set();
        scope.querySelectorAll('img').forEach(img => {
            const src = img.src || '';
            if (!src.startsWith('https')) return;
            if (SKIP_IMG.test(src)) return;
            if (!USER_IMG.test(src)) return;
            // Skip images inside comment articles
            if (img.closest('[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]')) return;
            if (seenSrc.has(src)) return;
            seenSrc.add(src);
            images.push({src: src.split('?')[0], alt: (img.alt || '').substring(0, 200)});
        });
        images = images.slice(0, 20);
    }

    // Engagement bar: best-effort counts from aria-labels / text.
    let reactions = null, comments_count = null, shares = null;
    const grabNum = (re) => {
        for (const el of scope.querySelectorAll('[aria-label], span')) {
            const s = (el.getAttribute('aria-label') || el.textContent || '').trim();
            const m = s.match(re);
            if (m) return m[1];
        }
        return null;
    };
    reactions = grabNum(/([\\d.,KMBkmb]+)\\s*(?:reactions?|người|cảm xúc)/i);
    comments_count = grabNum(/([\\d.,KMBkmb]+)\\s*(?:comments?|bình luận)/i);
    shares = grabNum(/([\\d.,KMBkmb]+)\\s*(?:shares?|lượt chia sẻ|chia sẻ)/i);

    return {
        author: author,
        profile_url: profileUrl,
        text: text ? text.substring(0, 20000) : null,
        timestamp: timestamp,
        images: images,
        reactions: reactions,
        comments_count: comments_count,
        shares: shares,
        post_url: window.location.href,
        scraped_at: new Date().toISOString(),
    };
})()
"""


async def extract_post_body(ws, next_id, include_images: bool = True) -> dict:
    """Extract the main post content (author, text, images, engagement) from DOM.

    Best-effort: any CDP/JS failure returns a minimal dict rather than aborting
    the crawl. Clicks the post-level "See more" first so long posts are full.
    """
    # Expand post-level "See more" (best-effort)
    try:
        await cdp_send(ws, "Runtime.evaluate",
                       {"expression": POST_SEEMORE_JS, "returnByValue": True},
                       msg_id=next_id())
        await asyncio.sleep(1.0)
    except (BrowserDisconnected, RuntimeError):
        pass
    js = f"var INCLUDE_IMAGES = {str(include_images).lower()};\n{POST_BODY_JS}"
    try:
        res = await cdp_send(ws, "Runtime.evaluate",
                             {"expression": js, "returnByValue": True},
                             msg_id=next_id())
        val = res.get("result", {}).get("value", {})
        if isinstance(val, dict):
            return val
    except (BrowserDisconnected, RuntimeError) as e:
        print(f"  ⚠ Post-body extract skipped (best-effort): {e}")
    return {"author": None, "text": None, "images": [], "post_url": None,
            "scraped_at": datetime.now().isoformat()}


async def navigate_and_scrape(post_url: str, max_scrolls: int = 5, target: int = 0,
                             max_rounds: int = 50, click_pause: float = 4.0,
                             sort_all: bool = True, include_images: bool = True,
                             include_post_body: bool = True,
                             cookie_file: Optional[str] = None,
                             cookie_string: Optional[str] = None,
                             cookie_domain: str = ".facebook.com",
                             dismiss_login_wall_flag: bool = False,
                             manifest: Optional[RunManifest] = None,
                             user_data_dir: Optional[str] = None,
                             browser: str = "auto",
                             crash_retries: int = 3,
                             crash_wait: float = 15.0,
                             relaunch: bool = True,
                             event_id: Optional[str] = None):
    """Navigate tab tới post URL, scroll, extract comments.

    cookie_file / cookie_string: optional auth via cookies (injected via CDP).
    If neither provided, assumes browser already has logged-in session.
    manifest: optional RunManifest for audit + resume. If None, creates one.
    """
    # Pre-resolve post folder so checkpoint paths work throughout the function
    from _data_paths import post_dir as _post_dir, sanitize_url as _sanitize_url
    _post_folder = _post_dir(post_url)
    if manifest is None:
        manifest = RunManifest(
            _post_folder,
            script="05_auto_scrape_cdp.py",
            input_url=post_url,
            input_args={
                "target": target, "max_rounds": max_rounds,
                "click_pause": click_pause, "sort_all": sort_all,
                "include_images": include_images,
                "include_post_body": include_post_body,
            },
        )

    # Cookie injection (if provided)
    if cookie_file or cookie_string:
        # Need to do this BEFORE finding the tab (so we can use the WS to inject)
        pass  # Handled below after we get the WS

    # Get list of pages (raises BrowserDisconnected if the browser app is down)
    try:
        with urllib.request.urlopen(f"{CDP_HTTP}/json") as r:
            pages = json.loads(r.read())
    except BrowserDisconnected:
        raise
    except Exception as e:
        raise BrowserDisconnected(f"CDP unreachable (browser down?): {e}") from e

    # Find main FB page (type=page, không phải iframe/worker)
    main_page = find_main_fb_page(pages)

    if not main_page:
        print("❌ Không tìm thấy tab Facebook. Đảm bảo đã mở browser và login.")
        return None

    ws_url = main_page["webSocketDebuggerUrl"]
    current_url = main_page["url"]
    print(f"✓ Connected to tab: {current_url}")

    try:
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            msg_id = 0

            def next_id():
                nonlocal msg_id
                msg_id += 1
                return msg_id

            # 0.5 Inject cookies (if provided)
            if cookie_file or cookie_string:
                from _browser import parse_cookie_file, parse_cookie_string, inject_cookies
                try:
                    if cookie_file:
                        cookies = parse_cookie_file(cookie_file)
                        print(f"\n→ Injecting {len(cookies)} cookies from file: {cookie_file}")
                    else:
                        cookies = parse_cookie_string(cookie_string, domain=cookie_domain)
                        print(f"\n→ Injecting {len(cookies)} cookies from string (domain: {cookie_domain})")
                    # Navigate to a neutral page first to be able to set cookies
                    await cdp_send(ws, "Page.navigate",
                                   {"url": "https://www.facebook.com/"},
                                   msg_id=next_id())
                    await asyncio.sleep(2)
                    # Now inject cookies
                    success = await inject_cookies(ws, cookies, default_domain=cookie_domain)
                    print(f"  ✓ Injected {success}/{len(cookies)} cookies")
                except Exception as e:
                    print(f"  ⚠ Cookie injection failed: {e}")

            # 1. Navigate tới post URL
            print(f"\n→ Navigate to: {post_url}")
            await cdp_send(ws, "Page.enable", msg_id=next_id())
            await cdp_send(ws, "Page.bringToFront", msg_id=next_id())  # hidden tab => FB stops lazy-loading
            # bringToFront does not restore a MINIMIZED window, and a minimized window
            # keeps visibilityState=hidden -> FB stops loading comments (~30 instead of
            # hundreds, seen 2026-11-19). Un-minimize it (best-effort).
            try:
                win = await cdp_send(ws, "Browser.getWindowForTarget", msg_id=next_id())
                await cdp_send(ws, "Browser.setWindowBounds",
                               {"windowId": win["windowId"], "bounds": {"windowState": "normal"}},
                               msg_id=next_id())
            except (BrowserDisconnected, RuntimeError, KeyError) as e:
                print(f"  ⚠ Could not restore browser window (best-effort): {e}")
            # Tall viewport: in a short post dialog FB hides "View N replies" buttons (height 0) and virtualizes harder.
            await cdp_send(ws, "Emulation.setDeviceMetricsOverride",
                           {"width": 1280, "height": 2400, "deviceScaleFactor": 1, "mobile": False}, msg_id=next_id())
            await cdp_send(ws, "Page.navigate",
                           {"url": post_url},
                           msg_id=next_id())

            # Đợi page load
            await asyncio.sleep(8)
            print("✓ Page loaded")
            current_url = post_url  # the tab's previous URL is irrelevant from here on

            # 1.1 Share links (/share/p/...) redirect via the home feed: while FB resolves
            # them, OTHER posts of the feed are on screen and got crawled instead (seen
            # 2026-11-19). Wait for the real post URL, then open it directly.
            if "/share/" in post_url:
                resolved = None
                for _ in range(20):
                    r = await cdp_send(ws, "Runtime.evaluate",
                                       {"expression": "location.href", "returnByValue": True},
                                       msg_id=next_id())
                    href = r.get("result", {}).get("value") or ""
                    if "/share/" not in href and re.search(
                            r"/posts/|/permalink|story_fbid=|/videos/|/reel/|/photo", href):
                        resolved = href.split("#")[0]
                        break
                    await asyncio.sleep(1)
                if resolved:
                    print(f"→ Share link resolved to: {resolved}")
                    await cdp_send(ws, "Page.navigate", {"url": resolved}, msg_id=next_id())
                    await asyncio.sleep(8)
                    current_url = resolved
                else:
                    print("  ⚠ Share link did not resolve to a post URL within 20s — "
                          "results may include other posts (filtered by post_id below)")

            # 1.4 Login-wall handling (logged-out session)
            # FB renders a "Xem thêm trên Facebook" overlay on top of post content when
            # not authenticated. Historically we claimed comments are NEVER returned
            # logged-out, but empirical testing (2026-07-12, post pfbid0Gm873NgfCnzgP)
            # shows FB DOES render a partial comment set (top/visible comments) behind
            # the wall: a fresh logged-out chromium pulled 6 of 10 comments after
            # dismissing the overlay. So the correct behavior is: dismiss the wall,
            # extract whatever FB rendered (a PARTIAL set), save it, but FLAG it as
            # partial — a logged-in session returns the full set. We no longer bail to
            # the __a=1 text-only fallback before even trying extraction.
            wall_dismissed = False
            if dismiss_login_wall_flag:
                manifest.stage("login_wall_check")
                wall_present = await detect_login_wall(ws, msg_id=next_id())
                if wall_present:
                    print("\n→ Login wall detected — dismissing overlay...")
                    result = await dismiss_login_wall(ws, msg_id=next_id())
                    print(f"  Dismissed: {result.get('removed')} "
                          f"(text behind: {result.get('behind_text_len')} chars)")
                    print("  ⚠ Logged-out: only the partial comment set FB renders "
                          "behind the wall is available (no session → no full set).")
                    wall_dismissed = True
                    await asyncio.sleep(1)
                else:
                    print("\n→ No login wall present")

            # When the login wall was dismissed we are logged-out. FB still renders a
            # partial comment set behind the overlay, so we proceed with sort/click/
            # extract — but we do NOT claim "success": the run is flagged partial at the
            # end so the operator knows a logged-in session yields the full set.
            # (Previously this branch bailed to the __a=1 text-only fallback; that was
            # wrong — it discarded the real comments FB had already rendered.)

            # 1.5 Switch sort to "All comments" (FB default is "Most relevant" — caps at ~60)
            # FB renders "Most relevant" + "Newest" + "All comments" options in a menuitem dropdown.
            # Trigger is a span with current sort name + chevron SVG.
            # Menuitem has format "All commentsShow all comments, including potential spam."
            manifest.stage("navigate", meta={"url": post_url})
            manifest.start()
            reel = re.fullmatch(r"/reels?/(\d+)/?", urlsplit(current_url).path)
            if reel:
                manifest.stage("reel_comments")
                await open_reel_comments(ws, next_id, reel[1])
            if sort_all:
                manifest.stage("sort_switch")
                print("\n→ Switching comment sort to 'All comments'...")
                sort_switch_js = """
                (function() {
                    const trigger = Array.from(document.querySelectorAll('span')).find(s => {
                        const t = (s.textContent || '').trim();
                        return /^(most relevant|all comments|newest|phù hợp nhất|tất cả bình luận|mới nhất)$/i.test(t) && s.querySelector('svg');
                    });
                    if (!trigger) return 'NO_TRIGGER';
                    trigger.click();
                    // Defer the menuitem click so FB's dropdown has time to render.
                    // No async/await + awaitPromise — that pattern wedges the CDP pipe
                    // on some FB DOM states (esp. fresh logged-out sessions) and blocks
                    // all subsequent commands on the session.
                    setTimeout(() => {
                        const items = document.querySelectorAll('[role="menuitem"]');
                        for (const el of items) {
                            const t = (el.textContent || '').trim();
                            if (t.startsWith('All comments') || t.startsWith('Tất cả bình luận')) { el.click(); break; }
                        }
                    }, 900);
                    return 'CLICKED_TRIGGER';
                })()
                """
                # Best-effort: a wedged/errored sort switch must NOT abort the crawl.
                try:
                    res = await cdp_send(ws, "Runtime.evaluate",
                                         {"expression": sort_switch_js, "returnByValue": True},
                                         msg_id=next_id())
                    result = res.get("result", {}).get("value", "?")
                    print(f"  Sort switch: {result}")
                except (BrowserDisconnected, RuntimeError) as e:
                    print(f"  ⚠ Sort switch skipped (best-effort): {e}")
                await asyncio.sleep(6)

                # Verify (also best-effort — never abort on this)
                try:
                    res = await cdp_send(ws, "Runtime.evaluate",
                                         {"expression": """(function() {
                                             const span = Array.from(document.querySelectorAll('span')).find(s => {
                                                 const t = (s.textContent || '').trim();
                                                 return /^(most relevant|all comments|newest|phù hợp nhất|tất cả bình luận|mới nhất)$/i.test(t) && s.querySelector('svg');
                                             });
                                             return span ? span.textContent.trim().substring(0, 30) : 'NONE';
                                         })()""", "returnByValue": True},
                                         msg_id=next_id())
                    current_sort = res.get("result", {}).get("value", "?")
                    print(f"  Current sort: {current_sort}")
                except (BrowserDisconnected, RuntimeError) as e:
                    print(f"  ⚠ Sort verify skipped (best-effort): {e}")
            else:
                print("\n→ Skipping sort switch (sort_all=False)")

            # 1b. Extract the MAIN post body (author, text, images, engagement).
            # Done once after wall handling + sort switch — the post article is
            # already rendered. Best-effort; never aborts the comment crawl.
            manifest.stage("post_body")
            post_body: dict = {}
            if include_post_body:
                print("\n→ Extracting post body (author / text / images / engagement)...")
                pb = await extract_post_body(ws, next_id, include_images=include_images)
                post_body = pb or {}
                ptxt = (post_body.get("text") or "").strip()
                print(f"  Post author : {post_body.get('author')}")
                print(f"  Post text   : {len(ptxt)} chars"
                      + (f" (images: {len(post_body.get('images', []))})" if post_body.get("images") else ""))
            else:
                print("\n→ Post-body extraction skipped (--no-post-body)")

            # 2. Click "View N replies" AND "View more comments" buttons iteratively.
            # Runs on the partial logged-out set FB rendered behind the wall too.
            # NOTE: logged-out FB paginates top-level comments behind a "View more
            # comments" button — must click it repeatedly or you only get the first
            # ~3. Matching replies alone caps the crawl far below the real count.
            # FB virtualizes the comment list (off-screen comments leave the DOM), so a single
            # extract at the end only sees the last window. Extract every round and merge.
            extract_js = """
            (function() {
                const results = [];
                const seen = new Set();

                // URL patterns for user-uploaded images
                // FB UI assets (static.xx.fbcdn.net/rsrc.php) and emoji sprites are excluded
                const USER_IMG = /scontent\\.[^/]+\\.fbcdn\\.net\\/v\\/t(39|45|51)/;
                const SKIP_IMG = /static\\.xx\\.fbcdn\\.net\\/rsrc|images\\.emoji\\.php|lookaside/i;

                const LABEL_SEL = '[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]';
                // Post opened as a modal: the page behind it shows OTHER posts (feed,
                // the user's own post...). Read only the post dialog; filter_to_post()
                // in Python drops anything that still leaks in.
                const scopeRoot = __pickPostDialog() || document;

                // Find ALL elements with comment/reply aria-label
                const allCandidates = scopeRoot.querySelectorAll('[aria-label]');
                allCandidates.forEach(el => {
                    const al = el.getAttribute('aria-label');
                    if (!al || !(/^(Comment by |Reply by |Bình luận dưới tên |Phản hồi bình luận của )/.test(al) || al.includes(' đáp lại phản hồi của '))) return;

                    const isReply = al.startsWith('Reply by') || al.startsWith('Phản hồi bình luận của ') || al.includes(' đáp lại phản hồi của ');
                    let name = null, timeStr = null, replyToAuthor = null;

                    let vm;
                    // Vietnamese UI: "Bình luận dưới tên X vào 32 tuần trước" /
                    //                "Phản hồi bình luận của P dưới tên X vào 32 tuần trước"
                    // Nested reply (reply to a reply): "X đáp lại phản hồi của Y vào 32 tuần trước"
                    if ((vm = al.match(/^(.+?) đáp lại phản hồi của (.+?) vào (.+)$/))) {
                        name = vm[1].trim(); replyToAuthor = vm[2].trim(); timeStr = vm[3].trim();
                    } else if ((vm = al.match(/^Bình luận dưới tên (.+?) vào (.+)$/))
                        || (vm = al.match(/^Phản hồi bình luận của .+? dưới tên (.+?) vào (.+)$/))) {
                        name = vm[1].trim(); timeStr = vm[2].trim();
                    } else if (isReply) {
                        // Format variants:
                        //   "Reply by Tiên Kim to Kin Đẹp Trai's comment 12 hours ago"
                        //   "Reply by Cuong Quach to Đậu Đậu's reply a week ago"
                        const m = al.match(/^Reply by (.+?) to (.+?)'s (comment|reply) (.+)$/);
                        if (m) {
                            name = m[1].trim(); timeStr = m[4].trim();
                            if (m[3] === 'reply') replyToAuthor = m[2].trim();  // nested reply
                        }
                    } else {
                        // "Comment by Kin Đẹp Trai 12 hours ago"
                        const rest = al.replace(/^Comment by /, '');
                        // Match "N units ago" or "a unit ago" or "yesterday" or "just now"
                        const m = rest.match(/^(.+?)((?:\\d+\\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\\s+ago|a\\s+(?:second|minute|hour|day|week|month|year)\\s+ago|just\\s+now|yesterday))$/i);
                        if (m) { name = m[1].trim(); timeStr = m[2].trim(); }
                    }

                    // Walk up to find container with text (the comment container has dir="auto" divs)
                    let container = el;
                    for (let i = 0; i < 5; i++) {
                        const tdivs = container.querySelectorAll('div[dir="auto"]');
                        if (tdivs.length > 0) break;
                        if (!container.parentElement) break;
                        container = container.parentElement;
                    }
                    const target = container || el;

                    // Get text from dir="auto" divs
                    const textDivs = target.querySelectorAll('div[dir="auto"]');
                    // Join outermost dir="auto" blocks: a reply may split the @mention and
                    // the message body (or several paragraphs) into separate blocks.
                    const parts = [];
                    for (const div of textDivs) {
                        if (div.parentElement && div.parentElement.closest('div[dir="auto"]')) continue;
                        // Walking up may reach sibling comments (e.g. a GIF-only comment has no
                        // own text) — never borrow text owned by another comment article.
                        const owner = div.closest(LABEL_SEL);
                        if (owner && owner !== el) continue;
                        const t = div.textContent.trim();
                        if (t && t.length < 5000) parts.push(t);
                    }
                    let text = parts.join('\\n');
                    if (text.length < 2) text = null;

                    // Extract user-uploaded images (filter FB UI assets + emoji sprites)
                    let imgData = [];
                    let images = [];
                    if (INCLUDE_IMAGES) {
                        const seenSrc = new Set();
                        target.querySelectorAll('img').forEach(img => {
                            const src = img.src || '';
                            if (!src.startsWith('https')) return;
                            if (SKIP_IMG.test(src)) return;
                            if (!USER_IMG.test(src)) return;
                            if (seenSrc.has(src)) return;
                            seenSrc.add(src);
                            imgData.push({
                                src: src.split('?')[0],  // strip query params
                                alt: (img.alt || '').substring(0, 200),
                            });
                        });
                        images = imgData.slice(0, 5);
                    }

                    if (!name) return;
                    // Allow image-only comments (no text but has images) — only if INCLUDE_IMAGES
                    if (!text && images.length === 0) return;

                    // Links owned by THIS comment (not by a nested reply article):
                    //  - timestamp link ("6 ngày") = POST url + ?comment_id=<id> (replies:
                    //    ?comment_id=<parent>&reply_comment_id=<self>) -> preferred: it also
                    //    tells which post the comment belongs to.
                    //  - author profile link (text = author name) only carries the own id.
                    // Parsed into comment_id / reply_to_id / author_id by _common_schema.py.
                    const own = Array.from(target.querySelectorAll('a[href]'))
                        .filter(a => a.closest(LABEL_SEL) === el);
                    const prof = own.find(a => (a.textContent || '').trim() === name);
                    const profileHref = prof ? prof.href : null;
                    const pathOf = h => { try { return new URL(h).pathname; } catch (e) { return null; } };
                    const profPath = prof ? pathOf(prof.href) : null;
                    const withId = own.filter(a => /[?&]comment_id=/.test(a.href || ''));
                    const tsLinks = withId.filter(a => pathOf(a.href) !== profPath);
                    const pick = tsLinks.find(a => /[?&]reply_comment_id=/.test(a.href))
                        || tsLinks[0] || withId[0];
                    const commentHref = pick ? pick.href : null;

                    // Dedupe by author + text (or image placeholder)
                    const key = (isReply ? 'R:' : 'C:') + name + '|' + (text || '[img]').substring(0, 80);
                    if (seen.has(key)) return;
                    seen.add(key);

                    results.push({
                        type: isReply ? 'reply' : 'comment',
                        author: name,
                        time: timeStr,
                        text: text ? text.substring(0, 5000) : null,
                        images: images,
                        scraped_at: new Date().toISOString(),
                        post_url: window.location.href,
                        comment_href: commentHref,
                        profile_href: profileHref,
                        reply_to_author: replyToAuthor,
                    });
                });

                return results;
            })();
            """

            # Wrap extract_js to inject include_images flag at the top
            extract_js_with_flag = (f"var INCLUDE_IMAGES = {str(include_images).lower()};\n"
                                    f"{PICK_POST_DIALOG_JS}\n{extract_js}")
            acc: dict = {}
            partial_path = _post_folder / (
                f"partial-comments-{datetime.now():%Y%m%d_%H%M%S_%f}.json"
            )

            async def _merge_extract():
                r = await cdp_send(ws, "Runtime.evaluate",
                                   {"expression": extract_js_with_flag, "returnByValue": True},
                                   msg_id=next_id())
                for c in (r.get("result", {}).get("value") or []):
                    # FB comment id is the reliable key; author+text only when FB gave no link.
                    k = (parse_comment_link(c.get("comment_href"))["comment_id"]
                         or parse_comment_link(c.get("profile_href"))["comment_id"]
                         or (c.get("type"), c.get("author"), (c.get("text") or "[img]")[:80]))
                    if k not in acc:
                        acc[k] = c
                    else:  # a later pass may see links an earlier pass missed
                        for f in ("comment_href", "profile_href", "reply_to_author"):
                            if c.get(f) and not acc[k].get(f):
                                acc[k][f] = c[f]

            # Scroll the post's OWN comment scroller (or the window) so FB lazy-loads more.
            # The first scrollable div is often the feed behind the dialog (0 comments):
            # scrolling it loads nothing and fakes "at bottom" -> crawl stopped at ~30.
            # Search the whole page: the comment scroller can WRAP the post dialog
            # (not sit inside it). Scrolling clicks nothing, so it cannot open other posts.
            find_scroller_js = """
            function __commentScroller() {
                const CMT = '[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]';
                let sc = null, best = -1;
                for (const e of document.querySelectorAll('div')) {
                    if (e.scrollHeight > e.clientHeight + 80 && e.clientHeight > 100
                        && /auto|scroll/.test(getComputedStyle(e).overflowY)) {
                        const n = e.querySelectorAll(CMT).length;
                        if (n > best) { best = n; sc = e; }
                    }
                }
                return best > 0 ? sc : null;
            }
            """
            scroll_js = find_scroller_js + """(function() {
                const sc = __commentScroller();
                const vis = document.visibilityState;
                if (!sc) {
                    window.scrollBy(0, 600);
                    const de = document.documentElement;
                    return JSON.stringify({mode: 'window', vis, pos: window.scrollY + innerHeight, sh: de.scrollHeight,
                                           bot: window.scrollY + innerHeight >= de.scrollHeight - 5});
                }
                sc.scrollTop = sc.scrollTop + Math.floor(sc.clientHeight * 0.8);
                return JSON.stringify({mode: 'scroller', vis, pos: sc.scrollTop + sc.clientHeight, sh: sc.scrollHeight,
                                       bot: sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 5});
            })()"""

            manifest.stage("click_loop", meta={"max_rounds": max_rounds})
            print("\n→ Expanding comments + replies (View more comments / View N replies)...")
            prev_total = 0
            stable_rounds = 0
            # Read checkpoint from previous interrupted run (if any) so a crash/kill
            # mid click-loop resumes instead of restarting from round 0.
            ckpt = RunManifest.load_checkpoint(_post_folder)
            start_round = 0
            if ckpt and ckpt.phase == "click_loop":
                start_round = ckpt.round
                print(f"  → Resuming click-loop from round {start_round} (previous interrupted run)")
            top_js = find_scroller_js + """(function(){const sc=__commentScroller(); if(sc){sc.scrollTop=0;return 1;} return 0;})()"""
            await cdp_send(ws, "Runtime.evaluate", {"expression": top_js, "returnByValue": True}, msg_id=next_id())
            at_bottom = False
            for round_i in range(start_round, max_rounds):
                # Click all unique "View replies" buttons (track by position)
                # + scroll-into-view first so hidden buttons (width=0) become clickable
                click_js = PICK_POST_DIALOG_JS + """
                (function() {
                    let clicked = 0;
                    const seen = new Set();
                    // Only the post dialog: clicking "Xem thêm bình luận" of a feed post
                    // behind it OPENS that post and navigates away (seen 2026-11-19).
                    const root = __pickPostDialog() || document;
                    // First: scroll all comment containers into view so nested View buttons render
                    root.querySelectorAll('[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]').forEach(el => {
                        try { el.scrollIntoView({block: 'nearest'}); } catch(e) {}
                    });
                    // Then: click all visible + hidden expander buttons —
                    //   replies:  "View 1 reply", "View more replies", "View previous"
                    //   comments: "View more comments", "View previous comments",
                    //             "Xem thêm bình luận" (logged-out top-level pagination)
                    root.querySelectorAll('[role="button"]').forEach(el => {
                        const t = (el.textContent || '').trim();
                        const isReplyBtn = /^view (all )?(\\d+ )?repl/i.test(t)
                            || /^view more repl/i.test(t) || /^view previous/i.test(t)
                            || /^xem (tất cả )?(\\d+ )?(câu trả lời|phản hồi)/i.test(t)
                            || /^xem thêm (câu trả lời|phản hồi)/i.test(t)
                            || /^xem (các )?(câu trả lời|phản hồi) trước/i.test(t);
                        const isCommentBtn = /^view more comment/i.test(t)
                            || /^view previous comment/i.test(t)
                            || /^view \\d+ (more )?comment/i.test(t)
                            || /^xem thêm bình luận/i.test(t)
                            || /^xem các bình luận/i.test(t);
                        if (isReplyBtn || isCommentBtn) {
                            const rect = el.getBoundingClientRect();
                            const key = Math.round(rect.top) + '|' + Math.round(rect.height);
                            // No longer require width > 0 — hidden buttons still clickable via JS
                            if (rect.height > 0 && !seen.has(key)) {
                                seen.add(key);
                                try { el.click(); clicked++; } catch(e) {}
                            }
                        }
                    });
                    return clicked;
                })();
                """
                res = await cdp_send(ws, "Runtime.evaluate",
                                     {"expression": click_js, "returnByValue": True},
                                     msg_id=next_id())
                clicked = res.get("result", {}).get("value", 0)
                await asyncio.sleep(click_pause if click_pause > 3.5 else 3.5)

                # Count comments in DOM
                count_js = """document.querySelectorAll('[aria-label^="Comment by "], [aria-label^="Reply by "], [aria-label^="Bình luận dưới tên "], [aria-label^="Phản hồi bình luận của "], [aria-label*=" đáp lại phản hồi của "]').length"""
                res = await cdp_send(ws, "Runtime.evaluate",
                                     {"expression": count_js, "returnByValue": True},
                                     msg_id=next_id())
                total = res.get("result", {}).get("value", 0)
                print(f"  Round {round_i+1}: clicked={clicked}, total in DOM={total}, collected={len(acc)}")

                await _merge_extract()

                # Preserve collected comments independently of Chrome and the resume counter.
                if (round_i + 1) % 5 == 0:
                    partial_comments = filter_to_post(list(acc.values()), current_url)
                    if target:
                        partial_comments = partial_comments[:target]
                    if partial_comments:
                        partial_tmp = partial_path.with_suffix(".json.tmp")
                        partial_tmp.write_text(json.dumps(partial_comments, ensure_ascii=False),
                                               encoding="utf-8")
                        partial_tmp.replace(partial_path)
                    ckpt_data = {"phase": "click_loop", "round": round_i + 1,
                                 "comments_extracted": total, "clicked": clicked}
                    cp_path = checkpoint_path(_post_folder)
                    tmp = cp_path.with_suffix(".json.tmp")
                    tmp.write_text(json.dumps(ckpt_data, ensure_ascii=False),
                                   encoding="utf-8")
                    tmp.replace(cp_path)

                sres = await cdp_send(ws, "Runtime.evaluate", {"expression": scroll_js, "returnByValue": True},
                                      msg_id=next_id())
                try:
                    sinfo = json.loads(sres.get("result", {}).get("value") or "{}")
                except Exception:
                    sinfo = {}
                at_bottom = bool(sinfo.get("bot"))
                print(f"           scroll={sinfo.get('mode')} {sinfo.get('pos')}/{sinfo.get('sh')} "
                      f"visibility={sinfo.get('vis')}")
                if sinfo.get("vis") == "hidden":
                    print("  ⚠ Tab is hidden (window minimized/covered?) — FB stops loading comments")
                await asyncio.sleep(2.0)  # let FB render the newly scrolled window before extracting
                await _merge_extract()
                if target and len(acc) >= target:
                    print(f"  Reached target ({len(acc)} >= {target} unique), stopping click loop")
                    break
                # A button that never expands (clicked>0 forever) must not spin all rounds:
                # stop after 8 rounds without DOM growth even if something is still "clicked".
                if len(acc) == prev_total:
                    stable_rounds += 1
                    # At the bottom FB may still be fetching the next page: give it 5 rounds.
                    if (at_bottom and stable_rounds >= 5) or stable_rounds >= 15:
                        print("  Stable, stopping click loop")
                        break
                else:
                    stable_rounds = 0
                prev_total = len(acc)

            # 3. Extract comments using aria-label selector (catches both Comment by + Reply by)
            manifest.stage("extract", meta={"target": target})
            print(f"\n→ Extracting comments (target: {target})...")

            await _merge_extract()
            comments = list(acc.values())
            # The whole page is read, so drop comments of other posts (feed behind the
            # dialog, previously opened posts) — matched by the post path in comment links.
            n_before = len(comments)
            comments = filter_to_post(comments, current_url)
            if len(comments) < n_before:
                print(f"  ⚠ Dropped {n_before - len(comments)} comments belonging to other posts")
            if target:
                comments = comments[:target]  # first N in discovery order

            print(f"✓ Extracted {len(comments)} unique comments")

            # Stats
            comments_n = sum(1 for c in comments if c.get("type") == "comment")
            replies_n = sum(1 for c in comments if c.get("type") == "reply")
            authors = set(c.get("author") for c in comments if c.get("author"))
            print(f"  Top-level: {comments_n} | Replies: {replies_n} | Authors: {len(authors)}")

            if not comments:
                # No-auth graceful degradation: only when FB genuinely rendered ZERO
                # comments (rare — usually a partial set comes back even logged-out).
                # Try FB's lightweight public post-text endpoint (__a=1) as a last
                # resort to salvage the public post body, if FB serves it.
                if dismiss_login_wall_flag and not (cookie_file or cookie_string):
                    out = await no_auth_fallback(post_url, current_url, _post_folder, manifest)
                    return out
                return None

            if target and len(comments) < target * 0.8:
                print(f"\n⚠ Got {len(comments)} < target {target}. FB có thể không load hết.")

            # 4. Save raw to post-specific folder
            from _data_paths import post_dir, sanitize_url
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            post_folder = _post_folder  # reuse pre-resolved folder
            # If raw.json exists, save with timestamp suffix (don't overwrite)
            raw_path = post_folder / "raw.json"
            if raw_path.exists():
                raw_path = post_folder / f"raw_{timestamp}.json"
            raw_path.write_text(json.dumps(comments, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            print(f"\n💾 Saved: {raw_path}")
            print(f"  Size: {raw_path.stat().st_size} bytes")
            print(f"  Comments: {len(comments)}")
            print(f"  Post folder: {post_folder}")

            # Shared multi-platform schema (comment_id, event_id, post_id, platform,
            # author_id, reply_to_id, ts, text). Same suffix as raw so reruns don't overwrite.
            common_rows = to_common_rows(comments, event_id, post_url=current_url)
            common_path = write_common_jsonl(
                common_rows, post_folder / raw_path.name.replace("raw", "common", 1)
                .replace(".json", ".jsonl"))
            n_real_id = sum(1 for r in common_rows if not r["comment_id"].startswith("fbh_"))
            print(f"💾 Common schema: {common_path} (FB comment_id: {n_real_id}/{len(common_rows)}, "
                  f"author_id: {sum(1 for r in common_rows if r['author_id'])}, "
                  f"event_id: {event_id or 'MISSING — pass --event-id'})")
            manifest.output("common", common_path)
            manifest.count("common_real_comment_id", n_real_id)

            # Save post body sidecar (additive — raw.json stays a pure comment list)
            post_json_path = post_folder / "post.json"
            pb_text = (post_body.get("text") or "").strip()
            if include_post_body and (pb_text or post_body.get("images")):
                if current_url and not post_body.get("post_url"):
                    post_body["post_url"] = current_url
                post_json_path.write_text(
                    json.dumps(post_body, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                print(f"💾 Post body: {post_json_path} ({len(pb_text)} chars, "
                      f"{len(post_body.get('images', []))} images)")
                manifest.output("post_body", post_json_path)
                manifest.count("post_text_chars", len(pb_text))
                manifest.count("post_images", len(post_body.get("images", [])))
            elif include_post_body:
                print("  ⚠ Post body had no text/images — post.json not written")

            # Record counts + outputs in manifest
            manifest.count("comments", len(comments))
            manifest.count("comments_top_level", comments_n)
            manifest.count("comments_replies", replies_n)
            manifest.count("unique_authors", len(authors))
            manifest.output("raw", raw_path)
            manifest.output("post_url", current_url)

            # Sample
            print(f"\n📋 Sample (first 3):")
            for c in comments[:3]:
                text_preview = (c.get("text") or "[image-only]")[:80].replace("\n", " ")
                print(f"  - [{c.get('type', '?')}] {c.get('author', '?')}: {text_preview}")

            # Finalize manifest. If the login wall was dismissed (logged-out), the
            # comment set is PARTIAL — flag it so the operator knows a logged-in
            # session yields more. Don't claim full "success" for a partial pull.
            final_status = "partial_logged_out" if wall_dismissed else "success"
            manifest.checkpoint({"phase": "done", "round": round_i + 1,
                                 "comments_extracted": len(comments),
                                 "logged_out_partial": wall_dismissed},
                                persist_every=1)
            manifest.finish(status=final_status)
            partial_path.unlink(missing_ok=True)
            if wall_dismissed:
                print(f"\n⚠ SAVED AS PARTIAL (logged-out): {len(comments)} comments. "
                      f"FB reports more — run with cookie auth for the full set.")
            # Clear checkpoint on clean finish so next run doesn't resume
            cp = checkpoint_path(post_folder)
            if cp.exists():
                cp.unlink()

            return raw_path



    except BrowserDisconnected:
        raise

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default=None,
                        help="URL post cần crawl (required, e.g. https://www.facebook.com/share/p/POST_ID/)")
    parser.add_argument("max_scrolls", nargs="?", type=int, default=5,
                        help="(deprecated) Kept for backward compat")
    parser.add_argument("--target", type=int, default=0,
                        help="Target comment count for warning if short")
    parser.add_argument("--max-rounds", type=int, default=50,
                        help="Max click-loop rounds (default 50, each ~4s)")
    parser.add_argument("--click-pause", type=float, default=4.0,
                        help="Seconds between click rounds (default 4.0)")
    parser.add_argument("--no-sort-all", action="store_true",
                        help="Skip switching sort to 'All comments' (default: switch)")
    parser.add_argument("--no-images", action="store_true",
                        help="Skip image extraction from comments (default: extract)")
    parser.add_argument("--no-post-body", action="store_true",
                        help="Skip extraction of the main post body (author/text/images/engagement). "
                             "Default: extract and save data/posts/<slug>/post.json")
    parser.add_argument("--cookie-file", type=str, default=None,
                        help="Path to Netscape/JSON cookie file (injected via CDP)")
    parser.add_argument("--cookie-string", type=str, default=None,
                        help="Raw cookie string (e.g. 'c_user=123; xs=abc')")
    parser.add_argument("--cookie-domain", type=str, default=".facebook.com",
                        help="Cookie domain (default: .facebook.com)")
    parser.add_argument("--dismiss-login-wall", action="store_true",
                        help="Dismiss FB's logged-out login overlay (no-auth crawl). "
                             "Exposes any DOM behind it; comments still need a session. "
                             "Also set FB_DISMISS_LOGIN_WALL=1.")
    parser.add_argument("--browser", type=str, default="auto",
                        help="Browser: auto|chromium|google-chrome|brave|edge|opera (default: auto)")
    parser.add_argument("--user-data-dir", type=str, default=None,
                        help="Chromium user-data-dir (session profile). Used to relaunch "
                             "the browser after a crash, preserving cookies/login. "
                             "If omitted, auto-detected from the running browser.")
    parser.add_argument("--crash-retries", type=int, default=3,
                        help="Times to retry after the browser app crashes mid-crawl "
                             "(default: 3). Waits for CDP, or relaunches via --user-data-dir.")
    parser.add_argument("--crash-wait", type=float, default=30.0,
                        help="Seconds to wait for CDP / browser to come back after a crash "
                             "(default: 30).")
    parser.add_argument("--event-id", type=str, default=None,
                        help="Event id this post belongs to; written to common.jsonl "
                             "(shared schema). Crawler cannot infer it.")
    parser.add_argument("--no-relaunch", action="store_true",
                        help="Don't auto-relaunch the browser on crash; only wait for an "
                             "external watchdog to bring it back.")
    args = parser.parse_args()

    dismiss_wall = args.dismiss_login_wall or os.environ.get("FB_DISMISS_LOGIN_WALL") == "1"

    if not args.url:
        parser.error("URL is required. Usage: python3 scripts/05_auto_scrape_cdp.py <URL> [--target N]")

    if not (args.cookie_file or args.cookie_string):
        print("=" * 60)
        print("FB AUTO-SCRAPE VIA CDP (deep mode v2)")
        print("=" * 60)
    else:
        print("=" * 60)
        print("FB AUTO-SCRAPE VIA CDP (deep mode v2, cookie auth)")
        print("=" * 60)
    print(f"Post URL   : {args.url}")
    print(f"Target     : {args.target or 'no warning threshold'}")
    print(f"Max rounds : {args.max_rounds}")
    print(f"Click pause: {args.click_pause}s")
    print(f"Sort all   : {not args.no_sort_all}")
    print(f"Browser    : {args.browser}")
    print(f"Dismiss wall: {dismiss_wall}")
    print(f"Event id   : {args.event_id or '(none — common.jsonl event_id will be null)'}")
    if args.cookie_file:
        print(f"Cookie file: {args.cookie_file}")
    if args.cookie_string:
        print(f"Cookie str : {args.cookie_string[:50]}...")
    print(f"CDP target : {CDP_HTTP}")
    print("=" * 60)

    # Resolve session profile for relaunch. If the user passed --user-data-dir
    # use it; otherwise try to read it off the running browser's cmdline.
    udd = args.user_data_dir
    if udd is None and not args.no_relaunch:
        udd = detect_user_data_dir()

    # Crash-recovery retry loop. If the browser app crashes mid-crawl,
    # navigate_and_scrape raises BrowserDisconnected. We wait for CDP (a
    # watchdog may have relaunched the browser) or relaunch it ourselves via
    # the session profile, then re-run — it resumes from the click-loop
    # checkpoint (checkpoint.json) instead of restarting from zero.
    result = None
    last_err: Optional[Exception] = None
    for attempt in range(1, args.crash_retries + 2):
        try:
            result = await navigate_and_scrape(
                args.url,
                args.max_scrolls,
                args.target,
                args.max_rounds,
                args.click_pause,
                sort_all=not args.no_sort_all,
                include_images=not args.no_images,
                include_post_body=not args.no_post_body,
                cookie_file=args.cookie_file,
                cookie_string=args.cookie_string,
                cookie_domain=args.cookie_domain,
                dismiss_login_wall_flag=dismiss_wall,
                user_data_dir=udd,
                browser=args.browser,
                crash_retries=0,  # inner retries disabled; this loop owns recovery
                crash_wait=args.crash_wait,
                relaunch=not args.no_relaunch,
                event_id=args.event_id,
            )
            break  # success or a non-crash terminal result (None)
        except BrowserDisconnected as e:
            last_err = e
            print(f"\n⚠ BROWSER CRASHED / DISCONNECTED (attempt {attempt}): {e}")
            if attempt > args.crash_retries:
                break
            # Wait for CDP to come back; if it doesn't and we have a profile,
            # relaunch the browser so navigate_and_scrape can reconnect next pass.
            try:
                await await_cdp_ready(timeout=args.crash_wait, poll=3.0)
                print("  → CDP back. Retrying crawl (resumes from checkpoint)...")
            except BrowserDisconnected:
                if not args.no_relaunch and udd is not None:
                    print(f"  → CDP still down. Relaunching browser (profile: {udd})...")
                    try:
                        relaunch_browser(args.url, udd, browser=args.browser)
                    except Exception as re:
                        print(f"  ⚠ Relaunch failed: {re}")
                    try:
                        await await_cdp_ready(timeout=args.crash_wait, poll=3.0)
                    except BrowserDisconnected:
                        pass
                else:
                    print("  → CDP still down and relaunch disabled; will retry wait.")
            continue
        except Exception as e:
            # Non-crash error: surface and abort (no point retrying).
            last_err = e
            print(f"\n❌ Error: {e}")
            try:
                from _data_paths import post_dir
                mf = RunManifest(post_dir(args.url), script="05_auto_scrape_cdp.py")
                if mf.is_resume or mf.started_at:
                    mf.error(f"{type(e).__name__}: {e}")
                    import traceback as _tb
                    mf.error("traceback", traceback=_tb.format_exc())
                    mf.finish(status="failed")
            except Exception:
                pass
            import traceback
            traceback.print_exc()
            sys.exit(1)

    if result:
        print(f"\n✓ Done. Raw file: {result}")
        print(f"\nNext step: python3 scripts/04_clean_data.py {result}")
    elif last_err is not None:
        # All crash retries exhausted without a successful (or terminal) result.
        print(f"\n❌ Browser crashed and could not be recovered after "
              f"{args.crash_retries} retry(ies): {last_err}")
        try:
            from _data_paths import post_dir
            mf = RunManifest(post_dir(args.url), script="05_auto_scrape_cdp.py")
            if mf.is_resume or mf.started_at:
                mf.error(f"crash recovery exhausted: {last_err}")
                mf.finish(status="failed")
        except Exception:
            pass
        sys.exit(BROWSER_DISCONNECT_EXIT_CODE)


if __name__ == "__main__":
    asyncio.run(main())
