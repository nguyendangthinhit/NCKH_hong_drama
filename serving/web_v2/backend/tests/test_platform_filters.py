import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app as backend
from platforms import preferred_platform, resolve_platform


class PlatformFilterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="event-platform-tests-")
        self.original_path = backend.DB_PATH
        backend.DB_PATH = Path(self.directory.name) / "events.db"
        with closing(sqlite3.connect(backend.DB_PATH)) as conn:
            conn.execute("""CREATE TABLE events (
                id_content TEXT PRIMARY KEY, ten_su_kien TEXT, danh_muc TEXT,
                platform TEXT, content_full TEXT, total_comments INTEGER, links TEXT)""")
            conn.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?)", [
                ("n1", "News alpha", "showbiz", "news", "", 110, "[]"),
                ("n2", "News beta", "education", "news", "", 100, "[]"),
                ("f1", "Facebook alpha", "showbiz", "facebook", "", 90, "[]"),
                ("f2", "Facebook beta", "showbiz", "facebook", "", 80, "[]"),
                ("f3", "Facebook gamma", "education", " Facebook ", "", 70, "[]"),
                ("t1", "TikTok alpha", "education", "tiktok", "", 60, "[]"),
            ])
            conn.commit()
        self.client = TestClient(backend.app)

    def tearDown(self):
        self.client.close()
        backend.DB_PATH = self.original_path
        self.directory.cleanup()

    def get_events(self, **params):
        response = self.client.get("/api/events", params=params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_platform_is_applied_before_count_and_pagination(self):
        first = self.get_events(platform="facebook", per_page=2, page=1)
        second = self.get_events(platform="facebook", per_page=2, page=2)
        self.assertEqual([row["id"] for row in first["data"]], ["f1", "f2"])
        self.assertEqual([row["id"] for row in second["data"]], ["f3"])
        self.assertEqual(first["total"], 3)
        self.assertEqual(first["total_pages"], 2)
        self.assertEqual(second["total"], 3)

    def test_source_lists_are_disjoint_and_all_sources_remain_available(self):
        ids = lambda response: {row["id"] for row in response["data"]}
        facebook = ids(self.get_events(platform="facebook"))
        news = ids(self.get_events(platform="news"))
        tiktok = ids(self.get_events(platform="tiktok"))
        all_events = self.get_events()
        self.assertFalse(facebook & news)
        self.assertEqual(facebook | news | tiktok, ids(all_events))
        self.assertEqual(all_events["total"], 6)

    def test_case_alias_category_and_keyword_filters_combine(self):
        response = self.get_events(platform=" FB ", category="education", q="gamma")
        self.assertEqual([row["id"] for row in response["data"]], ["f3"])
        self.assertEqual(response["total"], 1)

    def test_missing_source_and_injection_return_empty_results(self):
        for platform in ["missing", "facebook' OR 1=1 --"]:
            response = self.get_events(platform=platform)
            self.assertEqual(response["data"], [])
            self.assertEqual(response["total"], 0)
            self.assertEqual(response["total_pages"], 0)


class PlatformResolutionTests(unittest.TestCase):
    def test_primary_reference_and_raw_source_fallback(self):
        self.assertEqual(resolve_platform(["https://m.facebook.com/post/1"]), "facebook")
        self.assertEqual(resolve_platform(["https://fb.watch/video"]), "facebook")
        self.assertEqual(resolve_platform(["https://kenh14.vn/article.chn"]), "news")
        self.assertEqual(resolve_platform([], "https://kenh14.vn/article.chn"), "news")
        self.assertEqual(resolve_platform(["https://youtu.be/123"]), "youtube")
        self.assertEqual(resolve_platform(["https://www.tiktok.com/@channel"]), "tiktok")

    def test_explicit_metadata_wins_and_future_sources_survive(self):
        self.assertEqual(resolve_platform(["https://facebook.com/post"], platform="news"), "news")
        self.assertEqual(resolve_platform([], platform=" Mastodon "), "mastodon")

    def test_unknown_raw_metadata_does_not_hide_a_known_api_or_stored_source(self):
        for raw in ["unknown", "  ", None]:
            platform = preferred_platform(raw, "TikTok")
            self.assertEqual(resolve_platform(["https://short.example/post"], platform=platform), "tiktok")

    def test_missing_invalid_and_lookalike_urls(self):
        self.assertEqual(resolve_platform([]), "unknown")
        self.assertEqual(resolve_platform(["javascript://facebook.com/test"]), "unknown")
        self.assertEqual(resolve_platform(["https://facebook.com.example.test/test"]), "news")

    def test_known_legacy_scheme_typo_identifies_host_without_mutating_url(self):
        links = ["hhttps://tienphong.vn/article.tpo"]
        self.assertEqual(resolve_platform(links), "news")
        self.assertEqual(links, ["hhttps://tienphong.vn/article.tpo"])


if __name__ == "__main__":
    unittest.main()
