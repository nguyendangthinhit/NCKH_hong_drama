"""Test offline post_analyzer: job store, chuyển định dạng, đoán lĩnh vực, chạy job đủ chuỗi, API.

Crawler và LLM được thay bằng bản giả (không mở Chrome, không gọi mạng)."""

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[2]
sys.path[:0] = [str(BACKEND), str(ROOT)]
# import app tạo JobStore ở DATA_DIR: trỏ sang thư mục tạm để không đụng DB thật của server đang chạy
os.environ.setdefault("POST_ANALYZER_DATA_DIR", tempfile.mkdtemp(prefix="post-analyzer-test-"))

import pytest  # noqa: E402

import settings  # noqa: E402
import job_store as js  # noqa: E402
import job_worker  # noqa: E402
from domain_detector import detect_domain, parse_domain  # noqa: E402
from post_crawler import CrawlError, validate_url  # noqa: E402
from analysis_new.tests.fake_llm import FakeLLM  # noqa: E402

URL = "https://www.facebook.com/kenh14/posts/123"
ROWS = [
    {"comment_id": "c1", "reply_to_id": None, "text": "Ca sĩ này hát hay mà sao bị chê dữ vậy"},
    {"comment_id": "c2", "reply_to_id": "c1", "text": "Hay chỗ nào, hát phô thấy rõ"},
    {"comment_id": "c3", "reply_to_id": "c2", "text": "Mỗi người một gu thôi bạn"},
    {"comment_id": "c4", "reply_to_id": None, "text": "Showbiz bây giờ toàn drama, chán thật sự"},
    {"comment_id": "c5", "reply_to_id": "zz", "text": "Reply của comment không cào được vẫn giữ lại"},
]


class FakeClient(FakeLLM):
    """FakeLLM của analysis_new + trả lời câu hỏi lĩnh vực."""

    def __init__(self, domain_reply='{"domain": "showbiz", "reason": "nghệ sĩ"}', label="Cà khịa"):
        super().__init__(label)
        self.domain_reply = domain_reply

    def complete(self, prompt):
        if "phân loại một bài viết" in prompt:
            self.requests_sent += 1
            return self.domain_reply, "fake"
        return super().complete(prompt)


def fake_crawl(tmp_path, rows=ROWS):
    def crawl(url, max_comments, event_id, port, log_path):
        folder = tmp_path / "posts" / "p1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "post.json").write_text(json.dumps({"text": "Ca sĩ X bị chê hát phô"}), encoding="utf-8")
        common = folder / "common.jsonl"
        common.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows[: max_comments or None]),
                          encoding="utf-8")
        return common
    return crawl


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "JOBS_DIR", tmp_path / "jobs")
    return js.JobStore(tmp_path / "jobs.db")


def test_validate_url_only_facebook():
    assert validate_url("  https://www.facebook.com/x/posts/1 ") == "https://www.facebook.com/x/posts/1"
    assert validate_url("https://fb.watch/abc/")
    for bad in ("https://youtube.com/watch?v=1", "facebook.com/x", "https://evilfacebook.com/x", "",
                "https://l.facebook.com/l.php?u=https://evil.com", "https://www.facebook.com/"):
        with pytest.raises(ValueError):
            validate_url(bad)


def test_store_reuse_queue_and_interrupt(store):
    a = store.create(URL, 50)
    b = store.create("https://www.facebook.com/other/posts/9", 50)
    assert store.next_queued()["id"] == a["id"]
    assert store.claim(a["id"]) is True and store.claim(a["id"]) is False  # nhận job nguyên tử
    store.update(a["id"], status=js.QUEUED)
    assert store.queue_position(b) == 1
    assert store.find_reusable(URL, 50)["id"] == a["id"]
    assert store.find_reusable(URL, 100) is None
    store.update(a["id"], status=js.CRAWLING, meta={"x": 1})
    assert store.get(a["id"])["meta"] == {"x": 1}
    assert store.fail_interrupted() == 1
    assert store.get(a["id"])["status"] == js.FAILED
    assert store.find_reusable(URL, 50) is None  # job failed không được dùng lại
    with pytest.raises(ValueError):
        store.update(a["id"], url="x")


