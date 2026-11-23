"""Worker chạy nền (1 thread): lấy job queued cũ nhất, chạy hết chuỗi cào -> chuyển định dạng ->
đoán lĩnh vực -> gán nhãn -> tổng hợp, ghi trạng thái/tiến độ vào job_store.

Mỗi lần chỉ 1 job vì crawler dùng chung 1 Chrome + tài khoản phụ.
"""

import json
import logging
import threading
import traceback
from pathlib import Path

import settings
import job_store as js
import post_analysis_runner as runner
import post_crawler
import post_to_event
from domain_detector import detect_domain
from analysis_new.event_pipeline import BadLabelResponse  # noqa: E402
from analysis_new.mmo_client import LLMExhausted, MmoClient  # noqa: E402

POLL_S = 2.0
log = logging.getLogger("post_analyzer.worker")


def job_dir(job_id: str) -> Path:
    return settings.JOBS_DIR / job_id


def event_id_for(job: dict) -> str:
    return f"post_{job['id']}"


def run_job(store, job: dict, crawl=post_crawler.crawl_post, client_factory=MmoClient.from_files) -> None:
    """Chạy 1 job tới done/failed. crawl, client_factory thay được khi test."""
    jid, out = job["id"], job_dir(job["id"])
    meta = dict(job.get("meta") or {})
    if not store.claim(jid):  # thread/tiến trình khác đã nhận job này
        return
    try:
        client = client_factory()  # đọc khoá LLM trước khi cào: thiếu khoá thì báo ngay, không cào phí
        common = crawl(job["url"], job["max_comments"], event_id_for(job), settings.CDP_PORT, out / "crawl.log")
        official = post_to_event.build_official_event(common, Path(common).parent, event_id_for(job), job["url"])
        n = post_to_event.total_comments(official)
        if n == 0:
            raise post_crawler.CrawlError("Không lấy được comment nào từ bài viết này.")
        out.mkdir(parents=True, exist_ok=True)
        (out / "event.json").write_text(json.dumps(official, ensure_ascii=False, indent=1), encoding="utf-8")
        store.update(jid, status=js.ANALYZING, stage="Đang đoán lĩnh vực bài viết", n_comments=n)

        event = post_to_event.to_internal(official)
        meta["domain"] = detect_domain(client, event)
        domain = meta["domain"]["domain"]
        store.update(jid, domain=domain, meta=meta, stage="Đang phân tích comment bằng LLM")

        def progress(done, total):
            store.update(jid, progress_done=done, progress_total=total,
                         stage=f"Đang phân tích comment bằng LLM ({done}/{total} request)")

        runner.analyze(client, event, domain, out, on_progress=progress)
        meta["requests_sent"] = getattr(client, "requests_sent", None)
        store.update(jid, status=js.DONE, stage="Hoàn tất", meta=meta)
    except (post_crawler.CrawlError, LLMExhausted, BadLabelResponse, ValueError) as e:
        store.update(jid, status=js.FAILED, error=str(e), meta=meta)
    except Exception as e:  # lỗi lạ: vẫn đánh dấu failed để hàng đợi chạy tiếp
        try:
            out.mkdir(parents=True, exist_ok=True)
            (out / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        store.update(jid, status=js.FAILED, error=f"Lỗi hệ thống: {e.__class__.__name__}: {e}", meta=meta)


class Worker(threading.Thread):
    def __init__(self, store):
        super().__init__(daemon=True, name="post-analyzer-worker")
        self.store = store
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:  # lỗi DB/đĩa không được giết thread, nếu không hàng đợi đứng im tới khi khởi động lại
                job = self.store.next_queued()
                if job:
                    run_job(self.store, job)
                    continue
            except Exception:
                log.exception("Worker gặp lỗi, thử lại sau %ss", POLL_S)
            self.stop_event.wait(POLL_S)

    def stop(self):
        self.stop_event.set()


def load_result(job: dict):
    """(full, summary, event) đã ghi của job; thiếu file -> None."""
    d = job_dir(job["id"])
    full_p, summary_p = d / "full" / f"{event_id_for(job)}.json", d / "summary" / f"{event_id_for(job)}.json"
    if not (full_p.exists() and summary_p.exists()):
        return None
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    event_p = d / "event.json"
    return read(full_p), read(summary_p), read(event_p) if event_p.exists() else {}
