---
name: facebook-crawl
description: "Crawl Facebook posts, comments, profiles, fanpages, groups via Graph API, Apify, or bash+CDP. Includes the aria-label selector trick, click-loop pattern, scroll-into-view for hidden buttons, sort-switching for full comment set, image extraction, deep comment extraction, page timeline extraction, personal profile crawling, run manifest + resume, bulk mode, and CSV/Parquet export."
version: 3.0.0
author: Facebook Skills Suite
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [facebook, crawl, scraping, social-media, data-collection, cdp, deep-extraction, sort-switch, image-extraction, page-timeline, profile, manifest, bulk, export, parquet]
    related_skills: [facebook-anti-bot, facebook-data-clean, facebook-info-enrichment]
---

# Facebook Crawl

Methodology for collecting Facebook data for marketing intelligence, customer research, and analytics. Covers **source selection**, **deep comment extraction** (the aria-label trick), **pagination**, **output schema**, and **safe pacing**.

## When to use this skill

Load this skill when you need to:
- Collect public posts from a fanpage or group
- Crawl all comments (including nested replies) on a single post
- Pull public profile posts (limited)
- Search public posts by keyword (Facebook Search)
- Crawl Marketplace listings by category/location
- Track engagement metrics (likes, shares, comments count)

DO NOT load this skill if:
- You need private / friends-only data → mostly impossible, skip
- You only need analytics of a page you already own → use Graph API directly
- You need real-time streaming → use webhooks + Graph API

## Logged-out / login-wall handling

Facebook serves a logged-out session a fixed-position overlay
(`<form id="login_popup_cta_form">`, the "Xem thêm trên Facebook" CTA) on top of
post content. To crawl without a manual login:

- **Best path — cookie auth**: export cookies from a logged-in browser
  (`--cookie-file` / `--cookie-string`, see facebook-anti-bot skill) and inject via
  CDP. This is the only way to get the **full** comment set + complete post content.
- **Dismiss overlay** (no-auth, PARTIAL — works): pass `--dismiss-login-wall` (or
  `FB_DISMISS_LOGIN_WALL=1`). The crawler removes the overlay via CDP and then runs
  the normal sort-switch + click-loop + aria-label extraction. Empirically
  (2026-07-12, post `pfbid0Gm873NgfCnzgP…`), FB **does** render a partial comment set
  behind the wall: a fresh logged-out chromium pulled **6 of 10** comments. So you
  DO get real comments logged-out — but only the top/visible ones FB ships to
  unauthenticated sessions, NOT the full set.
- **No-auth fallback**: only when dismiss runs and **0** comments come back (rare),
  the crawler attempts `scripts/_lightweight.py` (`?__a=1` public post-text endpoint)
  to salvage the public post body. Unofficial; may return `LightweightUnavailable`.
- **Output status**: a logged-out run is saved as `partial_logged_out` (not
  `success`) in the manifest, so you know a logged-in session would yield more.

**Important correction (2026-07-12):** the old rule "comments are NEVER returned
logged-out" is FALSE. FB returns a *partial* set logged-out. Cookie auth is still
required for the *full* set (all comments, including deep replies FB hides from
unauthenticated sessions). Don't expect the same count you see while logged in.

**Click-loop must expand top-level comments, not just replies (fixed 2026-07-12):**
logged-out FB paginates top-level comments 3-at-a-time behind a **"View more
comments"** button. The click-loop originally matched only reply expanders
(`view replies` / `view more replies` / `view previous`), so a 24-comment post
yielded only ~4. Fix: also match `view more comments` / `view previous comments` /
`view N (more) comments` / `xem thêm bình luận` / `xem các bình luận`. After the fix
the same post climbed 3→28 DOM nodes → 27 extracted (share/v/1Jfj1vVBRv). The
matcher lives in `05_auto_scrape_cdp.py` click_loop `isCommentBtn`/`isReplyBtn`.

## Core capabilities

- **Source selection**: prioritize Graph API (official) > Apify/Harvest actors > unofficial libraries > playwright/stealth
- **Endpoint discovery**: know which endpoints Graph API allows vs. unofficial routes
- **Deep comment extraction**: the aria-label trick that catches both top-level comments AND nested replies in one selector
- **Click-loop expansion**: iteratively click "View N replies" buttons to expand nested threads
- **Pagination**: cursor-based (Graph API), scroll-based (HTML), `__a=1` JSON trick (unofficial)
- **Schema normalization**: every source maps to one canonical schema
- **Rate limit awareness**: per-endpoint limits, exponential backoff
- **Output formats**: JSONL (default for downstream), CSV, Parquet

## Decision tree: source selection

```
Purpose?
├── My own page (admin) ──────────────► Graph API + Page Access Token
├── Another brand's public page ──────► Graph API (public fields) OR Apify
├── Public group posts ───────────────► Apify OR unofficial /groups/
├── Profile public posts ─────────────► Graph API (limited) + Apify for full
├── Comments of a post ───────────────► Graph API (App Token + post_id) OR deep CDP crawl
├── Marketplace listings ─────────────► Apify /marketplace/ actor (no official API)
├── Search results by keyword ────────► Graph API `search` endpoint (limited) OR Apify
├── Real-time monitor ────────────────► Graph API webhooks (owned resources only)
└── Manual scrape via browser ────────► bash chromium + DevTools console (safest)
```

### Bash chromium approach (manual scrape)

When you need to quickly scrape 1-2 posts without automation (safest for the account):

