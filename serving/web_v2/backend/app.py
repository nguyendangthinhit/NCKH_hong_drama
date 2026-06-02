"""FastAPI server cho web_v2 — phục vụ sự kiện drama + xếp hạng HOT.

Chạy:  uvicorn app:app --reload --port 8000
DB:    events.db (chạy build_db.py trước)

Endpoints:
  GET /api/events?category=&q=&page=&per_page=   danh sách + lọc + phân trang
  GET /api/hot?category=&limit=                   sự kiện hot (xếp theo bình luận)
  GET /api/event/{id_content}                     chi tiết 1 sự kiện + actors
  GET /api/categories                             danh mục + số lượng
  GET /api/stats                                  thống kê tổng quan
"""

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = Path(__file__).resolve().parent / "events.db"

app = FastAPI(title="Drama Intelligence API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(503, "events.db chưa được build. Chạy: python build_db.py")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_event(row: sqlite3.Row) -> dict:
    """Map row DB -> shape thân thiện với frontend (giữ tương thích PostCard)."""
    d = dict(row)
    links = json.loads(d.get("links") or "[]")
    return {
        "id": d["id_content"],
        "id_content": d["id_content"],
        "title": d["ten_su_kien"],
        "category": d["danh_muc"],
        "platform": d.get("platform", "news"),
        "description": d.get("excerpt", ""),
        "content_full": d.get("content_full", ""),
        "time_event": d.get("time_event", ""),
        "links": links,
        "status": d.get("status", ""),
        "image_url": d.get("image_url"),
        "total_comments": d.get("total_comments", 0),
        "clean_comments": d.get("clean_comments", 0),
        "trash_comments": d.get("trash_comments", 0),
        "hot_rank": d.get("hot_rank"),
        "is_hot": bool(d.get("is_hot", 0)),
    }


@app.get("/api/events")
def list_events(
    category: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=9999),
):
    conn = get_conn()
    where, params = [], []
    if category:
        where.append("danh_muc = ?")
        params.append(category)
    if q:
        where.append("(ten_su_kien LIKE ? OR content_full LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    total = conn.execute(f"SELECT COUNT(*) FROM events {clause}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"""SELECT * FROM events {clause}
            ORDER BY total_comments DESC, id_content ASC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    return {
        "data": [row_to_event(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@app.get("/api/hot")
def hot_events(category: str | None = None, limit: int = Query(10, ge=1, le=50)):
    """Sự kiện HOT: chỉ lấy event có hot_rank, xếp theo số bình luận giảm dần."""
    conn = get_conn()
    where = ["is_hot = 1"]
    params = []
    if category:
        where.append("danh_muc = ?")
        params.append(category)
    rows = conn.execute(
        f"""SELECT * FROM events WHERE {' AND '.join(where)}
            ORDER BY total_comments DESC LIMIT ?""",
        params + [limit],
    ).fetchall()
    conn.close()
    return {"data": [row_to_event(r) for r in rows]}


@app.get("/api/event/{id_content}")
def event_detail(id_content: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM events WHERE id_content = ?", (id_content,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Không tìm thấy sự kiện")
    actors = conn.execute(
        "SELECT name, role FROM actors WHERE id_content = ?", (id_content,)
    ).fetchall()
    conn.close()
    event = row_to_event(row)
    event["actors"] = [dict(a) for a in actors]
    return event


@app.get("/api/categories")
def categories():
    conn = get_conn()
    rows = conn.execute(
        """SELECT danh_muc AS name, COUNT(*) AS count,
                  SUM(total_comments) AS comments
           FROM events GROUP BY danh_muc ORDER BY count DESC"""
    ).fetchall()
    conn.close()
    return {"data": [dict(r) for r in rows]}


@app.get("/api/stats")
def stats():
    conn = get_conn()
    row = conn.execute(
        """SELECT COUNT(*) AS total_events,
                  SUM(total_comments) AS total_comments,
                  SUM(is_hot) AS hot_events
           FROM events"""
    ).fetchone()
    conn.close()
    return dict(row)


@app.get("/")
def root():
    return {"service": "Drama Intelligence API", "version": "2.0", "docs": "/docs"}
