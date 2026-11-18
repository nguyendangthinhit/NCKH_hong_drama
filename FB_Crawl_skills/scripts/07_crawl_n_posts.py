"""
Crawl N posts stability test: dùng URL list từ CLI argument.

Dùng cho testing — không phụ thuộc vào việc group feed có load được không.

Usage:
  # Crawl 5 posts (auto-find from group feed)
  python3 scripts/07_crawl_n_posts.py --count 5

  # Crawl 3 posts từ URL list tùy ý
  python3 scripts/07_crawl_n_posts.py --count 3 --urls \\
      "https://www.facebook.com/groups/abc/posts/POST_ID_1/" \\
      "https://www.facebook.com/groups/abc/posts/POST_ID_2/"

  # Hoặc nhập URLs từ file (1 URL/dòng)
  python3 scripts/07_crawl_n_posts.py --count 10 --urls-file urls.txt
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
import urllib.request

sys.path.insert(0, str(Path(__file__).parent))
from _run_manifest import RunManifest  # noqa: E402

import websockets

CDP_HTTP = "http://127.0.0.1:9222"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TESTS_DIR = DATA_DIR / "tests"
TESTS_DIR.mkdir(parents=True, exist_ok=True)

# N default (no URLs — user phải cung cấp qua --urls hoặc --urls-file)
DEFAULT_N = 3
# Empty by default — user must specify URLs or use --urls-file
# Otherwise, auto-find from group feed via find_more_posts()
DEFAULT_URLS: list[str] = []


async def cdp_send(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error: {resp['error']}")
            return resp.get("result", {})


async def extract_comments(ws):
    extract_js = """
    (function() {
        const results = [];
        const seen = new Set();
        const articles = document.querySelectorAll('[role="article"]');

        articles.forEach((article) => {
            try {
                const authorLinks = article.querySelectorAll('a[href*="facebook.com/"], a[role="link"]');
                let author = null;
                let profileUrl = null;
                for (const link of authorLinks) {
                    const txt = link.textContent.trim();
                    if (txt && txt.length < 60 && !/^(Xem|View|Thêm|More|Reply|Trả lời)/i.test(txt)) {
                        author = txt;
                        profileUrl = link.href.split("?")[0];
                        break;
                    }
                }

                const textDivs = article.querySelectorAll('div[dir="auto"]');
                let text = null;
                for (const div of textDivs) {
                    const t = div.textContent.trim();
                    if (t && t.length >= 2 && t.length < 5000) {
                        text = t;
                        break;
                    }
                }

                const timeEl = article.querySelector('abbr, time, a[href*="comment_id"]');
                const timestamp = timeEl ? (timeEl.getAttribute('title') || timeEl.textContent.trim()) : null;

                if (!text || !author) return;

                const key = author + '|' + text.substring(0, 100);
                if (seen.has(key)) return;
                seen.add(key);

                results.push({
                    author: author,
                    profile_url: profileUrl,
                    text: text.substring(0, 2000),
                    timestamp: timestamp,
                });
            } catch (e) {}
        });

        return results;
    })();
    """
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": extract_js, "returnByValue": True})
    return res.get("result", {}).get("value", [])


async def find_more_posts(ws, group_url: str, n_needed: int):
    """Tìm thêm N post URLs từ group feed (nếu user không cung cấp đủ URLs)."""
    print(f"  → Tìm thêm {n_needed} post URLs từ group feed ({group_url})...")

    # Navigate về group feed
    await cdp_send(ws, "Page.navigate", {"url": group_url})
    await asyncio.sleep(6)

    # Scroll để load
    for _ in range(3):
        await cdp_send(ws, "Runtime.evaluate",
                       {"expression": "window.scrollTo(0, document.body.scrollHeight)"})
        await asyncio.sleep(2)

    extract_js = """
    (function() {
        const results = [];
        const seen = new Set();
        const links = document.querySelectorAll('a[href*="/posts/"], a[href*="/permalink/"]');
        links.forEach(link => {
            const href = link.href.split("?")[0];
            if (seen.has(href)) return;
            seen.add(href);
            const parent = link.closest('[role="article"]') || link.parentElement;
            const snippet = (parent ? parent.textContent : "").substring(0, 100).replace(/\\s+/g, ' ').trim();
            results.push({url: href, snippet: snippet});
        });
        return results;
    })();
    """
    res = await cdp_send(ws, "Runtime.evaluate",
                         {"expression": extract_js, "returnByValue": True})
    return res.get("result", {}).get("value", [])


async def main():
    # ============================================================
    # Parse CLI arguments
    # ============================================================
    parser = argparse.ArgumentParser(
        description="Crawl N posts for stability testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-n", "--count", type=int, default=DEFAULT_N,
        help=f"Số lượng posts cần crawl (default: {DEFAULT_N})",
    )
    parser.add_argument(
        "--urls", nargs="+", default=None,
        help="Danh sách URLs cụ thể (space-separated). Nếu không có, auto-find từ group feed.",
    )
    parser.add_argument(
        "--urls-file", type=Path, default=None,
        help="File chứa danh sách URLs (1 URL/dòng)",
    )
    parser.add_argument(
        "--group", type=str, default="https://www.facebook.com/groups/your-group-name",
        help="Group URL để tìm thêm posts nếu --urls không đủ (replace 'your-group-name' với group slug thật)",
    )
    parser.add_argument(
        "--no-auto-find", action="store_true",
        help="Không tự động tìm thêm URLs từ group feed nếu --urls ít hơn --count",
    )
    args = parser.parse_args()

    n = args.count
    print("=" * 60)
    print(f"TEST {n} POSTS — STABILITY")
    print("=" * 60)

    # ============================================================
    # Resolve URLs
    # ============================================================
    urls = []

    if args.urls:
        urls = args.urls
    elif args.urls_file:
        if not args.urls_file.exists():
            print(f"❌ File not found: {args.urls_file}")
            sys.exit(1)
        urls = [line.strip() for line in args.urls_file.read_text().splitlines() if line.strip()]
    else:
        # No URLs provided — auto-find from group feed
        urls = DEFAULT_URLS  # empty list, will trigger auto-find
        print(f"\n⚠ No URLs provided, will auto-find {n} posts from {args.group}")

    print(f"\n📋 Initial URLs ({len(urls)}):")
    for i, u in enumerate(urls, 1):
        print(f"  {i}. {u}")

    # Auto-find thêm nếu thiếu
    if len(urls) < n and not args.no_auto_find:
        n_needed = n - len(urls)
        print(f"\n⚠ Only {len(urls)} URLs provided, need {n}. Auto-finding {n_needed} from group feed...")

    # ============================================================
    # Connect to browser
    # ============================================================
    with urllib.request.urlopen(f"{CDP_HTTP}/json") as r:
        pages = json.loads(r.read())
    tab = next((p for p in pages if p.get("type") == "page" and "facebook.com" in p.get("url", "")), None)
    if not tab:
        print("❌ Không có tab Facebook. Mở browser + login trước.")
        sys.exit(1)

    ws_url = tab["webSocketDebuggerUrl"]
    print(f"\n✓ Connected to: {tab['url'][:80]}")

    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        msg_id = 0
        def next_id():
            nonlocal msg_id
            msg_id += 1
            return msg_id

        await cdp_send(ws, "Page.enable", msg_id=next_id())

        # Auto-find nếu cần
        if len(urls) < n and not args.no_auto_find:
            n_needed = n - len(urls)
            found = await find_more_posts(ws, args.group, n_needed)
            print(f"  → Found {len(found)} posts in group feed")
            # Lấy URLs chưa có trong list
            existing = set(urls)
            for post in found:
                if post["url"] not in existing:
                    urls.append(post["url"])
                    existing.add(post["url"])
                    if len(urls) >= n:
                        break

        # Cắt theo n
        urls = urls[:n]
        print(f"\n→ Crawling {len(urls)} posts:")
        for i, u in enumerate(urls, 1):
            print(f"  {i}. {u}")

        # ============================================================
        # Crawl từng post
        # ============================================================
        results = []
        for idx, post_url in enumerate(urls):
            print(f"\n--- Post {idx+1}/{len(urls)} ---")
            print(f"  Navigate: {post_url}")
            await cdp_send(ws, "Page.navigate", {"url": post_url}, msg_id=next_id())
            await asyncio.sleep(6)

            # Scroll
            for s in range(3):
                await cdp_send(ws, "Runtime.evaluate",
                               {"expression": "window.scrollTo(0, document.body.scrollHeight)"})
                await asyncio.sleep(2)

            comments = await extract_comments(ws)
            print(f"  ✓ Got {len(comments)} comments")

            results.append({
                "post_idx": idx + 1,
                "post_url": post_url,
                "comments": comments,
            })

        # ============================================================
        # Save outputs
        # ============================================================
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use tests/<n>posts_<ts>/ folder structure (consistent with other test runs)
        run_dir = TESTS_DIR / f"{n}posts_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Manifest for this batch run
        manifest = RunManifest(
            run_dir,
            script="07_crawl_n_posts.py",
            input_url=args.group,
            input_args={
                "count": n,
                "urls": list(urls),
                "no_auto_find": args.no_auto_find,
            },
        )
        manifest.count("posts_attempted", len(results))
        manifest.count("total_comments",
                       sum(len(p["comments"]) for p in results))
        manifest.count("unique_authors", len(set(
            c["author"] for p in results for c in p["comments"]
        )))

        # Full (debug)
        full_path = run_dir / "full.json"
        full_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        # Compact for small model: {a, t, ts} format
        compact_posts = []
        for post in results:
            compact_posts.append({
                "url": post["post_url"].split("?")[0],
                "n": len(post["comments"]),
                "comments": [
                    {"a": c["author"][:30], "t": c["text"][:300], "ts": c.get("timestamp") or ""}
                    for c in post["comments"]
                ],
            })

        all_authors = set()
        for post in results:
            for c in post["comments"]:
                all_authors.add(c["author"])

        compact = {
            "summary": {
                "posts": len(results),
                "total_comments": sum(len(p["comments"]) for p in results),
                "unique_authors": len(all_authors),
            },
            "posts": compact_posts,
        }

        compact_path = run_dir / "compact.json"
        compact_path.write_text(json.dumps(compact, ensure_ascii=False, indent=2), encoding="utf-8")

        # JSONL
        jsonl_path = run_dir / "compact.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for post in results:
                for c in post["comments"]:
                    f.write(json.dumps({
                        "post_idx": post["post_idx"],
                        "post_url": post["post_url"].split("?")[0],
                        **c,
                    }, ensure_ascii=False) + "\n")

        # Finalize manifest
        manifest.output("full", full_path)
        manifest.output("compact", compact_path)
        manifest.output("jsonl", jsonl_path)
        manifest.finish(status="success")

        # ============================================================
        # Summary
        # ============================================================
        print(f"\n{'=' * 60}")
        print(f"✅ DONE — {n} posts")
        print(f"{'=' * 60}")
        print(f"Run folder: {run_dir}")
        print(f"  Full    : {full_path}")
        print(f"  Compact : {compact_path}  ← dùng cho model nhỏ")
        print(f"  JSONL   : {jsonl_path}")
        print()
        print(f"Summary: {json.dumps(compact['summary'], ensure_ascii=False)}")

    print(f"\nPer-post:")
    for i, p in enumerate(compact_posts, 1):
        url_short = p["url"][-50:]
        print(f"  Post {i}: ...{url_short} — {p['n']} comments")


if __name__ == "__main__":
    asyncio.run(main())