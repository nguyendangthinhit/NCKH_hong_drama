"""
Scrape Facebook Group FEED (posts) qua Chrome DevTools Protocol.

Khác với 05 (scrape comments của 1 post):
  - 05: navigate tới post URL → extract comments
  - 06: đã ở group page → scroll → extract posts trong feed

Mỗi post có: author, text, timestamp, reactions count, comments count, shares, post_url.

Writes run manifest to `data/posts/<group_slug>/manifest.json` (see _run_manifest.py).
"""
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


async def crawl_group(group_url: str, max_posts: int = 10, max_scrolls: int = 15,
                     manifest: RunManifest | None = None):
    """Crawl posts trong group feed.

    manifest: optional RunManifest for audit. If None, creates one in a per-group folder.
    """
    from _data_paths import post_dir
    if manifest is None:
        manifest = RunManifest(
            post_dir(group_url),
            script="06_crawl_group.py",
            input_url=group_url,
            input_args={"max_posts": max_posts, "max_scrolls": max_scrolls},
        )
    manifest.stage("navigate", meta={"url": group_url})
    manifest.start()
    with urllib.request.urlopen(f"{CDP_HTTP}/json") as r:
        pages = json.loads(r.read())

    main_page = None
    for p in pages:
        if p.get("type") == "page" and "facebook.com" in p.get("url", ""):
            main_page = p
            break

    if not main_page:
        print("❌ Không tìm thấy tab FB.")
        return None

    ws_url = main_page["webSocketDebuggerUrl"]
    current_url = main_page["url"]
    print(f"✓ Tab hiện tại: {current_url}")

    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        msg_id = 0

        def next_id():
            nonlocal msg_id
            msg_id += 1
            return msg_id

        # Nếu URL hiện tại không phải group URL → navigate
        if group_url not in current_url:
            print(f"\n→ Navigate tới: {group_url}")
            await cdp_send(ws, "Page.enable", msg_id=next_id())
            await cdp_send(ws, "Page.navigate",
                           {"url": group_url},
                           msg_id=next_id())
            await asyncio.sleep(8)
        else:
            print(f"\n✓ Đã ở group, scroll để load posts...")

        # Scroll để load posts
        manifest.stage("scroll", meta={"max_scrolls": max_scrolls})
        print(f"\n→ Scroll tối đa {max_scrolls} lần...")
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

            if h == prev_height:
                stable_count += 1
                if stable_count >= 3:
                    print("  → Page height stable 3 lần, dừng scroll")
                    break
            else:
                stable_count = 0
            prev_height = h

        # Extract posts
        manifest.stage("extract", meta={"target": max_posts})
        print(f"\n→ Extract posts (target: {max_posts})...")

        extract_js = """
        (function() {
            const results = [];
            const seen = new Set();

            // FB group feed: posts có thể nằm trong nhiều container khác nhau.
            // Strategy: tìm feed stories bằng role="article" trong feed,
            // hoặc tìm div có data-pagelet="FeedUnit_0" hoặc tương tự.
            const articleSelectors = [
                '[role="article"]',
                'div[data-pagelet*="FeedUnit"]',
            ];

            let candidates = [];
            for (const sel of articleSelectors) {
                candidates = document.querySelectorAll(sel);
                if (candidates.length > 0) break;
            }

            candidates.forEach((article, idx) => {
                try {
                    // 1. Author — link đầu tiên trong article (thường có trong header)
                    const headerLinks = article.querySelectorAll('h2 a, h3 a, strong a, a[role="link"]');
                    let author = null;
                    let authorUrl = null;
                    for (const link of headerLinks) {
                        const txt = link.textContent.trim();
                        if (txt && txt.length > 0 && txt.length < 80 && !/^(Xem|View|Thêm|More|Reply|Trả lời)/i.test(txt)) {
                            author = txt;
                            authorUrl = link.href;
                            break;
                        }
                    }

                    // 2. Post text — div[dir="auto"] đầu tiên có text dài
                    const textDivs = article.querySelectorAll('div[dir="auto"]');
                    let postText = null;
                    for (const div of textDivs) {
                        const t = div.textContent.trim();
                        // Skip rỗng, quá ngắn, hoặc là số/reactions count
                        if (t && t.length > 15 && t.length < 10000 && !/^\\d+\\s*(reactions?|comments?|shares?)/i.test(t)) {
                            postText = t;
                            break;
                        }
                    }

                    // 3. Timestamp — abbr hoặc a có aria-label chứa thời gian
                    const timeEl = article.querySelector('abbr, time, a[aria-label*="phút"], a[aria-label*="giờ"], a[aria-label*="ngày"], a[href*="permalink"]');
                    const timestamp = timeEl ? (timeEl.getAttribute('title') || timeEl.getAttribute('aria-label') || timeEl.textContent.trim()) : null;

                    // 4. Reactions count
                    const reactMatch = (article.textContent || '').match(/(\\d+(?:[.,]\\d+)?[Kk]?)\\s*(?:lượt thích|reactions?|likes?)/i);
                    const reactions = reactMatch ? reactMatch[1] : null;

                    // 5. Comments count
                    const commentMatch = (article.textContent || '').match(/(\\d+(?:[.,]\\d+)?[Kk]?)\\s*(?:bình luận|comments?)/i);
                    const commentsCount = commentMatch ? commentMatch[1] : null;

                    // 6. Shares count
                    const shareMatch = (article.textContent || '').match(/(\\d+(?:[.,]\\d+)?[Kk]?)\\s*(?:chia sẻ|shares?)/i);
                    const shares = shareMatch ? shareMatch[1] : null;

                    // 7. Post URL — link permalink
                    const permalinkEl = article.querySelector('a[href*="/posts/"], a[href*="permalink"], a[href*="/videos/"], a[href*="story.php"]');
                    const postUrl = permalinkEl ? permalinkEl.href : null;

                    // 8. Media
                    const imgs = article.querySelectorAll('img[src*="scontent"]');
                    const mediaUrls = Array.from(imgs).slice(0, 4).map(img => img.src);

                    // Skip nếu thiếu data quan trọng
                    if (!postText || postText.length < 10) return;
                    if (!author) return;

                    // Dedupe bằng postUrl hoặc text hash
                    const key = postUrl || postText.substring(0, 100);
                    if (seen.has(key)) return;
                    seen.add(key);

                    results.push({
                        idx: results.length,
                        author: author,
                        author_url: authorUrl,
                        text: postText.substring(0, 5000),
                        timestamp: timestamp,
                        reactions: reactions,
                        comments_count: commentsCount,
                        shares: shares,
                        post_url: postUrl,
                        media_urls: mediaUrls,
                        scraped_at: new Date().toISOString(),
                        group_url: window.location.href,
                    });
                } catch (e) {}
            });

            return results;
        })();
        """

        res = await cdp_send(ws, "Runtime.evaluate",
                             {"expression": extract_js, "returnByValue": True},
                             msg_id=next_id())
        posts = res.get("result", {}).get("value", [])

        # Limit to max_posts
        if len(posts) > max_posts:
            posts = posts[:max_posts]

        print(f"✓ Extracted {len(posts)} posts")

        if not posts:
            print("\n⚠ 0 posts. Có thể:")
            print("  - Group không có posts")
            print("  - Cần scroll thêm hoặc login để xem feed")
            print("  - DOM structure khác → snippet selector cần update")
            return None

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_path = DATA_DIR / f"raw_group_posts_{timestamp}.json"
        raw_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        # Also save into the per-group folder (new convention)
        post_folder = manifest.post_dir
        per_post_raw = post_folder / "raw.json"
        if per_post_raw.exists():
            per_post_raw = post_folder / f"raw_{timestamp}.json"
        per_post_raw.write_text(json.dumps(posts, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        print(f"\n💾 Saved: {raw_path}")
        print(f"  + Per-post copy: {per_post_raw}")
        print(f"  Size: {raw_path.stat().st_size} bytes")
        print(f"  Posts: {len(posts)}")

        # Stats
        authors = set(p["author"] for p in posts)
        with_reactions = sum(1 for p in posts if p.get("reactions"))
        with_comments = sum(1 for p in posts if p.get("comments_count"))
        with_media = sum(1 for p in posts if p.get("media_urls"))

        print(f"\n📊 Stats:")
        print(f"  Unique authors : {len(authors)}")
        print(f"  With reactions : {with_reactions}")
        print(f"  With comments  : {with_comments}")
        print(f"  With media     : {with_media}")

        print(f"\n📋 Sample (first 3):")
        for p in posts[:3]:
            text_preview = p["text"][:80].replace("\n", " ")
            print(f"  - [{p['author']}] {text_preview}")

        # Record counts + outputs in manifest, finalize
        manifest.count("posts", len(posts))
        manifest.count("unique_authors", len(authors))
        manifest.count("with_reactions", with_reactions)
        manifest.count("with_comments", with_comments)
        manifest.count("with_media", with_media)
        manifest.output("raw", raw_path)
        manifest.output("per_post_raw", per_post_raw)
        manifest.finish(status="success")

        return raw_path


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/06_crawl_group.py <group_url> [max_posts] [max_scrolls]")
        print("Example: python3 scripts/06_crawl_group.py https://www.facebook.com/groups/<group-slug> 10")
        sys.exit(1)

    group_url = sys.argv[1]
    max_posts = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    max_scrolls = int(sys.argv[3]) if len(sys.argv) > 3 else 15

    print("=" * 60)
    print("FB GROUP CRAWL VIA CDP")
    print("=" * 60)
    print(f"Group URL   : {group_url}")
    print(f"Max posts   : {max_posts}")
    print(f"Max scrolls : {max_scrolls}")
    print("=" * 60)

    try:
        result = await crawl_group(group_url, max_posts, max_scrolls)
        if result:
            print(f"\n✓ Done. Raw file: {result}")
            print(f"\nNext: python3 scripts/04_clean_data.py {result}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())