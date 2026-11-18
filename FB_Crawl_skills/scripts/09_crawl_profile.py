"""
Crawl Facebook personal profile (public view) qua CDP.

⚠️  PRIVACY & ToS WARNING — READ BEFORE USING:

1. Personal profile data is **often PII** (PII = email, phone, location, employer,
   education, relationship status, photos, comments).

2. Many profiles are private or friends-only — this script handles those by
   detecting and warning, NOT by bypassing privacy controls.

3. Scraping personal profiles may violate:
   - Meta Terms of Service (https://www.facebook.com/terms)
   - GDPR (EU residents)
   - Vietnam PDPA Decree 13/2023/NĐ-CP
   - CCPA, LGPD, CFAA depending on jurisdiction

4. Only use this on profiles you have **explicit authorization** to crawl
   (e.g. your own profile, a research subject with informed consent, a brand
   ambassador's public profile for marketing analysis).

5. Cross-reference with `skills/facebook-anti-bot/SKILL.md` for the full
   legal warning before running this at scale.

What this script extracts (public view only):
  - Stage 1 — About: bio, current city, work history, education, website,
    contact email (if public), join date
  - Stage 2 — Posts: timeline posts (using page-timeline extractor as base)
  - Stage 3 — Photos (optional): photo URLs + captions from /photos tab

URL formats supported:
  - https://www.facebook.com/<username>            # vanity URL
  - https://www.facebook.com/profile.php?id=<id>   # legacy numeric ID
  - https://www.facebook.com/people/<name>/<id>    # new format

Writes run manifest to `data/posts/<profile_slug>/manifest.json`.
"""
import argparse
import asyncio
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _run_manifest import RunManifest  # noqa: E402

import websockets

CDP_HTTP = "http://127.0.0.1:9222"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


