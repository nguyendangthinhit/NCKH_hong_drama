"""API của website phân tích 1 bài viết (GĐ6). Chạy local vì cần Chrome + tài khoản phụ:

    cd serving/post_analyzer/backend
    py -3.14 -m uvicorn app:app --host 127.0.0.1 --port 8020

POST /api/jobs {url, max_comments}  tạo job (cùng link + số comment đã có -> trả job cũ, trừ khi force)
GET  /api/jobs                      danh sách job gần đây
GET  /api/jobs/{id}                 trạng thái + tiến độ
GET  /api/jobs/{id}/result          dữ liệu dashboard (job done)
GET  /api/options                   lựa chọn số comment, cấu hình ước tính
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

import settings
import job_store as js
import job_worker
from post_crawler import cache_key, validate_url
from result_view import build_view
from analysis_new.config import MAX_COMMENTS_PER_REQUEST  # noqa: E402

store = js.JobStore(settings.DB_PATH)


@asynccontextmanager
async def lifespan(_app):
    store.fail_interrupted()
    worker = job_worker.Worker(store)
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="Post Analyzer", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?",
                   allow_methods=["GET", "POST"], allow_headers=["*"])
# Chặn DNS rebinding: chỉ nhận Host local (API không có đăng nhập, điều khiển tài khoản phụ)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


class JobIn(BaseModel):
    url: str
    max_comments: int = 100
    force: bool = False


def public(job: dict) -> dict:
    """Thông tin job trả cho web (thêm vị trí trong hàng đợi)."""
    out = {k: job[k] for k in ("id", "url", "max_comments", "status", "stage", "progress_done",
                               "progress_total", "domain", "n_comments", "error", "created_at", "updated_at")}
    out["domain_info"] = job["meta"].get("domain")
    out["queue_position"] = store.queue_position(job) if job["status"] == js.QUEUED else 0
    return out


@app.get("/api/options")
def options():
    return {"comment_choices": settings.COMMENT_CHOICES, "comments_per_request": MAX_COMMENTS_PER_REQUEST}


@app.post("/api/jobs")
def create_job(body: JobIn):
    try:
        url = validate_url(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if body.max_comments not in settings.COMMENT_CHOICES:
        raise HTTPException(400, f"max_comments phải là một trong {settings.COMMENT_CHOICES} (0 = toàn bộ)")
    key = cache_key(url)
    if not body.force:
        old = store.find_reusable(key, body.max_comments)
        # job "done" mà thư mục kết quả đã bị xoá thì không dùng lại
        if old and (old["status"] != js.DONE or job_worker.load_result(old)):
            return {**public(old), "reused": True}
    return {**public(store.create(url, body.max_comments, key)), "reused": False}


@app.get("/api/jobs")
def list_jobs(limit: int = 30):
    return [public(j) for j in store.list(min(max(limit, 1), 200))]


def _get(job_id: str) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Không tìm thấy job")
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return public(_get(job_id))


@app.get("/api/jobs/{job_id}/result")
def get_result(job_id: str):
    job = _get(job_id)
    if job["status"] != js.DONE:
        raise HTTPException(409, f"Job chưa xong (trạng thái {job['status']})")
    loaded = job_worker.load_result(job)
    if not loaded:
        raise HTTPException(500, "Job đã xong nhưng thiếu file kết quả")
    full, summary, event = loaded
    return build_view(job, full, summary, event.get("post_content", ""))
