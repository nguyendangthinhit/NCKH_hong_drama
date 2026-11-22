"""Test offline: đọc/ghi bảng link (trạng thái pending/done) và chuyển common.jsonl -> định dạng analysis_new."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "ingestion")]

import pytest  # noqa: E402

from analysis_new.thread_loader import build_clusters, normalize_event  # noqa: E402
from crawl_links_from_sheet import max_rounds_for  # noqa: E402
from crawl_sheet_io import DONE, PENDING, CrawlSheet  # noqa: E402
from crawled_posts_to_analysis_events import build_tree  # noqa: E402

HEADER = ["STT", "Mã sự kiện", "Nhóm", "Tên sự kiện", "Trang hoặc nhóm đăng", "Ngày đăng",
          "Link Facebook", "Số bình luận hiển thị", "Số bình luận (số)", "Nguồn", "Trạng thái"]


def row(n, status="pending"):
    return [n, "showbiz_064", "Giải trí", "Erik xin lỗi", "Kenh14", "2026-08-23",
            f"https://www.facebook.com/reel/{n}/", "1,987", 1987, "File 55", status]


def write_sheet(tmp_path, rows, header=HEADER):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    ws["A1"].font = ws["A1"].font.copy(bold=True)
    p = tmp_path / "cao.xlsx"
    wb.save(p)
    return p


def test_sheet_reads_columns_by_header_and_keeps_format(tmp_path):
    p = write_sheet(tmp_path, [row(1), row(2, status="")])
    s = CrawlSheet.load(p)
    r = s.rows()
    assert (r[0]["event_id"], r[0]["n_comments"], r[0]["status"], r[0]["page"]) == ("showbiz_064", 1987, PENDING, "Kenh14")
    assert r[1]["status"] == PENDING  # ô trống -> pending
    CrawlSheet.mark(p, "https://www.facebook.com/reel/1/", DONE)
    from openpyxl import load_workbook
    ws = load_workbook(p).active
    assert ws["K2"].value == DONE and ws["J2"].value == "File 55" and ws["A1"].font.bold


def test_sheet_adds_status_column_when_missing(tmp_path):
    p = write_sheet(tmp_path, [row(1)[:10]], HEADER[:10])
    s = CrawlSheet.load(p)
    assert not s.has_status_col and s.rows()[0]["status"] == PENDING
    s.save()
    assert CrawlSheet.load(p).has_status_col


def test_sheet_rejects_missing_link_column(tmp_path):
    p = write_sheet(tmp_path, [row(1)], [h.replace("Link Facebook", "Link") for h in HEADER])
    with pytest.raises(ValueError):
        CrawlSheet.load(p)


def test_build_tree_nests_replies_and_feeds_analysis():
    rows = [
        {"comment_id": "a", "reply_to_id": None, "text": "gốc 1"},
        {"comment_id": "b", "reply_to_id": "a", "text": "reply a"},
        {"comment_id": "c", "reply_to_id": "b", "text": "reply b"},
        {"comment_id": "d", "reply_to_id": "zzz", "text": "cha không lấy được"},
        {"comment_id": "a", "reply_to_id": None, "text": "trùng"},
    ]
    tree = build_tree(rows)
    assert [c["comment_id"] for c in tree] == ["a", "d"]
    assert tree[0]["reply_count"] == 1 and tree[0]["replies"][0]["replies"][0]["comment_id"] == "c"
    assert tree[1]["reply_to_id"] is None
    event = normalize_event({"id_content": "showbiz_x", "event_name": "x", "post_content": "",
                             "comments": tree}, "showbiz_x")
    clusters = build_clusters(event)
    assert [n["level"] for n in clusters[0]["nodes"]] == [1, 2, 3]
    assert len(clusters) == 2


def test_max_rounds_scales_with_comment_count():
    assert max_rounds_for(100, 0) == 50
    assert max_rounds_for(27558, 0) == 3444
    assert max_rounds_for(27558, 500) == 500


def test_mark_only_changes_its_row(tmp_path):
    p = write_sheet(tmp_path, [row(1), row(2)])
    CrawlSheet.mark(p, "https://www.facebook.com/reel/1/", DONE)
    CrawlSheet.mark(p, "https://www.facebook.com/reel/2/", DONE)
    assert [r["status"] for r in CrawlSheet.load(p).rows()] == [DONE, DONE]


def test_lock_blocks_second_terminal(tmp_path, monkeypatch):
    import crawl_links_from_sheet as m
    monkeypatch.setattr(m, "post_folder", lambda url: tmp_path / "post")
    first = m.try_lock("u", 9222)
    assert first and m.try_lock("u", 9223) is None
    first.unlink()
    assert m.try_lock("u", 9223)


def test_reel_links_crawl_as_watch_with_unique_folder():
    from crawl_links_from_sheet import crawl_url, post_folder
    assert crawl_url("https://www.facebook.com/reel/123/") == "https://www.facebook.com/watch/?v=123"
    assert crawl_url("https://www.facebook.com/K14vn/posts/pfbidX") == "https://www.facebook.com/K14vn/posts/pfbidX"
    assert post_folder("https://www.facebook.com/reel/123/").name == "watch__v123"
    assert post_folder("https://www.facebook.com/reel/123/") != post_folder("https://www.facebook.com/reel/456/")