async def cdp_send(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error: {resp['error']}")
            return resp.get("result", {})
        # Skip events


# -----------------------------------------------------------------------
# JS extractors
# -----------------------------------------------------------------------

# Stage 1 — About section
# Walks About page; sections are rendered as labeled rows
# (e.g. "Current city" header followed by value).
ABOUT_JS = r"""
(function() {
    const result = {};
    const text = document.body.textContent || '';

    // Bio: usually in the "Intro" section as a paragraph
    // Try selectors: data-pagelet="ProfileTilesFeed" contains about sections
    const bioEl = document.querySelector(
        '[data-pagelet="ProfileTilesFeed"] div[dir="auto"], ' +
        'div[class*="bio"] div[dir="auto"], ' +
        'span[class*="bio"]'
    );
    if (bioEl) {
        const bio = (bioEl.textContent || '').trim();
        if (bio.length >= 10 && bio.length < 1000) result.bio = bio;
    }

    // Section labels and values: walk all rows in About section
    // Common pattern: <span>Current city</span><span>Ho Chi Minh City</span>
    const sectionLabels = {
        'current city': 'current_city',
        'hometown': 'hometown',
        'work': 'work',
        'education': 'education',
        'website': 'website',
        'social links': 'social_links',
        'contact info': 'contact_info',
        'contact email': 'contact_email',
        'phone': 'phone',
        'address': 'address',
        'joined': 'joined_date',
        'relationship': 'relationship',
        'gender': 'gender',
        'birthday': 'birthday',
        'languages': 'languages',
    };

    // Walk all spans, look for label-like text → grab next sibling
    const spans = document.querySelectorAll('span, div');
    const found = {};
    spans.forEach(el => {
        const t = (el.textContent || '').trim().toLowerCase().slice(0, 50);
        if (sectionLabels[t] && !found[t]) {
            // Look for value in next sibling or parent's next sibling
            let valueEl = el.nextElementSibling;
            let attempts = 0;
            while (valueEl && attempts < 3) {
                const v = (valueEl.textContent || '').trim();
                if (v && v.length > 0 && v.length < 500 && v.toLowerCase() !== t) {
                    found[t] = v;
                    break;
                }
                valueEl = valueEl.nextElementSibling;
                attempts++;
            }
            // Fallback: parent's next sibling
            if (!found[t] && el.parentElement && el.parentElement.nextElementSibling) {
                const v = (el.parentElement.nextElementSibling.textContent || '').trim();
                if (v && v.length > 0 && v.length < 500) found[t] = v;
            }
        }
    });

    for (const [label, key] of Object.entries(sectionLabels)) {
        if (found[label]) result[key] = found[label];
    }

    // If profile is private, FB shows "This profile is private" or similar
    if (/this profile is private|trang này riêng tư|này là riêng tư/i.test(text)) {
        result._private = true;
    }

    // Display name (always visible if page loaded)
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) {
        result.name = (ogTitle.content || '').trim();
    }
    if (!result.name) {
        const h1 = document.querySelector('h1');
        if (h1) result.name = (h1.textContent || '').trim();
    }

    // Profile ID from URL
    result.profile_url = window.location.href;

    return result;
})();
"""


# Stage 2 — Timeline posts (reuses page-timeline-style logic with stricter
# single-author filter)
POSTS_JS = r"""
(function() {
    const results = [];
    const seen = new Set();

    const candidates = document.querySelectorAll(
        '[role="article"], div[data-pagelet*="FeedUnit"]'
    );

    candidates.forEach((article) => {
        try {
            // Skip nav widgets / suggestions
            const heading = (article.querySelector('h2,h3,h4') || {}).textContent || '';
            if (/^(suggested for you|people also viewed|pages you may like)/i.test(heading)) {
                return;
            }

            // Author — for personal profiles, it's always the profile owner
            const headerLinks = article.querySelectorAll('h2 a, h3 a, strong a, a[role="link"]');
            let author = null;
            for (const link of headerLinks) {
                const txt = (link.textContent || '').trim();
                if (!txt || txt.length > 80) continue;
                if (/^(view|more|reply|see all)/i.test(txt)) continue;
                author = txt;
                break;
            }
            // Profile posts default to "Timeline post" or no header — use page name
            // from og:title as fallback
            if (!author) {
                const ogTitle = document.querySelector('meta[property="og:title"]');
                if (ogTitle) author = (ogTitle.content || '').split('|')[0].trim();
            }

            // Post text
            const textDivs = article.querySelectorAll('div[dir="auto"]');
            let postText = null;
            for (const div of textDivs) {
                const t = (div.textContent || '').trim();
                if (t && t.length >= 10 && t.length < 10000
                    && !/^\d+(\.\d+)?[KkMm]?\s*(reactions?|comments?|shares?)?$/i.test(t)) {
                    postText = t;
                    break;
                }
            }
            if (!postText) return;

            // Timestamp
            const abbr = article.querySelector('abbr[title]');
            const timestamp = abbr ? abbr.title : null;

            // Post URL
            const permalinkA = article.querySelector('a[href*="/posts/"], a[href*="/permalink/"], a[href*="story.php"], a[href*="/videos/"]');
            const postUrl = permalinkA ? permalinkA.href.split("?")[0] : null;
            if (!postUrl) return;

            // Reactions count (best effort)
            const txt = article.textContent || '';
            const reactMatch = txt.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:lượt thích|reactions?|likes?)/i);
            let reactions = null;
            if (reactMatch) {
                let num = parseFloat(reactMatch[1].replace(/,/g, ''));
                const lastChar = reactMatch[1].slice(-1);
                if (/k/i.test(lastChar)) num *= 1000;
                else if (/m/i.test(lastChar)) num *= 1e6;
                reactions = Math.round(num);
            }

            // Comments count
            const commentMatch = txt.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:bình luận|comments?)/i);
            let commentsCount = null;
            if (commentMatch) {
                let num = parseFloat(commentMatch[1].replace(/,/g, ''));
                const lastChar = commentMatch[1].slice(-1);
                if (/k/i.test(lastChar)) num *= 1000;
                else if (/m/i.test(lastChar)) num *= 1e6;
                commentsCount = Math.round(num);
            }

            // Media
            const imgs = article.querySelectorAll('img[src*="scontent"]');
            const mediaUrls = [];
            const seenSrc = new Set();
            for (const img of imgs) {
                const src = (img.src || '').split('?')[0];
                if (!src || seenSrc.has(src)) continue;
                if (/static\.xx\.fbcdn\.net|images\.emoji\.php/i.test(src)) continue;
                seenSrc.add(src);
                mediaUrls.push(src);
                if (mediaUrls.length >= 4) break;
            }

            // Dedupe by post_url
            if (seen.has(postUrl)) return;
            seen.add(postUrl);

            results.push({
                author: author || "(profile owner)",
                text: postText.substring(0, 5000),
                timestamp: timestamp,
                post_url: postUrl,
                reactions: reactions,
                comments_count: commentsCount,
                media_urls: mediaUrls,
                scraped_at: new Date().toISOString(),
                profile_url: window.location.href,
            });
        } catch (e) {}
    });

    return results;
})();
"""


# Stage 3 — Photos
PHOTOS_JS = r"""
(function() {
    const results = [];
    const seen = new Set();

    // Photo grid items: usually have aspect-ratio + lazy-loaded img
    document.querySelectorAll('img[src*="scontent"]').forEach(img => {
        const src = (img.src || '').split('?')[0];
        if (!src || seen.has(src)) return;
        if (/static\.xx\.fbcdn\.net|images\.emoji\.php/i.test(src)) return;
        seen.add(src);

        // Try to find caption (parent link text or aria-label)
        let caption = '';
        const parent = img.closest('a') || img.parentElement;
        if (parent) {
            caption = (parent.getAttribute('aria-label') || parent.textContent || '').trim();
            if (caption.length > 500) caption = caption.substring(0, 500);
        }

        results.push({
            url: src,
            caption: caption,
        });
    });

    return results.slice(0, 100);  // cap at 100 photos
})();
"""


# -----------------------------------------------------------------------
# Stage helpers
# -----------------------------------------------------------------------

async def navigate(ws, url: str, next_id, wait: float = 6.0):
    """Navigate to URL, wait for page load."""
    print(f"  → Navigate: {url}")
    await cdp_send(ws, "Page.navigate", {"url": url}, msg_id=next_id())
    await asyncio.sleep(wait)


async def extract_about(ws, profile_url: str) -> dict:
    """Stage 1: extract About info from <profile>/about."""
    print("\n→ Stage 1: About section")
    about_url = profile_url.rstrip("/") + "/about"
    # Already handled in caller; here just extract
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": ABOUT_JS, "returnByValue": True})
    about = res.get("result", {}).get("value", {})

    if about.get("_private"):
        print("  ⚠ Profile is PRIVATE — only public fields will be returned")
        about["_warning"] = "profile_private"
    else:
        fields_found = [k for k in about if not k.startswith("_") and k != "profile_url"]
        print(f"  ✓ Extracted {len(fields_found)} fields: {', '.join(fields_found[:8])}")
    return about


async def extract_posts(ws, profile_url: str, max_posts: int) -> list:
    """Stage 2: extract timeline posts."""
    print(f"\n→ Stage 2: Timeline posts (max: {max_posts})")
    # Caller navigated to base profile URL; extract here
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": POSTS_JS, "returnByValue": True})
    posts = res.get("result", {}).get("value", [])
    if len(posts) > max_posts:
        posts = posts[:max_posts]
    print(f"  ✓ Extracted {len(posts)} posts")
    return posts


async def extract_photos(ws) -> list:
    """Stage 3: extract photos (must be on /photos URL)."""
    print("\n→ Stage 3: Photos")
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": PHOTOS_JS, "returnByValue": True})
    photos = res.get("result", {}).get("value", [])
    print(f"  ✓ Extracted {len(photos)} photo URLs")
    return photos


# -----------------------------------------------------------------------
# Main crawler
# -----------------------------------------------------------------------

async def crawl_profile(profile_url: str, max_posts: int = 10, max_scrolls: int = 10,
                         with_about: bool = True, with_photos: bool = False,
                         manifest: RunManifest | None = None):
    """Crawl a personal profile (public view).

    Args:
        profile_url: profile URL (vanity, profile.php?id=, or /people/ format)
        max_posts: max timeline posts to extract
        max_scrolls: max scroll rounds for timeline loading
        with_about: extract About section
        with_photos: extract photos (requires /photos nav)
        manifest: optional RunManifest

    Returns:
        Path to raw JSON file, or None on failure.
    """
    from _data_paths import post_dir
    if manifest is None:
        manifest = RunManifest(
            post_dir(profile_url),
            script="09_crawl_profile.py",
            input_url=profile_url,
            input_args={
                "max_posts": max_posts, "max_scrolls": max_scrolls,
                "with_about": with_about, "with_photos": with_photos,
            },
        )
    manifest.start()

    # Connect
    with urllib.request.urlopen(f"{CDP_HTTP}/json") as r:
        pages = json.loads(r.read())
    main_page = None
    for p in pages:
        if p.get("type") == "page" and "facebook.com" in p.get("url", ""):
            main_page = p
            break
    if not main_page:
        print("❌ Không tìm thấy tab Facebook. Đảm bảo đã mở browser + login.")
        manifest.finish(status="failed")
        return None

    ws_url = main_page["webSocketDebuggerUrl"]
    print(f"✓ Connected: {main_page['url']}")

    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        msg_id = 0
        def next_id():
            nonlocal msg_id
            msg_id += 1
            return msg_id

        # Stage 1 — About
        about_data = {}
        if with_about:
            manifest.stage("about")
            await navigate(ws, profile_url.rstrip("/") + "/about",
                          next_id=next_id, wait=6.0)
            about_data = await extract_about(ws, profile_url)

        # Stage 2 — Posts (navigate back to base profile)
        manifest.stage("posts", meta={"max_posts": max_posts})
        await navigate(ws, profile_url, next_id=next_id, wait=6.0)

        # Scroll to load posts
        for i in range(max_scrolls):
            await cdp_send(ws, "Runtime.evaluate",
                           {"expression": "window.scrollTo(0, document.body.scrollHeight)"},
                           msg_id=next_id())
            await asyncio.sleep(2)
            res = await cdp_send(ws, "Runtime.evaluate",
                                 {"expression": "document.body.scrollHeight",
                                  "returnByValue": True},
                                 msg_id=next_id())
            h = res.get("result", {}).get("value", 0)
            print(f"  Scroll {i+1}/{max_scrolls} — height: {h}px")
            manifest.checkpoint({"phase": "posts", "round": i + 1, "height": h},
                                persist_every=3, round_index=i + 1)

        posts_data = await extract_posts(ws, profile_url, max_posts)

        # Stage 3 — Photos
        photos_data = []
        if with_photos:
            manifest.stage("photos")
            await navigate(ws, profile_url.rstrip("/") + "/photos",
                          next_id=next_id, wait=6.0)
            # Scroll photos
            for _ in range(3):
                await cdp_send(ws, "Runtime.evaluate",
                               {"expression": "window.scrollTo(0, document.body.scrollHeight)"},
                               msg_id=next_id())
                await asyncio.sleep(2)
            photos_data = await extract_photos(ws)

        # Assemble output
        manifest.stage("save")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = {
            "profile": about_data,
            "posts": posts_data,
            "photos": photos_data,
            "scraped_at": datetime.now().isoformat(),
            "profile_url": profile_url,
        }

        # Save flat + per-folder
        flat_path = DATA_DIR / f"raw_profile_{timestamp}.json"
        flat_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        post_folder = manifest.post_dir
        per_post_raw = post_folder / "raw.json"
        if per_post_raw.exists():
            per_post_raw = post_folder / f"raw_{timestamp}.json"
        per_post_raw.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                encoding="utf-8")

        print(f"\n💾 Saved: {flat_path}")
        print(f"  + Per-post copy: {per_post_raw}")
        print(f"  About fields: {len([k for k in about_data if not k.startswith('_')])}")
        print(f"  Posts: {len(posts_data)}")
        print(f"  Photos: {len(photos_data)}")

        if about_data.get("_private"):
            print("\n⚠  Profile is PRIVATE. Public fields only.")
            print(f"   Name: {about_data.get('name', '?')}")
            print(f"   See: {about_data.get('profile_url', profile_url)}")

        # Manifest finalize
        manifest.count("about_fields", len([k for k in about_data if not k.startswith('_')]))
        manifest.count("posts", len(posts_data))
        manifest.count("photos", len(photos_data))
        if about_data.get("_private"):
            manifest.warning("profile_private_only_public_fields_returned")
        manifest.output("raw", flat_path)
        manifest.output("per_post_raw", per_post_raw)
        manifest.finish(status="success")
        return flat_path


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(
        description="Crawl a Facebook personal profile (PUBLIC view only). "
                    "⚠️  Read privacy/ToS warning at top of this script.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/09_crawl_profile.py https://www.facebook.com/<username> --with-about
  python3 scripts/09_crawl_profile.py <profile_url> --max-posts 20 --with-photos
  python3 scripts/fb_cli.py crawl profile <profile_url> --with-about

Stages (run in order):
  1. About (if --with-about): bio, work, education, contact, etc.
  2. Posts: timeline posts (max --max-posts, default 10)
  3. Photos (if --with-photos): photo URLs + captions from /photos tab
        """,
    )
    parser.add_argument("profile_url",
                        help="Profile URL (https://www.facebook.com/<username>)")
    parser.add_argument("--max-posts", type=int, default=10,
                        help="Max timeline posts (default: 10)")
    parser.add_argument("--max-scrolls", type=int, default=10,
                        help="Max scroll rounds for posts (default: 10)")
    parser.add_argument("--with-about", action="store_true",
                        help="Extract About section (Stage 1)")
    parser.add_argument("--no-about", action="store_true",
                        help="Skip About section")
    parser.add_argument("--with-photos", action="store_true",
                        help="Extract photos from /photos tab (Stage 3)")
    args = parser.parse_args()

    # Generic URL checks
    if "facebook.com" not in args.profile_url:
        parser.error(f"URL phải chứa facebook.com: {args.profile_url}")
    if "<" in args.profile_url or "your-" in args.profile_url.lower():
        parser.error(
            f"URL chứa placeholder '{args.profile_url}' — replace với profile URL thật"
        )

    with_about = args.with_about and not args.no_about

    print("=" * 60)
    print("FB PROFILE CRAWL VIA CDP")
    print("=" * 60)
    print(f"Profile URL   : {args.profile_url}")
    print(f"Max posts     : {args.max_posts}")
    print(f"Max scrolls   : {args.max_scrolls}")
    print(f"With about    : {with_about}")
    print(f"With photos   : {args.with_photos}")
    print("⚠️  Privacy/ToS: chỉ dùng cho profile public hoặc có authorization.")
    print("=" * 60)

    try:
        result = await crawl_profile(
            args.profile_url,
            args.max_posts,
            args.max_scrolls,
            with_about=with_about,
            with_photos=args.with_photos,
        )
        if result:
            print(f"\n✓ Done. Raw file: {result}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())