```bash
# Open chromium via bash, use dedicated user data dir to persist session
bash scripts/01_open_chromium.sh

# Once browser opens:
# 1. Login to Facebook manually
# 2. Navigate to the post you want to scrape
# 3. F12 → Console tab → paste snippet from scripts/03_console_snippets.js
# 4. Snippet auto-scrolls + extracts comments + downloads JSON file
```

**Pros**: No automation → no bot detection trigger. No Playwright/Stealth needed. Safe for personal accounts.

**Cons**: Manual, doesn't scale. One post at a time. Can't automate the pipeline.

### Source priority (by safety & ToS)

1. **Graph API (Meta official)** — safest, full docs, clear rate limits.
   - Need: Facebook App + Access Token (User or Page token)
   - Endpoints: `/v18.0/{page-id}/posts`, `/v18.0/{post-id}/comments`, `/v18.0/search`
2. **Apify / Bright Data actors** — wrapped scrapers with proxy rotation.
   - E.g. `apify/facebook-posts-scraper`, `apify/facebook-comments-scraper`
   - Pricing: pay-per-result. Good for one-shot large crawls
3. **Unofficial libraries** (e.g. `facebook-scraper` Python) — uses hidden HTML endpoint
   - Easy to use but fragile (FB changes often)
   - Risk of rate-limit / checkpoint
4. **Playwright + stealth** — only when the above fail
   - Most complex, easiest for FB to detect
   - Use together with `facebook-anti-bot` skill

## Deep comment extraction (the aria-label trick)

This is the most important lesson learned from real-world testing on a post with 108+ comments. The naive `[role="article"]` selector only catches top-level comments and misses all replies. Here's what actually works:

### The selector that catches EVERYTHING

```javascript
// BOTH top-level comments AND nested replies have these aria-labels:
//   "Comment by <Name> <time>"
//   "Reply by <Name> to <Parent>'s comment|reply <time>"
const allEls = document.querySelectorAll(
  '[aria-label^="Comment by "], [aria-label^="Reply by "]'
);
```

### The full extraction pipeline

```javascript
(function() {
    const results = [];
    const seen = new Set();
    const TIME_REGEX = /^(.+?)((?:\d+\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+ago|a\s+(?:second|minute|hour|day|week|month|year)\s+ago|just\s+now|yesterday))$/i;
    const REPLY_REGEX = /^Reply by (.+?) to .+?'s (?:comment|reply) (.+)$/;

    document.querySelectorAll('[aria-label]').forEach(el => {
        const al = el.getAttribute('aria-label');
        if (!al) return;
        const isReply = al.startsWith('Reply by ');
        if (!isReply && !al.startsWith('Comment by ')) return;

        let name = null, timeStr = null;
        if (isReply) {
            const m = al.match(REPLY_REGEX);
            if (m) { name = m[1].trim(); timeStr = m[2].trim(); }
        } else {
            const rest = al.replace(/^Comment by /, '');
            const m = rest.match(TIME_REGEX);
            if (m) { name = m[1].trim(); timeStr = m[2].trim(); }
        }

        // Get text from dir="auto" divs (walk up if needed)
        let container = el;
        for (let i = 0; i < 5; i++) {
            if (container.querySelectorAll('div[dir="auto"]').length > 0) break;
            if (!container.parentElement) break;
            container = container.parentElement;
        }
        const target = container || el;
        const textDivs = target.querySelectorAll('div[dir="auto"]');
        let text = null;
        for (const div of textDivs) {
            const t = div.textContent.trim();
            if (t && t.length >= 2 && t.length < 5000) { text = t; break; }
        }
        if (!name || !text) return;

        const key = (isReply ? 'R:' : 'C:') + name + '|' + text.substring(0, 80);
        if (seen.has(key)) return;
        seen.add(key);

        results.push({
            type: isReply ? 'reply' : 'comment',
            author: name,
            time: timeStr,
            text: text.substring(0, 5000),
        });
    });

    return results;
})();
```

### The click-loop pattern to expand replies

FB lazy-loads replies. You must click "View N replies" buttons iteratively:

```javascript
// IMPORTANT: scroll-into-view FIRST, then click. Hidden buttons (width=0)
// need to be scrolled into the viewport before FB will render their content.
(function() {
    let clicked = 0;
    const seen = new Set();

    // Step 1: scroll all comment containers into view
    // (forces FB to render nested View buttons that were width=0)
    document.querySelectorAll('[aria-label^="Comment by "], [aria-label^="Reply by "]').forEach(el => {
        try { el.scrollIntoView({block: 'nearest'}); } catch(e) {}
    });

    // Step 2: click all unique "View N replies" buttons
    // Do NOT require width > 0 — hidden buttons are still clickable via JS .click()
    document.querySelectorAll('[role="button"]').forEach(el => {
        const t = (el.textContent || '').trim();
        if (/^view (all )?(\d+ )?repl/i.test(t) || /^view more repl/i.test(t) || /^view previous/i.test(t)) {
            const rect = el.getBoundingClientRect();
            const key = Math.round(rect.top) + '|' + Math.round(rect.height);
            if (!seen.has(key)) {
                seen.add(key);
                try { el.click(); clicked++; } catch(e) {}
            }
        }
    });
    return clicked;
})();
```

