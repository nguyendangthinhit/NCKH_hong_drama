"""Helper module for organizing scraped data into per-post folders.

Each crawl request = one folder under `data/posts/<sanitized_url>/`.
Folder structure:
  data/posts/<post_slug>/
    raw.json              — raw scraped comments
    clean.jsonl           — cleaned comments (dedup, spam filter, PII redact)
    compact.json          — for small models (compact format)
    jsonl.jsonl           — line-per-comment
    stats.json            — extraction statistics
    quarantine.jsonl      — filtered spam (optional)

Tests go under `data/tests/<test_name>/`.

Usage:
    from _data_paths import post_dir, raw_path, clean_path, compact_path, jsonl_path, stats_path, quarantine_path

    url = "https://www.facebook.com/share/p/POST_ID/"
    d = post_dir(url)
    # d = Path(__file__).resolve().parent.parent / "data" / "posts" / "share_p_POST_ID"
    raw_path(url).write_text(...)
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

# Root paths
# Project root = parent of scripts/, so data lives at <repo>/data regardless
# of where the repo is cloned or the current working directory.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POSTS_DIR = DATA_DIR / "posts"
TESTS_DIR = DATA_DIR / "tests"
ARCHIVE_DIR = DATA_DIR / "archive"


def sanitize_url(url: str) -> str:
    """Convert FB post URL to filesystem-safe folder name."""
    # Strip protocol + domain + trailing slashes
    s = url.replace("https://", "").replace("http://", "")
    s = re.sub(r"^www\.facebook\.com/", "", s)
    s = s.rstrip("/")
    # Replace / with _
    s = s.replace("/", "_")
    # Strip query params — but keep the video id of watch/?v=<id> links, otherwise every
    # watch URL collapses into the same "watch_" folder.
    if "?" in s:
        s, query = s.split("?", 1)
        m = re.search(r"(?:^|&)v=(\d+)", query)
        if m:
            s = f"{s}_v{m.group(1)}"
    # Sanitize special chars
    s = re.sub(r"[^\w\-_]", "", s)
    # Lowercase prefix, keep IDs case-sensitive (FB IDs are case-sensitive)
    return s


def post_dir(url: str) -> Path:
    """Get folder for a post URL (creates folder if missing)."""
    slug = sanitize_url(url)
    d = POSTS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def post_body_path(url: str) -> Path:
    """Path to the sidecar post-body file for a post URL.

    The main post content (author, text, images, engagement counts) is stored
    separately from raw.json (which stays a pure comment list) so existing
    consumers (list_posts, 04_clean_data.py) are untouched.
    """
    return post_dir(url) / "post.json"


def post_paths(url: str) -> dict[str, Path]:
    """Get all standard paths for a post URL."""
    d = post_dir(url)
    return {
        "raw": d / "raw.json",
        "post": d / "post.json",
        "clean": d / "clean.jsonl",
        "compact": d / "compact.json",
        "jsonl": d / "jsonl.jsonl",
        "stats": d / "stats.json",
        "quarantine": d / "quarantine.jsonl",
    }


def test_dir(test_name: str) -> Path:
    """Get folder for a test run (creates folder if missing)."""
    slug = re.sub(r"[^\w\-_]", "", test_name)
    d = TESTS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_posts() -> list[dict]:
    """List all post folders with metadata."""
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for d in sorted(POSTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        info = {"slug": d.name, "path": d}
        # Try to read metadata from raw.json
        raw = d / "raw.json"
        if raw.exists():
            try:
                import json
                data = json.loads(raw.read_text(encoding="utf-8"))
                if data and isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    info["post_url"] = first.get("post_url", "")
                    info["comments_count"] = len(data)
                    if "scraped_at" in first:
                        info["last_scraped"] = first["scraped_at"]
            except Exception:
                pass
        # Post body sidecar (post.json) — additive metadata
        post_body = d / "post.json"
        if post_body.exists():
            info["has_post_body"] = True
            try:
                import json
                pb = json.loads(post_body.read_text(encoding="utf-8"))
                if isinstance(pb, dict):
                    info["post_text_chars"] = len(pb.get("text") or "")
                    if not info.get("post_url"):
                        info["post_url"] = pb.get("post_url", "")
            except Exception:
                pass
        else:
            info["has_post_body"] = False
        # File sizes
        info["files"] = {}
        for f in d.iterdir():
            if f.is_file():
                info["files"][f.name] = f.stat().st_size
        posts.append(info)
    return posts


def legacy_filename_to_url(filename: str) -> str | None:
    """Try to reverse-engineer URL from legacy filename (for migration)."""
    # Patterns:
    # raw_comments_<TIMESTAMP>.json → no URL info (use timestamp only)
    # post_<SLUG>_full.json → SLUG is sanitized URL
    # post_<SLUG>_compact.json
    # post_<SLUG>.jsonl
    # clean_comments_<TIMESTAMP>.jsonl → no URL info
    m = re.match(r"^post_([a-zA-Z0-9_\-]+)_(?:full|compact|full_all|compact_all|all)\.(?:json|jsonl)$", filename)
    if m:
        slug = m.group(1)
        # Reverse sanitize
        return slug.replace("_", "/")
    return None


if __name__ == "__main__":
    # CLI test
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"URL: {url}")
        print(f"Slug: {sanitize_url(url)}")
        print(f"Folder: {post_dir(url)}")
        print(f"Paths:")
        for name, p in post_paths(url).items():
            print(f"  {name}: {p}")
    else:
        print("DATA_DIR:", DATA_DIR)
        print("POSTS_DIR:", POSTS_DIR)
        print()
        print("Existing posts:")
        for p in list_posts():
            print(f"  {p['slug']}: {p.get('comments_count', '?')} comments, {len(p['files'])} files")