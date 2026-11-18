"""
Scrape Facebook fanpage TIMELINE (https://facebook.com/<page-slug>/) qua CDP.

Khác với 06 (group feed — multiple authors per post):
  - 06: group feed → many authors (user names)
  - 08: page timeline → single author per post (the page itself)

Why tách riêng từ 06: Fanpage timeline render DOM khác group feed:
  - Author luôn là page name (1 lần), không random user names.
  - Reactions/comments/shares counts thường ở `aria-label="X reactions"` chứ
    không phải text thuần "123 reactions" (group feed thì có cả hai).
  - "X comments" link có pattern `/<page-slug>/posts/<id>/?comment_id=...`.
  - "Pinned post" có badge riêng → flag `pinned: true` thay vì skip.

Mỗi post: author, text, timestamp, reactions_count, comments_count, shares_count,
post_url, media_urls[], pinned.

Writes run manifest to `data/posts/<page_slug>/manifest.json`.
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
# JS extractor — page-timeline-specific
# -----------------------------------------------------------------------

# Notes vs. 06_crawl_group.py:
#   - Author: filter to ONE name (the page) by checking href contains page-slug
#     OR strong-tag with page name (page header is repeated).
#   - Counts: prefer aria-label (e.g. "1.2K reactions") over text pattern.
#   - Pinned detection: look for "Pinned post" text near timestamp.
#   - Skip rules: skip nav widgets, "Suggested for you", "People also viewed".

EXTRACT_JS = r"""
(function() {
    const results = [];
    const seen = new Set();

    // Same candidate selectors as group feed (FB reuses these), but we'll filter
    // more strictly because page timeline mixes posts + nav widgets + suggestions.
    const articleSelectors = [
        '[role="article"]',
        'div[data-pagelet*="FeedUnit"]',
    ];

    let candidates = [];
    for (const sel of articleSelectors) {
        candidates = document.querySelectorAll(sel);
        if (candidates.length > 0) break;
    }

    candidates.forEach((article) => {
        try {
            // Skip rules: nav widgets, suggestions, "people also viewed"
            const articleText = (article.textContent || '').toLowerCase();
            if (/^(suggested for you|people also viewed|pages you may like)/i.test(
                    (article.querySelector('h2,h3,h4') || {}).textContent || '')) {
                return;
            }

            // 1. Author — page name (1 entry per post usually)
            // Try strong>a, h2>a, h3>a, then role=link.
            // Page-timeline author link href contains the page slug.
            const headerLinks = article.querySelectorAll(
                'h2 a, h3 a, h4 a, strong a, a[role="link"]'
            );
            let author = null;
            let authorUrl = null;
            for (const link of headerLinks) {
                const txt = (link.textContent || '').trim();
                const href = link.href || '';
                // Filter: text must be reasonable, not "View" / "More" / etc.
                if (!txt || txt.length === 0 || txt.length > 80) continue;
                if (/^(view|xem|thêm|more|reply|trả lời|see all|show more)/i.test(txt)) continue;
                // Skip if href doesn't look like a profile/page link
                if (!/facebook\.com\//.test(href)) continue;
                author = txt;
                authorUrl = href.split("?")[0];
                break;
            }

            // 2. Post text — first dir="auto" div with reasonable length
            const textDivs = article.querySelectorAll('div[dir="auto"]');
            let postText = null;
            for (const div of textDivs) {
                const t = (div.textContent || '').trim();
                // Skip rỗng / quá ngắn / numbers-only
                if (t && t.length >= 15 && t.length < 10000
                    && !/^\d+(\.\d+)?[KkMm]?\s*(reactions?|comments?|shares?|lượt thích|bình luận|chia sẻ)?$/i.test(t)) {
                    postText = t;
                    break;
                }
            }
            if (!postText) return;

            // 3. Timestamp — prefer <abbr title="ISO8601"> or permalink a[title]
            const abbr = article.querySelector('abbr[title]');
            const permalinkA = article.querySelector('a[href*="/posts/"]');
            let timestamp = null;
            let postUrl = null;
            if (abbr && abbr.title) {
                timestamp = abbr.title;
            } else if (permalinkA) {
                timestamp = permalinkA.getAttribute('title') || abbr?.textContent?.trim() || null;
                postUrl = permalinkA.href.split("?")[0];
            }
            if (!postUrl) {
                // Fallback: any anchor with /posts/ or permalink
                const anyPermalink = article.querySelector(
                    'a[href*="/posts/"], a[href*="/permalink/"], a[href*="story.php"], a[href*="/videos/"]'
                );
                if (anyPermalink) postUrl = anyPermalink.href.split("?")[0];
            }

            // 4. Reactions count — try aria-label FIRST (page-timeline convention),
            //    then fall back to text pattern.
            let reactions = null;
            const reactAriaLabel = article.querySelector(
                '[aria-label*="reaction" i], [aria-label*="thích" i], [aria-label*="like" i]'
            );
            if (reactAriaLabel) {
                const al = reactAriaLabel.getAttribute('aria-label') || '';
                const m = al.match(/([\d.,]+)\s*([KkMm]?)/);
                if (m) {
                    const num = parseFloat(m[1].replace(/,/g, ''));
                    const mult = /k/i.test(m[2]) ? 1000 : /m/i.test(m[2]) ? 1e6 : 1;
                    reactions = Math.round(num * mult);
                }
            }
            if (reactions == null) {
                const txt = article.textContent || '';
                const reactMatch = txt.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:lượt thích|reactions?|likes?)/i);
                if (reactMatch) {
                    let num = parseFloat(reactMatch[1].replace(/,/g, ''));
                    const lastChar = reactMatch[1].slice(-1);
                    if (/k/i.test(lastChar)) num *= 1000;
                    else if (/m/i.test(lastChar)) num *= 1e6;
                    reactions = Math.round(num);
                }
            }

            // 5. Comments count — same dual approach
            let commentsCount = null;
            const commentAriaLabel = article.querySelector(
                '[aria-label*="comment" i], [aria-label*="bình luận" i]'
            );
            if (commentAriaLabel) {
                const al = commentAriaLabel.getAttribute('aria-label') || '';
                const m = al.match(/([\d.,]+)\s*([KkMm]?)/);
                if (m) {
                    const num = parseFloat(m[1].replace(/,/g, ''));
                    const mult = /k/i.test(m[2]) ? 1000 : /m/i.test(m[2]) ? 1e6 : 1;
                    commentsCount = Math.round(num * mult);
                }
            }
            if (commentsCount == null) {
                const txt = article.textContent || '';
                const m = txt.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:bình luận|comments?)/i);
                if (m) {
                    let num = parseFloat(m[1].replace(/,/g, ''));
                    const lastChar = m[1].slice(-1);
                    if (/k/i.test(lastChar)) num *= 1000;
                    else if (/m/i.test(lastChar)) num *= 1e6;
                    commentsCount = Math.round(num);
                }
            }

            // 6. Shares count — same dual approach
            let shares = null;
            const shareAriaLabel = article.querySelector(
                '[aria-label*="share" i], [aria-label*="chia sẻ" i]'
            );
            if (shareAriaLabel) {
                const al = shareAriaLabel.getAttribute('aria-label') || '';
                const m = al.match(/([\d.,]+)\s*([KkMm]?)/);
                if (m) {
                    const num = parseFloat(m[1].replace(/,/g, ''));
                    const mult = /k/i.test(m[2]) ? 1000 : /m/i.test(m[2]) ? 1e6 : 1;
                    shares = Math.round(num * mult);
                }
            }
            if (shares == null) {
                const txt = article.textContent || '';
                const m = txt.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:chia sẻ|shares?)/i);
                if (m) {
                    let num = parseFloat(m[1].replace(/,/g, ''));
                    const lastChar = m[1].slice(-1);
                    if (/k/i.test(lastChar)) num *= 1000;
                    else if (/m/i.test(lastChar)) num *= 1e6;
                    shares = Math.round(num);
                }
            }

            // 7. Pinned post detection
            const isPinned = /pin(?:ned)? post|bài viết đã ghim/i.test(
                article.textContent || ''
            );

            // 8. Media URLs — filter to user-uploaded scontent images
            const imgs = article.querySelectorAll('img[src*="scontent"]');
            const mediaUrls = [];
            const seenSrc = new Set();
            for (const img of imgs) {
                const src = img.src || '';
                if (!src) continue;
                // Strip query (signatures expire)
                const clean = src.split('?')[0];
                if (seenSrc.has(clean)) continue;
                // Skip emoji / static UI assets
                if (/static\.xx\.fbcdn\.net|images\.emoji\.php/i.test(clean)) continue;
                seenSrc.add(clean);
                mediaUrls.push(clean);
                if (mediaUrls.length >= 4) break;
            }

            // Skip if missing required fields
            if (!postUrl) return;
            if (!author) return;

            // Dedupe
            if (seen.has(postUrl)) return;
            seen.add(postUrl);

            results.push({
                author: author,
                author_url: authorUrl,
                text: postText.substring(0, 5000),
                timestamp: timestamp,
                reactions: reactions,
                comments_count: commentsCount,
                shares: shares,
                post_url: postUrl,
                media_urls: mediaUrls,
                pinned: isPinned,
                scraped_at: new Date().toISOString(),
                page_url: window.location.href,
            });
        } catch (e) {}
    });

    // Sort: pinned first, then by timestamp desc (best-effort — FB doesn't always render ISO)
    results.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        return 0;
    });

    return results;
})();
"""


# -----------------------------------------------------------------------
# Crawl function
# -----------------------------------------------------------------------

async def crawl_page_timeline(page_url: str, max_posts: int = 10, max_scrolls: int = 15,
                                manifest: RunManifest | None = None):
    """Crawl posts from a fanpage timeline.

    manifest: optional RunManifest. If None, creates one in a per-page folder.
    """
    from _data_paths import post_dir
    if manifest is None:
        manifest = RunManifest(
            post_dir(page_url),
            script="08_crawl_page_timeline.py",
            input_url=page_url,
            input_args={"max_posts": max_posts, "max_scrolls": max_scrolls},
        )

    # Get list of pages
    with urllib.request.urlopen(f"{CDP_HTTP}/json") as r:
        pages = json.loads(r.read())

    main_page = None
    for p in pages:
        if p.get("type") == "page" and "facebook.com" in p.get("url", ""):
            main_page = p
            break

    if not main_page:
        print("❌ Không tìm thấy tab Facebook. Đảm bảo đã mở browser và login.")
        manifest.finish(status="failed")
        return None

    ws_url = main_page["webSocketDebuggerUrl"]
    current_url = main_page["url"]
    print(f"✓ Tab hiện tại: {current_url}")

    manifest.stage("navigate", meta={"url": page_url})
    manifest.start()

    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        msg_id = 0

        def next_id():
            nonlocal msg_id
            msg_id += 1
            return msg_id

        # Navigate tới page URL nếu chưa ở đó
        if page_url.rstrip("/") not in current_url.rstrip("/"):
            print(f"\n→ Navigate tới: {page_url}")
            await cdp_send(ws, "Page.enable", msg_id=next_id())
            await cdp_send(ws, "Page.navigate", {"url": page_url}, msg_id=next_id())
            await asyncio.sleep(8)
        else:
            print(f"\n✓ Đã ở page, scroll để load posts...")

        # Scroll cho đến khi height stable 3 lần
        manifest.stage("scroll", meta={"max_scrolls": max_scrolls})
        prev_height = 0
        stable_count = 0
        for i in range(max_scrolls):
            await cdp_send(ws, "Runtime.evaluate",
                           {"expression": "window.scrollTo(0, document.body.scrollHeight)"},
                           msg_id=next_id())
            await asyncio.sleep(2.5)
            res = await cdp_send(ws, "Runtime.evaluate",
                                 {"expression": "document.body.scrollHeight",
                                  "returnByValue": True},
                                 msg_id=next_id())
            h = res.get("result", {}).get("value", 0)
            print(f"  Scroll {i+1}/{max_scrolls} — height: {h}px")
            manifest.checkpoint({"phase": "scroll", "round": i + 1, "height": h},
                                persist_every=3, round_index=i + 1)
            if h == prev_height:
                stable_count += 1
                if stable_count >= 3:
                    print("  → Page height stable 3 lần, dừng scroll")
                    break
            else:
                stable_count = 0
            prev_height = h

        # Extract posts
        manifest.stage("extract", meta={"max_posts": max_posts})
        print(f"\n→ Extract posts (target: {max_posts})...")

        res = await cdp_send(ws, "Runtime.evaluate",
                             {"expression": EXTRACT_JS, "returnByValue": True},
                             msg_id=next_id())
        posts = res.get("result", {}).get("value", [])

        if len(posts) > max_posts:
            posts = posts[:max_posts]

        print(f"✓ Extracted {len(posts)} posts")

        if not posts:
            print("\n⚠ 0 posts. Có thể:")
            print("  - Page private hoặc không có posts public")
            print("  - Cần login để xem feed")
            print("  - DOM structure khác → selector cần update")
            manifest.finish(status="failed")
            return None

        # Save — both flat file (legacy) + per-post folder (new convention)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        flat_path = DATA_DIR / f"raw_page_posts_{timestamp}.json"
        flat_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2),
                             encoding="utf-8")

        post_folder = manifest.post_dir
        per_post_raw = post_folder / "raw.json"
        if per_post_raw.exists():
            per_post_raw = post_folder / f"raw_{timestamp}.json"
        per_post_raw.write_text(json.dumps(posts, ensure_ascii=False, indent=2),
                                encoding="utf-8")

        print(f"\n💾 Saved: {flat_path}")
        print(f"  + Per-post copy: {per_post_raw}")
        print(f"  Posts: {len(posts)}")

        # Stats
        authors = set(p["author"] for p in posts)
        with_reactions = sum(1 for p in posts if p.get("reactions") is not None)
        with_comments = sum(1 for p in posts if p.get("comments_count") is not None)
        with_shares = sum(1 for p in posts if p.get("shares") is not None)
        with_media = sum(1 for p in posts if p.get("media_urls"))
        pinned_count = sum(1 for p in posts if p.get("pinned"))

        print(f"\n📊 Stats:")
        print(f"  Unique authors   : {len(authors)}")
        print(f"  With reactions   : {with_reactions}")
        print(f"  With comments    : {with_comments}")
        print(f"  With shares      : {with_shares}")
        print(f"  With media       : {with_media}")
        print(f"  Pinned posts     : {pinned_count}")

        print(f"\n📋 Sample (first 3):")
        for p in posts[:3]:
            text_preview = p["text"][:80].replace("\n", " ")
            print(f"  - [{p['author']}]{' [PINNED]' if p.get('pinned') else ''} "
                  f"r={p.get('reactions','?')} c={p.get('comments_count','?')}: "
                  f"{text_preview}")

        # Manifest finalize
        manifest.count("posts", len(posts))
        manifest.count("unique_authors", len(authors))
        manifest.count("with_reactions", with_reactions)
        manifest.count("with_comments", with_comments)
        manifest.count("with_shares", with_shares)
        manifest.count("with_media", with_media)
        manifest.count("pinned", pinned_count)
        manifest.output("raw", flat_path)
        manifest.output("per_post_raw", per_post_raw)
        manifest.finish(status="success")

        return flat_path


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(
        description="Crawl a fanpage timeline (posts only, no deep comments).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/08_crawl_page_timeline.py https://www.facebook.com/<page-slug> 20
  python3 scripts/08_crawl_page_timeline.py <page_url> 10 25  # 10 posts, 25 scrolls
  python3 scripts/fb_cli.py crawl timeline <page_url> 30       # via dispatcher
        """,
    )
    parser.add_argument("page_url",
                        help="Page timeline URL (e.g. https://www.facebook.com/<page-slug>)")
    parser.add_argument("max_posts", nargs="?", type=int, default=10,
                        help="Max posts to extract (default: 10)")
    parser.add_argument("max_scrolls", nargs="?", type=int, default=15,
                        help="Max scroll rounds (default: 15)")
    args = parser.parse_args()

    # Generic check: reject obviously wrong URLs
    if "facebook.com" not in args.page_url:
        parser.error(f"URL phải chứa facebook.com: {args.page_url}")
    if "<" in args.page_url or "your-" in args.page_url.lower():
        parser.error(
            f"URL chứa placeholder '{args.page_url}' — replace với page slug thật"
        )

    print("=" * 60)
    print("FB PAGE TIMELINE CRAWL VIA CDP")
    print("=" * 60)
    print(f"Page URL    : {args.page_url}")
    print(f"Max posts   : {args.max_posts}")
    print(f"Max scrolls : {args.max_scrolls}")
    print("=" * 60)

    try:
        result = await crawl_page_timeline(args.page_url, args.max_posts, args.max_scrolls)
        if result:
            print(f"\n✓ Done. Raw file: {result}")
            print(f"\nNext: python3 scripts/04_clean_data.py {result}")
            print(f"   OR: python3 scripts/fb_cli.py crawl deep <post_url>  # deep comments per post")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())