Then loop: click → wait 4-5s (longer than 3s for nested FB renders) → check count → repeat until stable (no new comments for 3 rounds). Each round can spawn new "View N replies" buttons inside the just-expanded threads, so iteration is required. **Hard cap**: typically 60 unique comments per session (FB's DOM rendering limit per post).

### Common pitfalls with the aria-label approach

1. **Nested reply chain rendering**: FB renders the same reply multiple times in nested threads (once as direct reply, once as nested). Dedupe by `author + text[:80]` to handle.
2. **Empty text**: some replies are pure emoji or very short. The script requires `text.length >= 2`. Loosen to 1 if needed for emoji-only.
3. **Author with apostrophes**: pattern `'s` in "Reply by X to Y's comment" — the regex uses `'` which matches standard apostrophes. Vietnamese names with diacritics (Đẹp Trai) work fine.
4. **Time format variants**: `"12 hours ago"`, `"a week ago"`, `"5 days ago"`, `"yesterday"`, `"just now"`. The TIME_REGEX handles all.
5. **Reply vs comment label**: top-level replies use `'s comment`, nested replies use `'s reply`. The `(?:comment|reply)` handles both.

### Switching sort to "All comments" (unlock full comment set)

FB's default comment sort is **"Most relevant"** which caps at ~60 comments even when the post has more. To get the full set:

```javascript
(async () => {
    // Step 1: click the sort trigger (span with current sort name + chevron SVG)
    const trigger = Array.from(document.querySelectorAll('span')).find(s => {
        const t = (s.textContent || '').trim();
        return /^(most relevant|all comments|newest)$/i.test(t) && s.querySelector('svg');
    });
    if (!trigger) return 'NO_TRIGGER';
    trigger.click();

    // Step 2: wait for menu to render, then click "All comments"
    await new Promise(r => setTimeout(r, 800));

    for (const el of document.querySelectorAll('[role="menuitem"]')) {
        const t = (el.textContent || '').trim();
        // CRITICAL: use startsWith not exact match — menuitem text contains subtitle
        // e.g. "All commentsShow all comments, including potential spam."
        if (t.startsWith('All comments')) {
            el.click();
            return 'CLICKED: ' + t.substring(0, 50);
        }
    }
    return 'MENU_NOT_FOUND';
})()
```

**Key gotchas**:
- **Don't use exact match** (`===` or `/^All comments$/i`) — menuitem contains BOTH title and subtitle concatenated
- **Wait 800ms** between trigger click and menuitem search — FB menu animates in
- **`\b` (word boundary) doesn't work** between "comments" and "Show" — both start with letter
- **CDP `awaitPromise: true`** is needed — otherwise the await in JS gets `Promise was collected` error, but code still runs

**Expected impact**: +5-15% comments on most posts (post-dependent). Some posts gain 0 (already had full set); others gain 20%+ (heavily spammed).

### Image extraction in comments

Comments can contain user-uploaded images. To capture them:

```javascript
// URL patterns
const USER_IMG = /scontent\.[^/]+\.fbcdn\.net\/v\/t(39|45|51)/;
const SKIP_IMG = /static\.xx\.fbcdn\.net\/rsrc|images\.emoji\.php|lookaside/i;

// Walk to comment container (same as text extraction), then:
const imgData = [];
const seenSrc = new Set();
target.querySelectorAll('img').forEach(img => {
    const src = img.src || '';
    if (!src.startsWith('https')) return;
    if (SKIP_IMG.test(src)) return;       // skip FB UI assets, emoji sprites
    if (!USER_IMG.test(src)) return;      // only user-uploaded
    if (seenSrc.has(src)) return;         // dedupe
    seenSrc.add(src);
    imgData.push({
        src: src.split('?')[0],           // strip query params (signatures)
        alt: (img.alt || '').substring(0, 200),
    });
});
const images = imgData.slice(0, 5);       // cap at 5 per comment
```

**Three URL categories you'll see**:

| Pattern | Type | Action |
|---------|------|--------|
| `scontent.*.fbcdn.net/v/t39.../*.jpg` | User status/timeline image | **KEEP** |
| `scontent.*.fbcdn.net/v/t45.../*` | Open Graph preview | **KEEP** |
| `scontent.*.fbcdn.net/v/t51.../*` | Profile pic / comment thumbnail | **KEEP** (may over-include) |
| `static.xx.fbcdn.net/rsrc.php/*` | FB UI asset (buttons, icons) | FILTER OUT |
| `images.emoji.php/v9/.../16/270d.png` | Emoji sprite | FILTER OUT |
| `lookaside.fbsbx.com/*` | External share preview | FILTER OUT |

**Strip query params**: FB CDN URLs include signatures (`_nc_ohc=...`, `oh=00_AQ...`, `oe=68...`) that expire. Strip `?` and everything after to get canonical URL.

**Allow image-only comments**: change the text check from `if (!text) return` to `if (!text && images.length === 0) return`. Some users post screenshots with no text.

**Schema addition**:
```json
{
  "type": "comment",
  "author": "Duy Nguyen",
  "text": "Adu",
  "images": [
    {
      "src": "https://scontent.fdad1-3.fna.fbcdn.net/v/t39.99422-6/740622227_1037580118688826_6476287021821204912_n.png",
      "alt": "May be an image of text that says 'AI Claude @claudeai X.com'"
    }
  ],
  "scraped_at": "2026-07-08T...",
  "post_url": "..."
}
```

**Important caveat**: FB CDN URLs have TTL signatures. For long-term storage, download images immediately (requires FB auth cookies). Otherwise URLs may expire within days.

### Pagination patterns

### Cursor-based (Graph API)
```python
import requests
def crawl_page_posts(page_id, token, limit=100):
    url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
    params = {"access_token": token, "limit": min(limit, 100),
              "fields": "id,message,created_time,reactions.summary(true),comments.summary(true)"}
    out = []
    while url and len(out) < limit:
        r = requests.get(url, params=params).json()
        out.extend(r.get("data", []))
        url = r.get("paging", {}).get("next")
        params = None  # next URL already contains params
    return out
```

### Scroll-based (HTML)
```javascript
// Loop until DOM stops growing
let prevHeight = 0, stableCount = 0;
for (let i = 0; i < 30; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 2000));
    const h = document.body.scrollHeight;
    if (h === prevHeight) {
        if (++stableCount >= 3) break;
    } else { stableCount = 0; }
    prevHeight = h;
}
```

### `__a=1` JSON trick
URL `https://www.facebook.com/{page-id}/posts/?__a=1` returns JSON instead of HTML. **Unofficial endpoint** — may break at any time.

## Rate limits & safe pacing

| Endpoint | Limit (per hour per token) | Best practice |
|----------|----------------------------|---------------|
| Graph API (App token) | 200 calls/hour | Add jitter 1-3s between calls |
| Graph API (User token) | 200 calls/hour/user | Better for personal data |
| Public data scrape (unofficial) | Not officially documented | Max 1 req / 5-10s, rotate UA |
| Comments crawl (deep) | Per endpoint | Crawl by batch post_id, don't scroll forever |

**Exponential backoff**:
```python
import time, random
def safe_request(url, max_retries=5):
    for attempt in range(max_retries):
        r = requests.get(url)
        if r.status_code == 429:
            wait = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
            continue
        return r
    raise Exception("Rate limit hit too many times")
```

## Step-by-step workflow

### Step 1 — Define source & scope

Before writing code, answer:
- **Business purpose**: marketing analytics? competitor research? lead gen?
- **Estimated volume**: 100 posts / 10K posts / 1M posts?
- **Frequency**: one-shot or recurring (daily/weekly)?
- **Storage target**: local JSONL? Postgres? S3?

### Step 2 — Try Graph API first

```bash
curl -s "https://graph.facebook.com/v18.0/{page-id}?fields=name,fan_count&access_token={TOKEN}" | jq .
```

If Graph API returns enough data → use Graph API. If missing fields (e.g. comments text not exposed for public page) → move to step 3.

### Step 3 — Unofficial route (Python)

```python
from facebook_scraper import get_posts
for post in get_posts('nintendo', pages=3, extra_info=True):
    print(post['post_id'], post['text'][:80], post['likes'])
```

### Step 4 — Deep comment extraction (when Graph API is insufficient)

Use the **aria-label trick** + **click-loop** pattern documented above. Connect via CDP to existing Chromium (see scripts/05_auto_scrape_cdp.py).

### Step 5 — Normalize schema

Every record from every source maps to the canonical schema (see Output schema below).

### Step 6 — Validate & report

```bash
wc -l posts.jsonl
jq -r '.post_id' posts.jsonl | sort | uniq -d | wc -l  # dup count
```

## Output schemas

### Posts schema (canonical)
```json
{
  "post_id": "123456789_987654321",
  "source": "graph_api" | "apify" | "playwright" | "unofficial",
  "page_id": "123456789",
  "author_id": null,
  "author_name": "Nintendo",
  "text": "Join us for...",
  "timestamp": "2026-07-07T10:30:00Z",
  "url": "https://facebook.com/.../posts/...",
  "media_urls": ["https://..."],
  "reactions": {
    "like": 1234, "love": 56, "haha": 7, "wow": 0, "sad": 0, "angry": 0, "total": 1297
  },
  "comments_count": 42,
  "shares_count": 12,
  "raw": {}
}
```

### Comments schema (with deep extraction)
```json
{
  "type": "comment" | "reply",
  "comment_id": "auto-generated-from-key",
  "post_id": "123456789_987654321",
  "parent_comment_id": null,
  "author_id": null,
  "author_name": "...",
  "text": "...",
  "timestamp": "12 hours ago",
  "reactions_total": 5,
  "raw": {}
}
```

### Profile schema (limited public data)
```json
{
  "profile_id": "...",
  "name": "...",
  "bio": "...",
  "category": "...",
  "followers_count": 1234,
  "likes_count": 5678,
  "website": "...",
  "avatar_url": "...",
  "scraped_at": "..."
}
```

### Post body sidecar (`data/posts/<slug>/post.json`)

On every `05_auto_scrape_cdp.py` run, the **main post content** (not comments)
is captured from the live DOM and written to `post.json` (a single dict, kept
separate from `raw.json` so `04_clean_data.py` and `_data_paths.list_posts()`
are untouched). Opt out with `--no-post-body`.

```json
{
  "author": "Page/Person name",
  "profile_url": "https://www.facebook.com/<id>",
  "text": "Full post message (post-level 'See more' expanded). null if image-only.",
  "timestamp": "2026-07-12 14:30",
  "images": [{"src": "https://scontent.../v/t39/...", "alt": "..."}],
  "reactions": "1.2K",
  "comments_count": "10",
  "shares": "3",
  "post_url": "https://www.facebook.com/share/p/<ID>/",
  "scraped_at": "2026-07-13T...Z"
}
```

All fields are best-effort / nullable. The post article is identified as the
top `[role="article"]` WITHOUT a `Comment by` / `Reply by` aria-label, so it
never overlaps the comment set. In the 0-comment no-auth fallback, `post.json`
is still written with `text` salvaged from FB's `?__a=1` endpoint (`source` set
to `"no_auth_fallback_?__a=1"`).

