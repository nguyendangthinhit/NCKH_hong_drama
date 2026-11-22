"""Offline tests: Sheet mapping, safe dispatch, fresh outputs and resume."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "crawl-facebook-pending-sheet.py"
SPEC = importlib.util.spec_from_file_location("facebook_sheet_wrapper", SCRIPT)
wrapper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wrapper
SPEC.loader.exec_module(wrapper)
HEADER = ["Thể loại", "id_content", "Tên sự kiện", "Links", "Status"]
URL = "https://www.facebook.com/page/posts/123"
SHEET_URL = "https://docs.google.com/spreadsheets/d/test-sheet/edit?gid=1"


def sheet_row(event="showbiz_055", url=URL, status="pending", name="Sự kiện A"):
    return ["Giải trí", event, name, url, status]


def common(event="showbiz_055", cid="99"):
    return {"comment_id": cid, "event_id": event, "platform": "facebook",
            "post_id": "123", "reply_to_id": None, "text": "Bình luận"}


class SheetWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "crawler-output"
        self.folder.mkdir()
        self.args = SimpleNamespace(crawler=wrapper.DEFAULT_CRAWLER, output=self.root,
                                    target=0, max_rounds=50, click_pause=4.0,
                                    cdp_url="http://127.0.0.1:9333", timeout=30)
        self.job = wrapper.Job("showbiz_055", "Sự kiện A", URL, [2])

    def test_selects_pending_and_deduplicates_multiple_links(self):
        rows = [HEADER, sheet_row(status="Done"), sheet_row(url=URL + "/\n" + URL),
                sheet_row(status=" Pending "), sheet_row(status="error")]
        jobs = wrapper.pending_jobs(rows)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].sheet_rows, [3, 4])
        self.assertEqual(jobs[0].event_id, "showbiz_055")

    def test_missing_id_is_not_inherited(self):
        with self.assertRaisesRegex(ValueError, "Row 3"):
            wrapper.pending_jobs([HEADER, sheet_row(), sheet_row(event="")])

    def test_conflicting_event_for_same_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "assigned to both"):
            wrapper.pending_jobs([HEADER, sheet_row(), sheet_row(event="showbiz_056")])

    def test_bad_host_and_event_path_rejected(self):
        for row in [sheet_row(url="https://facebook.com.attacker.test/posts/1"),
                    sheet_row(event="../escape"), sheet_row(url=""),
                    sheet_row(url="https://example.com")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                wrapper.pending_jobs([HEADER, row])

    def test_missing_or_duplicate_columns_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing Sheet"):
            wrapper.pending_jobs([["Links", "Status"]])
        with self.assertRaisesRegex(ValueError, "Duplicate Sheet"):
            wrapper.pending_jobs([HEADER + ["status"]])

    def test_dispatch_passes_event_and_disables_browser_relaunch(self):
        command = wrapper.command_for(self.job, self.args)
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[2], URL)
        self.assertEqual(command[command.index("--event-id") + 1], "showbiz_055")
        self.assertIn("--no-relaunch", command)
        self.assertEqual(command[command.index("--crash-retries") + 1], "0")

    def test_edge_cdp_is_rejected(self):
        from io import BytesIO
        with patch.object(wrapper, "urlopen", return_value=BytesIO(b'{"Browser":"Edg/157"}')):
            with self.assertRaisesRegex(RuntimeError, "not Google Chrome"):
                wrapper.chrome_preflight(self.args.cdp_url)

    def test_exit_zero_without_new_output_is_failure(self):
        old = self.folder / "common.jsonl"
        old.write_text(json.dumps(common()) + "\n", encoding="utf-8")
        with patch.object(wrapper, "crawler_folder", return_value=self.folder), \
             patch.object(wrapper.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(RuntimeError, "got 0"):
                wrapper.crawl_job(self.job, self.args)

    def test_fresh_output_snapshot_and_event_merge(self):
        def fake_crawl(command, **kwargs):
            self.assertEqual(kwargs["env"]["FB_CDP_HTTP"], self.args.cdp_url)
            (self.folder / "common.jsonl").write_text(json.dumps(common()) + "\n", encoding="utf-8")
            return SimpleNamespace(returncode=0)
        with patch.object(wrapper, "crawler_folder", return_value=self.folder), \
             patch.object(wrapper.subprocess, "run", side_effect=fake_crawl):
            record = wrapper.crawl_job(self.job, self.args)
        self.assertTrue(wrapper.reusable(record, self.job.event_id))
        state = {"jobs": {self.job.key: record}}
        wrapper.export_events(state, self.root)
        result = json.loads((self.root / "events/showbiz_055.json").read_text(encoding="utf-8"))
        self.assertEqual(result["id_content"], "showbiz_055")
        self.assertEqual(result["comments_count"], 1)
        self.assertEqual(result["comments"][0]["comment_id"], "99")

    def test_wrong_event_output_cannot_be_reused(self):
        path = self.root / "wrong.jsonl"
        path.write_text(json.dumps(common("showbiz_999")) + "\n", encoding="utf-8")
        self.assertFalse(wrapper.reusable({"status": "success", "common_file": str(path)}, "showbiz_055"))

    def test_preview_does_not_call_crawler_or_chrome(self):
        with patch.object(wrapper, "read_sheet", return_value=[HEADER, sheet_row()]), \
             patch.object(wrapper, "crawl_job") as crawl, \
             patch.object(wrapper, "chrome_preflight") as chrome:
            self.assertEqual(wrapper.main(["--sheet-url", SHEET_URL, "--output", str(self.root)]), 0)
            crawl.assert_not_called()
            chrome.assert_not_called()
        self.assertTrue((self.root / "pending-plan.json").exists())

    def test_resume_skips_completed_before_applying_limit(self):
        path = self.root / "saved.jsonl"
        path.write_text(json.dumps(common()) + "\n", encoding="utf-8")
        wrapper.atomic_json(self.root / "state.json", {"jobs": {
            self.job.key: {"status": "success", "common_file": str(path)}}})
        rows = [HEADER, sheet_row(), sheet_row(url="https://facebook.com/page/posts/456")]
        with patch.object(wrapper, "read_sheet", return_value=rows):
            self.assertEqual(wrapper.main(["--sheet-url", SHEET_URL, "--output", str(self.root), "--limit", "1"]), 0)
        plan = json.loads((self.root / "pending-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["jobs"][0]["url"], "https://facebook.com/page/posts/456")

    def test_run_saves_failure_then_retries_and_resumes_success(self):
        rows = [HEADER, sheet_row()]
        arguments = ["--run", "--sheet-url", SHEET_URL, "--output", str(self.root), "--limit", "1"]
        with patch.object(wrapper, "read_sheet", return_value=rows), \
             patch.object(wrapper, "chrome_preflight"), \
             patch.object(wrapper, "crawl_job", side_effect=RuntimeError("No new output")):
            self.assertEqual(wrapper.main(arguments), 1)
        state = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["jobs"][self.job.key]["status"], "failed")
        self.assertFalse((self.root / ".running.lock").exists())
        snapshot = self.root / "saved.jsonl"
        snapshot.write_text(json.dumps(common()) + "\n", encoding="utf-8")
        result = {"status": "success", "event_id": "showbiz_055", "event_name": "Sự kiện A",
                  "url": URL, "sheet_rows": [2], "count": 1, "common_file": str(snapshot)}
        with patch.object(wrapper, "read_sheet", return_value=rows), \
             patch.object(wrapper, "chrome_preflight"), \
             patch.object(wrapper, "crawl_job", return_value=result) as crawl:
            self.assertEqual(wrapper.main(arguments), 0)
            self.assertEqual(wrapper.main(arguments), 0)
            self.assertEqual(crawl.call_count, 1)
        self.assertTrue((self.root / "events/showbiz_055.json").exists())
        self.assertFalse((self.root / ".running.lock").exists())

    def test_disconnect_does_not_record_failure_or_start_next_job(self):
        rows = [HEADER, sheet_row(), sheet_row(url=URL + "4")]
        with patch.object(wrapper, "read_sheet", return_value=rows), \
             patch.object(wrapper, "chrome_preflight", side_effect=[None, None, OSError("offline")]), \
             patch.object(wrapper, "crawl_job", side_effect=RuntimeError("Crawler exit 1")) as crawl:
            with self.assertRaisesRegex(RuntimeError, "Paused on .*Chrome CDP unavailable"):
                wrapper.main(["--run", "--sheet-url", SHEET_URL, "--output", str(self.root)])
        self.assertEqual(crawl.call_count, 1)
        self.assertFalse((self.root / "state.json").exists())
        self.assertFalse((self.root / ".running.lock").exists())

    def test_retry_plan_recrawls_success_once_and_preserves_previous_comments(self):
        snapshot = self.root / "saved.jsonl"
        original = "".join(json.dumps(common(cid=cid)) + "\n" for cid in ("98", "99"))
        snapshot.write_text(original, encoding="utf-8")
        wrapper.atomic_json(self.root / "state.json", {"jobs": {
            self.job.key: {"status": "success", "common_file": str(snapshot), "count": 2}}})
        plan = self.root / "retry.json"
        wrapper.atomic_json(plan, {"jobs": [
            {"event_id": self.job.event_id, "event_name": self.job.event_name,
             "url": self.job.url, "sheet_rows": self.job.sheet_rows}]})
        checkpoint = self.folder / "checkpoint.json"
        checkpoint.write_text('{"round": 10}', encoding="utf-8")

        def fake_crawl(command, **kwargs):
            self.assertFalse(checkpoint.exists())
            rows = [common(cid="99"), common(cid="100")]
            (self.folder / "common.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            return SimpleNamespace(returncode=0)

        arguments = ["--run", "--output", str(self.root), "--retry-plan", str(plan)]
        with patch.object(wrapper, "chrome_preflight"), \
             patch.object(wrapper, "crawler_folder", return_value=self.folder), \
             patch.object(wrapper, "read_sheet") as read_sheet, \
             patch.object(wrapper.subprocess, "run", side_effect=fake_crawl) as crawl:
            self.assertEqual(wrapper.main(arguments), 0)
            self.assertEqual(wrapper.main(arguments), 0)
        read_sheet.assert_not_called()
        self.assertEqual(crawl.call_count, 1)
        self.assertEqual(snapshot.read_text(encoding="utf-8"), original)
        state = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        record = state["jobs"][self.job.key]
        self.assertEqual(record["count"], 3)
        self.assertEqual(record["last_retry_count"], 2)
        self.assertNotEqual(record["common_file"], str(snapshot))
        self.assertEqual(len(list(self.folder.glob("checkpoint-retry-*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
