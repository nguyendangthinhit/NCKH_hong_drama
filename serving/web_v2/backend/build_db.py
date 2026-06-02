"""ETL: gộp 3 nguồn dữ liệu -> SQLite `events.db` phục vụ web_v2.

Nguồn:
  1. data/raw/data_web.json            -> sự kiện (id_content, tên, danh mục, content, actors)
  2. data/analysis-output/insights.json -> xếp hạng hot (top_events_by_comments) + phân bố cảm xúc
  3. Apps Script API (tùy chọn)         -> links[] + status theo id_content

Chạy:  python build_db.py
Tự dò repo root nên chạy ở đâu cũng được.
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from urllib.request import urlopen

# Windows console mặc định cp1252 -> ép UTF-8 để in tiếng Việt / ký tự đặc biệt
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_extractor import extract_clean_content, make_excerpt  # noqa: E402
from og_image_scraper import fetch_og_images_batch  # noqa: E402

# ── Đường dẫn ──────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]  # serving/web_v2/backend -> repo root
DATA_WEB = REPO_ROOT / "data" / "raw" / "data_web.json"
INSIGHTS = REPO_ROOT / "data" / "analysis-output" / "insights.json"
DB_PATH = BACKEND_DIR / "events.db"

APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbynT1r0tDzNhf8er-zNsDIJuQB5yfpy6VrxhDk_k83EB9FPOkYbKq1NF16nFMZ2403C/exec"
)

CATEGORY_MAP = {"showbiz": "Giải trí", "giáo dục": "Giáo dục"}


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_links_by_id() -> dict:
    """Lấy links[] + status từ Apps Script, gom theo id_content. Lỗi -> {}."""
    try:
        with urlopen(APPS_SCRIPT_URL, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        posts = raw.get("posts", raw) if isinstance(raw, dict) else raw
        out = {}
        for p in posts:
            pid = str(p.get("id", ""))
            if pid:
                out[pid] = {
                    "links": p.get("links", []) or [],
                    "status": p.get("status", ""),
                }
        print(f"  [api] lấy được links cho {len(out)} sự kiện")
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  [api] WARN không lấy được links ({e}); bỏ qua links")
        return {}


def build_hot_lookup(insights: dict) -> dict:
    """id_content -> {rank, total, clean, trash} dựa trên top_events_by_comments."""
    hot = {}
    for cat_key in ("education", "showbiz"):
        ranked = insights.get(cat_key, {}).get("top_events_by_comments", [])
        for idx, ev in enumerate(ranked):
            hot[ev["id_content"]] = {
                "rank": idx + 1,
                "total_comments": ev.get("total", 0),
                "clean_comments": ev.get("clean", 0),
                "trash_comments": ev.get("trash", 0),
            }
    return hot


def create_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        DROP TABLE IF EXISTS events;
        DROP TABLE IF EXISTS actors;

        CREATE TABLE events (
            id_content      TEXT PRIMARY KEY,
            ten_su_kien     TEXT NOT NULL,
            danh_muc        TEXT,
            platform        TEXT,
            content_full    TEXT,
            excerpt         TEXT,
            time_event      TEXT,
            links           TEXT,          -- JSON array
            status          TEXT,
            image_url       TEXT,           -- og:image scraped from first link
            total_comments  INTEGER DEFAULT 0,
            clean_comments  INTEGER DEFAULT 0,
            trash_comments  INTEGER DEFAULT 0,
            hot_rank        INTEGER,        -- NULL nếu không nằm trong top
            is_hot          INTEGER DEFAULT 0
        );

        CREATE TABLE actors (
            id_content TEXT,
            name       TEXT,
            role       TEXT,
            FOREIGN KEY (id_content) REFERENCES events(id_content)
        );

        CREATE INDEX idx_events_cat  ON events(danh_muc);
        CREATE INDEX idx_events_hot  ON events(total_comments DESC);
        """
    )


def main():
    print("→ Build events.db")
    print(f"  repo root: {REPO_ROOT}")

    data_web = load_json(DATA_WEB)
    insights = load_json(INSIGHTS)
    hot_lookup = build_hot_lookup(insights)
    links_lookup = fetch_links_by_id()

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    n_events = n_actors = n_hot = 0

    for src_key, events in data_web.items():
        danh_muc = CATEGORY_MAP.get(src_key, src_key)
        for ev in events:
            pid = ev.get("id_content")
            if not pid:
                continue

            full = extract_clean_content(ev.get("content", ""))
            excerpt = make_excerpt(full)
            hot = hot_lookup.get(pid, {})
            api = links_lookup.get(pid, {})

            conn.execute(
                """INSERT OR REPLACE INTO events
                   (id_content, ten_su_kien, danh_muc, platform, content_full,
                    excerpt, time_event, links, status, image_url, total_comments,
                    clean_comments, trash_comments, hot_rank, is_hot)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid,
                    ev.get("ten_su_kien", ""),
                    danh_muc,
                    "news",
                    full,
                    excerpt,
                    ev.get("time_event", ""),
                    json.dumps(api.get("links", []), ensure_ascii=False),
                    api.get("status", ""),
                    None,  # image_url placeholder, scraped below
                    hot.get("total_comments", 0),
                    hot.get("clean_comments", 0),
                    hot.get("trash_comments", 0),
                    hot.get("rank"),
                    1 if hot.get("rank") else 0,
                ),
            )
            n_events += 1
            if hot.get("rank"):
                n_hot += 1

            for actor in ev.get("actor_related", []) or []:
                if isinstance(actor, dict) and actor.get("name"):
                    conn.execute(
                        "INSERT INTO actors (id_content, name, role) VALUES (?,?,?)",
                        (pid, actor["name"], actor.get("role", "")),
                    )
                    n_actors += 1

    conn.commit()

    # ── OG image scraping ──────────────────────────────────────
    print("→ Scraping og:image from event links...")
    rows = conn.execute(
        "SELECT id_content, links FROM events WHERE image_url IS NULL AND links != '[]'"
    ).fetchall()

    if rows:
        url_map = []  # [(id_content, first_link), ...]
        for row in rows:
            links = json.loads(row[1] or "[]")
            if links:
                url_map.append((row[0], links[0]))

        if url_map:
            urls = [u for _, u in url_map]
            print(f"  Fetching og:image for {len(urls)} events (concurrency=10)...")
            images = asyncio.run(fetch_og_images_batch(urls, concurrency=10))

            updated = 0
            for (pid, _), img_url in zip(url_map, images):
                if img_url:
                    conn.execute(
                        "UPDATE events SET image_url = ? WHERE id_content = ?",
                        (img_url, pid),
                    )
                    updated += 1
            conn.commit()
            print(f"  ✓ Scraped {updated}/{len(urls)} images")
        else:
            print("  No events with links to scrape")
    else:
        print("  All events already have image_url or no links")

    conn.close()
    print(f"✓ Done: {n_events} sự kiện, {n_actors} actors, {n_hot} hot events")
    print(f"  DB: {DB_PATH}")


if __name__ == "__main__":
    main()