List all crawled posts with post-body availability:
```bash
python3 scripts/_data_paths.py     # shows has_post_body + post_text_chars per post
```

## Bash chromium workflow (manual scrape)

This is the **safest approach for personal accounts**. Open Chromium via bash, login manually, scrape via DevTools console. No automation → no bot detection.

### Step 1 — Open Chromium

```bash
bash scripts/01_open_chromium.sh
# Or with a specific URL:
FB_TARGET_URL="https://www.facebook.com/share/p/1Cvzu3tg2c/" bash scripts/01_open_chromium.sh
```

Chromium opens with a dedicated user data dir (`~/snap/chromium/common/chromium-fb-userdata`) to persist sessions. **Do NOT use `~/.config/`** — AppArmor on snap chromium blocks writes there.

### Step 2 — Login manually

Login to Facebook normally. Pass 2FA if required.

### Step 3 — Navigate to the post

Go to the post URL, e.g. `https://www.facebook.com/share/p/1Cvzu3tg2c/`.

### Step 4 — Scroll to load comments

Scroll down manually, or paste the auto-scroll snippet from `scripts/03_console_snippets.js`.

### Step 5 — Extract comments via DevTools console

1. Press **F12** → **Console** tab
2. Open `scripts/03_console_snippets.js`, copy snippet 1
3. **Paste into console** → Enter
4. Wait 5-30s
5. Browser auto-downloads `fb_comments_<timestamp>.json` to `~/Downloads/`

