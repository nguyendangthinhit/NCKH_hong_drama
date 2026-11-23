"""Lưu job phân tích bài viết trong SQLite (1 bảng `jobs`).

Trạng thái: queued -> crawling -> analyzing -> done | failed.
Mỗi hàm mở kết nối riêng nên dùng được từ thread worker lẫn request API.
"""

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path

QUEUED, CRAWLING, ANALYZING, DONE, FAILED = "queued", "crawling", "analyzing", "done", "failed"
ACTIVE = (QUEUED, CRAWLING, ANALYZING)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,
    max_comments INTEGER NOT NULL,
    status TEXT NOT NULL,
    stage TEXT DEFAULT '',
    progress_done INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    domain TEXT DEFAULT '',
    n_comments INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    meta TEXT DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(url_hash, max_comments, status);
"""

FIELDS = ("stage", "status", "progress_done", "progress_total", "domain", "n_comments", "error", "meta")


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


class JobStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row(r) -> dict:
        if r is None:
            return None
        d = dict(r)
        d["meta"] = json.loads(d.get("meta") or "{}")
        return d

    def create(self, url: str, max_comments: int, key: str = None) -> dict:
        """key: khoá dùng lại kết quả (mặc định chính link)."""
        now = time.time()
        job_id = uuid.uuid4().hex[:12]
        with self._conn() as c:
            c.execute("INSERT INTO jobs (id, url, url_hash, max_comments, status, created_at, updated_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?)", (job_id, url, url_hash(key or url), max_comments, QUEUED, now, now))
        return self.get(job_id)

    def get(self, job_id: str):
        with self._conn() as c:
            return self._row(c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())

    def list(self, limit: int = 50) -> list:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(r) for r in rows]

    def find_reusable(self, key: str, max_comments: int):
        """Job cùng khoá bài + cùng số comment đang chạy hoặc đã xong (mới nhất) -> dùng lại, khỏi cào lại."""
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE url_hash = ? AND max_comments = ? AND status != ? "
                          "ORDER BY created_at DESC LIMIT 1", (url_hash(key), max_comments, FAILED)).fetchone()
        return self._row(r)

    def next_queued(self):
        with self._conn() as c:
            return self._row(c.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                                       (QUEUED,)).fetchone())

    def claim(self, job_id: str) -> bool:
        """Chuyển queued -> crawling nguyên tử; False nếu tiến trình/thread khác đã nhận job này."""
        with self._conn() as c:
            cur = c.execute("UPDATE jobs SET status = ?, stage = ?, updated_at = ? WHERE id = ? AND status = ?",
                            (CRAWLING, "Đang cào comment từ Facebook", time.time(), job_id, QUEUED))
            return cur.rowcount == 1

    def update(self, job_id: str, **fields) -> None:
        bad = set(fields) - set(FIELDS)
        if bad:
            raise ValueError(f"Trường không hợp lệ: {bad}")
        if "meta" in fields:
            fields["meta"] = json.dumps(fields["meta"], ensure_ascii=False)
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE jobs SET {cols}, updated_at = ? WHERE id = ?",
                      (*fields.values(), time.time(), job_id))

    def fail_interrupted(self) -> int:
        """Lúc khởi động: job đang cào/phân tích dở (server bị tắt) -> failed để người dùng chạy lại."""
        with self._conn() as c:
            cur = c.execute("UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE status IN (?, ?)",
                            (FAILED, "Server bị tắt khi job đang chạy; hãy gửi lại link.", time.time(),
                             CRAWLING, ANALYZING))
            return cur.rowcount

    def queue_position(self, job: dict) -> int:
        """Số job đang chạy hoặc chờ phía trước (0 = sắp tới lượt)."""
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM jobs WHERE status IN (?, ?, ?) AND created_at < ?",
                             (*ACTIVE, job["created_at"])).fetchone()[0]