def test_parse_domain_variants():
    assert parse_domain('```json\n{"domain": "education", "reason": "thi cử"}\n```') == ("education", "thi cử")
    assert parse_domain("Lĩnh vực: showbiz")[0] == "showbiz"
    assert parse_domain("không biết")[0] is None
    res = detect_domain(FakeClient("???"), {"post_title": "abc", "comments": []})
    assert res["domain"] == "showbiz" and res["source"] == "default"


def test_run_job_end_to_end_showbiz(store, tmp_path):
    job = store.create(URL, 0)
    job_worker.run_job(store, job, crawl=fake_crawl(tmp_path), client_factory=FakeClient)
    done = store.get(job["id"])
    assert done["status"] == js.DONE, done["error"]
    assert done["n_comments"] == 5 and done["domain"] == "showbiz"
    assert done["progress_done"] == done["progress_total"] > 0
    full, summary, event = job_worker.load_result(done)
    assert {c["id"] for c in full["comments"]} == {"c1", "c2", "c3", "c4", "c5"}
    assert event["comments"][0]["replies"][0]["replies"][0]["comment_id"] == "c3"  # cây 3 tầng giữ nguyên

    from result_view import build_view
    view = build_view(done, full, summary, event["post_content"])
    assert view["domain_name"] == "Showbiz" and view["totals"]["comments"] == 5
    assert sum(x["count"] for x in view["labels"]) == view["totals"]["valid"]
    assert view["toxic"] is not None and view["clusters"]


def test_run_job_education_has_conclusion(store, tmp_path):
    job = store.create(URL, 0)
    client = lambda: FakeClient('{"domain": "education"}', label="tích cực")  # noqa: E731
    job_worker.run_job(store, job, crawl=fake_crawl(tmp_path), client_factory=client)
    done = store.get(job["id"])
    assert done["status"] == js.DONE and done["domain"] == "education"
    from result_view import build_view
    view = build_view(done, *job_worker.load_result(done)[:2], "")
    assert view["toxic"] is None and view["conclusion"]["focus"] == "f"


def test_run_job_crawl_error_marks_failed(store, tmp_path):
    def broken(*_a):
        raise CrawlError("bài riêng tư")
    job = store.create(URL, 50)
    job_worker.run_job(store, job, crawl=broken, client_factory=FakeClient)
    j = store.get(job["id"])
    assert j["status"] == js.FAILED and "riêng tư" in j["error"]


def test_run_job_zero_comments_failed(store, tmp_path):
    job = store.create(URL, 50)
    job_worker.run_job(store, job, crawl=fake_crawl(tmp_path, rows=[]), client_factory=FakeClient)
    assert store.get(job["id"])["status"] == js.FAILED


def test_api_create_reuse_and_validate(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app as app_mod
    monkeypatch.setattr(app_mod, "store", js.JobStore(tmp_path / "api.db"))
    monkeypatch.setattr(job_worker.Worker, "start", lambda self: None)  # không chạy worker thật
    with TestClient(app_mod.app) as c:
        assert c.get("/api/options").json()["comment_choices"] == settings.COMMENT_CHOICES
        assert c.post("/api/jobs", json={"url": "https://youtube.com/x", "max_comments": 50}).status_code == 400
        assert c.post("/api/jobs", json={"url": URL, "max_comments": 77}).status_code == 400
        first = c.post("/api/jobs", json={"url": URL, "max_comments": 50}).json()
        again = c.post("/api/jobs", json={"url": URL, "max_comments": 50}).json()
        assert first["reused"] is False and again["reused"] is True and again["id"] == first["id"]
        tracked = c.post("/api/jobs", json={"url": URL + "?mibextid=abc", "max_comments": 50}).json()
        assert tracked["id"] == first["id"]  # cùng bài, khác query theo dõi -> vẫn dùng lại
        assert c.get("/api/options", headers={"Host": "evil.example"}).status_code == 400  # chặn DNS rebinding
        forced = c.post("/api/jobs", json={"url": URL, "max_comments": 50, "force": True}).json()
        assert forced["id"] != first["id"] and forced["queue_position"] == 1
        assert c.get(f"/api/jobs/{first['id']}/result").status_code == 409
        assert c.get("/api/jobs/nope").status_code == 404
        assert len(c.get("/api/jobs").json()) == 2