### Step 6 — Move file to data dir

```bash
mv ~/Downloads/fb_comments_*.json data/
```

Then use `facebook-data-clean` skill to normalize:

```bash
python3 scripts/04_clean_data.py data/fb_comments_xxx.json
```

## Crash recovery & watchdog (browser tự mở lại)

FB crawls run for minutes (click-loop, sort-switch, scrolls). The browser app
can crash mid-run (renderer OOM, segfault, system OOM-kill, manual kill). Two
cooperative mechanisms handle this so a long crawl survives without losing
progress:

### 1. Persistent browser watchdog (`scripts/09_browser_watchdog.py`)
Started by `01_open_browser.sh` when `FB_WATCHDOG=1`. It polls
`http://127.0.0.1:<port>/json/version` every `FB_WATCHDOG_INTERVAL` seconds and
**relaunches Chromium with the SAME flags + SAME user-data-dir** if CDP goes
down — so the session (cookies / login) is preserved. The crawler can then
reconnect.

```bash
# Launch browser WITH watchdog (auto-relaunch on crash)
FB_WATCHDOG=1 FB_WATCHDOG_INTERVAL=5 FB_WATCHDOG_MAX_RESTARTS=50 \
  FB_USER_DATA_DIR="$HOME/snap/chromium/common/chromium-fb-session" \
  bash scripts/01_open_browser.sh

# Stop the watchdog:
touch /tmp/fb-watchdog-<port>.stop
# or: pkill -f 09_browser_watchdog.py
```

Watchdog log: `/tmp/fb-watchdog-<port>.log`. `--max-restarts` guards against a
browser that crashes instantly in a loop (it exits non-zero once exceeded).
For a one-shot "relaunch if down then exit" use `python3 scripts/09_browser_watchdog.py --once`.

### 2. Crawler-side crash recovery (`scripts/05_auto_scrape_cdp.py`)
`cdp_send` raises `BrowserDisconnected` when the WS is closed or CDP stops
answering. `main()` wraps `navigate_and_scrape` in a retry loop:

- On `BrowserDisconnected`, it waits up to `--crash-wait` for CDP to return
  (the watchdog may have relaunched the browser).
- If CDP stays down AND `--user-data-dir` is known, it relaunches the browser
  itself (via `relaunch_browser`), then waits again.
- It re-runs `navigate_and_scrape`, which **resumes from the click-loop
  checkpoint** (`<post_folder>/checkpoint.json`, written every 5 rounds) instead
  of restarting from round 0. The login-wall / no-auth branch returns
  immediately, so a logged-out run never loops forever.

```bash
# Crawl with crash auto-recovery (defaults: 3 retries, 30s wait each)
FB_DISMISS_LOGIN_WALL=1 \
  python3 scripts/05_auto_scrape_cdp.py "https://www.facebook.com/share/p/1PTBu3Hnmh/" \
  --dismiss-login-wall --no-sort-all \
  --crash-retries 3 --crash-wait 30

# If the browser was launched WITHOUT a known profile, tell 05 where it is
# so 05 can relaunch on its own (or rely on the watchdog above):
python3 scripts/05_auto_scrape_cdp.py "<URL>" --user-data-dir "$HOME/snap/chromium/common/chromium-fb-session"

# Disable auto-relaunch (only wait for an external watchdog to bring it back):
python3 scripts/05_auto_scrape_cdp.py "<URL>" --no-relaunch
```

Notes:
- Logged-out crawls: crash recovery still applies, but because FB withholds all
  content without a session, `05` finishes the no-auth fallback on the first pass
  and won't spin on retries.
- `--user-data-dir` is auto-detected from the running browser's cmdline if not
  passed, so you normally don't need it.

## Anti-patterns

- ❌ **Crawl without rate limit** — FB detects quickly, bans account/IP within minutes
- ❌ **Hardcode password/token in code** — use env vars, `.env` files (gitignored)
- ❌ **Crawl 24/7 without rest** — triggers anomaly detection
- ❌ **Ignore `robots.txt` or rate limit headers** — clear bot signal
- ❌ **Save raw HTML 1GB+** — wastes disk, hard to query. Parse before saving
- ❌ **Skip pagination validation** — silent data miss, schema drift
- ❌ **Crawl private / friends-only data** — ToS violation, potentially illegal
- ❌ **Use `[role="article"]` for comments** — misses nested replies; use aria-label instead
- ❌ **Use `(?:\d+ ago|a year ago)` without ` ago` suffix** — fails on "a week ago"
- ❌ **Skip `scrollIntoView` before clicking View buttons** — buttons have `width=0` until scrolled into viewport; naive `rect.width > 0` filter rejects them all
- ❌ **Require `rect.width > 0` for clickable buttons** — same as above; FB renders many clickable buttons off-screen that respond to `.click()` just fine
- ❌ **Assume `bodyHeight > innerHeight` means there's scrollable content** — FB posts are rendered in a scroll-container that may report body height = inner height even when nested content exists

## Pitfalls

1. **Facebook changes DOM often** — unofficial scrapers break weekly. Have a plan B (switch source, Apify fallback)
2. **Access tokens expire** — long-lived tokens still expire ~60 days. Refresh strategy required for recurring crawls
3. **Comments may be hidden / deleted** — handle missing fields gracefully
4. **Unicode / emoji** — text may contain emoji, ZWJ sequences, RTL marks. Use UTF-8 everywhere
5. **Timezones** — Facebook returns UTC ISO8601. Convert to local only for display, store as UTC
6. **Nested reply deduplication** — same reply renders multiple times in nested threads. Dedupe by `author + text[:80]`
7. **Reply vs comment aria-label** — top-level uses `'s comment`, nested uses `'s reply`. Regex must accept both
8. **Scroll vs click** — `window.scrollTo` doesn't trigger FB reply loading. Must click "View N replies" buttons
9. **AppArmor on snap chromium** — can't write to `~/.config/`. Use `~/snap/chromium/common/` for user data dir
10. **Polling vs streaming** — deep comment extraction is one-shot. For real-time, use webhooks
11. **Hidden View buttons (width=0)** — FB renders "View N replies" buttons with `width=0` until scrolled into viewport. Naive `getBoundingClientRect().width > 0` filter rejects them. Use `el.scrollIntoView({block: 'nearest'})` before click loop, OR drop the width filter and rely on position-based dedup.
12. **Hard cap at ~60 unique comments per session** — FB's DOM rendering limit. Even with aggressive clicking, you'll plateau around 50-60 unique comments per post per session. To get more: open multiple sessions with different accounts, or use Graph API (limited to public pages).
13. **No "X comments" count text in DOM** — Facebook doesn't render the total comment count as a leaf text node. Search aria-labels and `<li>` count instead. Cannot verify "we got them all" without external ground truth.
14. **Reply vs reply chain duplicates** — nested replies render multiple times at different DOM depths (once direct, once nested). Dedupe by `author + text[:80]` handles this.
15. **Click-loop stabilizes but DOM still has hidden content** — stable for 3 rounds means "no more clicks succeeded", NOT "all comments loaded". FB may have rendered all it can.

## Changelog

- **v3.1.0**: Crash recovery + watchdog. New `scripts/09_browser_watchdog.py` relaunches Chromium on crash preserving the session (launched by `01_open_browser.sh` with `FB_WATCHDOG=1`). `05_auto_scrape_cdp.py` now detects `BrowserDisconnected` (WS close / CDP timeout) and retries — waiting for CDP or self-relaunching via `--user-data-dir` — then resumes from the click-loop `checkpoint.json`. New flags: `--crash-retries` (default 3), `--crash-wait` (default 30s), `--no-relaunch`, `--user-data-dir`. Fixed click-loop checkpoint write/resume (was gated on a `post_folder`/`_post_folder` typo so it never persisted).
- **v3.0.0** (current): Industrialize — new extractors for fanpage timeline (`08_crawl_page_timeline.py`) and personal profile (`09_crawl_profile.py`, 3-stage with ToS/privacy warnings). Run manifest + checkpoint + resume support via `_run_manifest.py` (integrated into 05/06/07/08/09). Cross-run dedup in `04_clean_data.py --cross-dedup` (hashes normalized cleaned text). CSV/JSON/Parquet export via `_export.py` (15-column flat schema). Schedule runner (`_schedule.py`, YAML config) + audit dashboard (`_audit.py`, scan all manifests for success rate + per-script duration). `fb_cli.py` dispatcher extended with `crawl timeline/profile`, `bulk`, `export`, `schedule`, `audit`, `clean --cross-dedup`.
- **v2.3.0**: Added image extraction for comments. Filters FB UI assets (`static.xx.fbcdn.net/rsrc`) and emoji sprites (`images.emoji.php`); keeps user-uploaded `scontent.*.fbcdn.net/v/t(39|45|51)/...`. Strips query params (signatures expire). Cap at 5 images per comment. Image-only comments now pass through. Added `--no-images` flag to opt out.
- **v2.2.0**: Added sort-switching technique (click "All comments" to bypass FB's 60-comment cap on default "Most relevant" sort). Documented 4 gotchas: startsWith not exact, 800ms wait, `\b` doesn't work between title/subtitle, `awaitPromise: true` for CDP. Added `--no-sort-all` flag to opt-out.
- **v2.1.0**: Added `scrollIntoView` pattern before click loop. Removed `rect.width > 0` filter (was rejecting all hidden buttons). Added `--max-rounds` and `--click-pause` CLI flags. Documented 60-comment hard cap.
- **v2.0.0**: Initial English rewrite with aria-label trick, click-loop pattern.

## Verification commands

```bash
# Schema check — every record must have post_id, timestamp, text
jq -r '.post_id // empty' posts.jsonl | wc -l
jq -r 'select(.post_id == null) | .' posts.jsonl | head

# Volume check
wc -l posts.jsonl
du -h posts.jsonl

# Duplicate check
jq -r '.post_id' posts.jsonl | sort | uniq -d | wc -l

# Date range check
jq -r '.timestamp' posts.jsonl | sort | head -1
jq -r '.timestamp' posts.jsonl | sort | tail -1

# Deep extraction verification
jq -r '.type' comments.jsonl | sort | uniq -c  # should show comment + reply breakdown
```

## Quick start (TL;DR)

### Via Graph API
```python
import os, json, requests
TOKEN = os.environ["FB_ACCESS_TOKEN"]
PAGE_ID = "nintendo"

posts = []
url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/posts"
params = {"access_token": TOKEN, "limit": 100,
          "fields": "id,message,created_time,reactions.summary(true),comments.summary(true),shares"}

while url:
    r = requests.get(url, params=params).json()
    posts.extend(r.get("data", []))
    url = r.get("paging", {}).get("next")
    params = None

with open("posts.jsonl", "w") as f:
    for p in posts:
        f.write(json.dumps(p) + "\n")
```

### Via CDP deep extraction (in scripts/05_auto_scrape_cdp.py)
```python
# Connect to existing Chromium at localhost:9222
# Navigate to post → click-loop "View N replies" → extract via aria-label
result = await navigate_and_scrape(post_url, max_scrolls=5, target=108)
```

## Page timeline extraction (fanpage)

For crawling a fanpage's main timeline (`https://www.facebook.com/<page-slug>/`),
use **`scripts/08_crawl_page_timeline.py`** (or `fb_cli.py crawl timeline <url>`).

**Why a separate script from `06_crawl_group.py`**: Fanpage timeline render
differs from group feed in three ways:

1. **Author is the page itself**, not random user names. Filter via
   `aria-label`/`<strong><a>` and prefer the link whose `href` contains the
   page slug.
2. **Counts prefer `aria-label`** over text: page timeline shows
   `aria-label="1.2K reactions"` while group feed uses both text and ARIA.
3. **Pinned post badge** is unique to pages — flag it as `pinned: true`
   instead of skipping (operators may want to track pinned content separately).

```python
# scripts/08_crawl_page_timeline.py (key JS selector)
const articleSelectors = ['[role="article"]', 'div[data-pagelet*="FeedUnit"]'];
// Skip nav widgets + suggestions
if (/^(suggested for you|people also viewed)/i.test(heading)) return;
// Reactions via aria-label FIRST, then text fallback
const reactAria = article.querySelector('[aria-label*="reaction" i]');
// Pinned detection
const isPinned = /pin(?:ned)? post|bài viết đã ghim/i.test(article.textContent);
```

**Two-step workflow for deep extraction**:
```bash
# Step 1: get post URLs from page timeline
python3 scripts/08_crawl_page_timeline.py https://www.facebook.com/<page-slug> 30
# → raw.json in data/posts/<page-slug>/

# Step 2: for each post URL, deep-extract comments
python3 scripts/05_auto_scrape_cdp.py <post_url> --target 100
# OR batch via bulk mode:
python3 scripts/fb_cli.py bulk post_urls.txt --count 30
```

This 2-step split prevents timeout traps (single huge script that tries to
both find posts and extract their comments).

## Personal profile extraction

For crawling a personal profile (`/people/...`, `/<username>`, or
`/profile.php?id=<id>`), use **`scripts/09_crawl_profile.py`**
(or `fb_cli.py crawl profile <url> --with-about`).

**Three-stage pipeline** (each navigates a different page):

| Stage | URL pattern | Extracts |
|-------|-------------|----------|
| 1. About | `<profile>/about` | bio, current city, work, education, website, contact, join date |
| 2. Posts | `<profile>` (timeline) | post text, reactions/comments counts, media |
| 3. Photos (optional) | `<profile>/photos` | photo URLs + captions (capped at 100) |

```bash
# Full 3-stage
python3 scripts/09_crawl_profile.py https://www.facebook.com/<username> --with-about --with-photos

# Or via dispatcher
python3 scripts/fb_cli.py crawl profile https://www.facebook.com/<username> --with-about --max-posts 20
```

**Critical privacy notes** (read top of `09_crawl_profile.py`):
- Most personal profiles are PRIVATE. Script detects `_private: true` and
  only returns public fields (name + profile URL).
- Even public profiles are PII under GDPR/PDPA/CCPA. Only use with explicit
  authorization (your own profile, research consent, brand ambassador).
- See `skills/facebook-anti-bot/SKILL.md` for the full legal warning.

**About section selector pattern**:
```javascript
// Walk About page; section labels map to keys
const sectionLabels = {
  'current city': 'current_city',
  'work': 'work', 'education': 'education',
  'website': 'website', 'contact email': 'contact_email',
  'joined': 'joined_date', 'relationship': 'relationship',
};
// Look for label-like span text → grab next sibling's value
```

## Run manifest + resume

Every crawl run writes a **manifest** to the post folder
(`data/posts/<slug>/manifest.json`). Captures: run_id, script, input URL,
input args, started/ended timestamps, status, stages, counts, output paths,
errors, warnings.

**Why**: debugging when FB DOM breaks, auditing "what changed", resume after
crash. Without manifests, "the script got 12 comments yesterday and 60 today"
is unanswerable.

```python
# scripts/_run_manifest.py (key API)
from _run_manifest import RunManifest, manifest_path

with RunManifest(post_dir, script="05_auto_scrape_cdp.py",
                 input_url=post_url, input_args={"target": 100}) as m:
    m.stage("navigate")
    m.stage("click_loop")
    for round_i in range(max_rounds):
        m.checkpoint({"phase": "click_loop", "round": round_i,
                      "comments": total}, persist_every=5)
    m.count("comments", 60)
    m.output("raw", raw_path)
    m.finish(status="success")
# On next run, detects interrupted status="running" → resume from last checkpoint
```

**Resume is automatic** for `05_auto_scrape_cdp.py`:
- Checkpoint saved every 5 click-loop rounds to `checkpoint.json`.
- On start, if `manifest.status == "running"`, reads `checkpoint.round` and
  resumes from that round (skips already-done work).
- On clean success, checkpoint is deleted so next run starts fresh.

CLI to inspect:
```bash
# Summary of all manifests
python3 scripts/_run_manifest.py scan data

# Full manifest for one post
python3 scripts/_run_manifest.py show /path/to/manifest.json
```

## Bulk mode + cross-run dedup

For crawling 50+ post URLs at once (e.g. weekly snapshot of a group),
use `scripts/07_crawl_n_posts.py` with `--urls-file <file>` or via
`fb_cli.py bulk <urls_file> --count N`.

**Cross-run dedup** (in `04_clean_data.py --cross-dedup`):
- Loads `text_hash` from all existing `data/posts/*/clean.jsonl` files.
- Hashes the **normalized cleaned text** (so PII redaction + NFC normalization
  don't break the match across runs).
- Skip records whose hash already exists → output goes to quarantine with
  `reason: "cross_run_dup"`.

```bash
# After running the same post twice, second clean with --cross-dedup removes duplicates
python3 scripts/04_clean_data.py data/posts/<slug>/raw.json --cross-dedup
# → cross_dup_removed=N in stats.json
```

Limitations:
- Cross-dedup only scans `clean.jsonl` (stable name), NOT timestamped
  `clean_<ts>.jsonl` files. To enable cross-dedup for a post, re-run
  `04_clean_data.py` to overwrite the stable `clean.jsonl` first.
- Cross-dedup requires the output dir to be inside `data/posts/` (so the
  scan finds it). For ad-hoc output dirs, cross-dedup has no effect.

## Export (CSV / JSON / Parquet)

For analytics teams that need tabular data, use `scripts/_export.py`:

```bash
# CSV (default output: <input>.csv)
python3 scripts/_export.py data/posts/<slug>/clean.jsonl csv

# JSON array (for direct loading)
python3 scripts/_export.py data/posts/<slug>/clean.jsonl json

# Parquet (for pandas/dbt, requires pyarrow)
pip install pyarrow
python3 scripts/_export.py data/posts/<slug>/clean.jsonl parquet
```

**Flat schema** (15 columns) — see `_export.py:CSV_COLUMNS`:
- `record_id` — stable SHA-256 prefix of (post_url|author|text[:80])
- `text`, `author`, `type` (comment/reply), `post_url`
- `time_iso` — ISO parse of `timestamp_raw` (null if relative like "12 hours ago")
- `n_images`, `image_urls` (pipe-separated), `parent_comment_id`
- `reactions_total`, `scraped_at`, `source_file`

**When NOT to use export**: For downstream enrichment (`facebook-data-clean`),
keep the original JSONL — it preserves nested fields that CSV flattens away.

Via dispatcher:
```bash
python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl csv
python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl parquet out.parquet
```

## Schedule + audit

**Schedule** (`scripts/_schedule.py`): YAML config + on-demand runs.
```bash
python3 scripts/fb_cli.py schedule add daily_nintendo timeline \
    https://www.facebook.com/Nintendo 30
python3 scripts/fb_cli.py schedule list
python3 scripts/fb_cli.py schedule run daily_nintendo
```
Wrap with system cron / systemd timer:
```cron
0 9 * * * cd /home/enzo/Documents/Facebook && python3 scripts/fb_cli.py schedule run daily_nintendo >> /var/log/fb-crawl.log 2>&1
```

**Audit** (`scripts/_audit.py`): dashboard of all past runs.
```bash
python3 scripts/fb_cli.py audit                    # summary
python3 scripts/fb_cli.py audit --since 7d        # last 7 days
python3 scripts/fb_cli.py audit --script 05       # specific script
python3 scripts/fb_cli.py audit --json out.json   # machine-readable
```

Outputs: total runs, success rate, avg/p50/p95 duration per script,
recent failures (last 7d).

## Reference

- Facebook Graph API docs: https://developers.facebook.com/docs/graph-api/
- `facebook-scraper` (unofficial Python): https://github.com/kevinzg/facebook-scraper
- Apify Facebook scrapers: https://apify.com/store?search=facebook
- Chrome DevTools Protocol: https://chromedevtools.github.io/devtools-protocol/