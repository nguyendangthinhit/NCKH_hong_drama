"""Offline tests for scripts/_common_schema.py (raw FB comments -> shared schema)."""
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _common_schema import (COMMON_FIELDS, filter_to_post, parse_author_id,  # noqa: E402
                            parse_comment_link, parse_post_id_from_url, relative_to_iso,
                            to_common_rows)

POST = "https://www.facebook.com/tinhte/posts/pfbid02mL2Ad"
SCRAPED = "2026-11-14T18:00:00.000Z"


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode().rstrip("=")


def test_comment_link_base64_top_level_and_reply():
    top = parse_comment_link(f"{POST}?comment_id={_b64('comment:111_222')}&__cft__=x")
    assert top == {"comment_id": "222", "parent_id": None, "post_id": "111"}
    rep = parse_comment_link(
        f"{POST}?comment_id={_b64('comment:111_222')}&reply_comment_id={_b64('comment:111_333')}")
    assert rep == {"comment_id": "333", "parent_id": "222", "post_id": "111"}


def test_comment_link_numeric_and_missing():
    assert parse_comment_link(f"{POST}?comment_id=222")["comment_id"] == "222"
    assert parse_comment_link(None)["comment_id"] is None
    assert parse_comment_link(POST)["comment_id"] is None


def test_author_id_variants():
    assert parse_author_id("https://www.facebook.com/profile.php?id=1000123&comment_id=x") == "1000123"
    assert parse_author_id("https://www.facebook.com/minh.an.9?comment_id=x") == "minh.an.9"
    assert parse_author_id("https://www.facebook.com/people/Ten-A/1000456/") == "1000456"
    assert parse_author_id("https://www.facebook.com/groups/abc/user/1000789/") == "1000789"
    assert parse_author_id("https://www.facebook.com/hashtag/abc") is None
    assert parse_author_id(None) is None


def test_post_id_from_url():
    assert parse_post_id_from_url("https://www.facebook.com/permalink.php?story_fbid=55&id=1") == "55"
    assert parse_post_id_from_url("https://www.facebook.com/baodantri/posts/1110630964511903") \
        == "1110630964511903"
    assert parse_post_id_from_url("https://www.facebook.com/share/p/1Fk/") is None


def test_relative_time_vi_en():
    assert relative_to_iso("8 giờ trước", SCRAPED) == "2026-11-14T10:00:00+00:00"
    assert relative_to_iso("khoảng 1 giờ trước", SCRAPED) == "2026-11-14T17:00:00+00:00"
    assert relative_to_iso("20 phút trước", SCRAPED) == "2026-11-14T17:40:00+00:00"
    assert relative_to_iso("32 tuần trước", SCRAPED).startswith("2026-04-04")
    assert relative_to_iso("Hôm qua", SCRAPED).startswith("2026-11-13")
    assert relative_to_iso("a week ago", SCRAPED).startswith("2026-11-07")
    assert relative_to_iso("12 hours ago", SCRAPED) == "2026-11-14T06:00:00+00:00"
    assert relative_to_iso("2h", SCRAPED) == "2026-11-14T16:00:00+00:00"
    assert relative_to_iso("Vừa xong", SCRAPED) == "2026-11-14T18:00:00+00:00"
    assert relative_to_iso("vài giây trước", SCRAPED) == "2026-11-14T18:00:00+00:00"
    assert relative_to_iso("không rõ", SCRAPED) is None
    assert relative_to_iso(None, SCRAPED) is None


def _prof(pid, cid):
    return f"https://www.facebook.com/someone?comment_id={_b64(f'comment:{pid}_{cid}')}"


def test_filter_to_post_by_owner_and_post_id():
    # Same post, different pfbid encoding than the crawled URL; ghost = user's own post.
    mine = [{"comment_href": f"https://www.facebook.com/tinhte/posts/pfbidOTHER?comment_id={i}",
             "profile_href": _prof(111, i)} for i in (1, 2)]
    ghost = [{"comment_href": f"https://www.facebook.com/me.9/posts/pfbidZ?comment_id={i}",
              "profile_href": _prof(777, i)} for i in (3, 4, 5)]  # more comments than target
    no_link = {"comment_href": None}
    kept = filter_to_post(ghost[:1] + mine + ghost[1:] + [no_link], POST + "?rdid=abc")
    assert kept == mine + [no_link]
    # Unknown owner (share URL): fall back to the dominant post id
    assert filter_to_post(mine + ghost, "https://fb.com/share/p/x") == ghost


def _c(author, text, href=None, profile=None, reply_to=None):
    return {"author": author, "text": text, "time": "1 giờ trước", "scraped_at": SCRAPED,
            "post_url": POST, "comment_href": href, "profile_href": profile,
            "reply_to_author": reply_to}


def test_rows_schema_threading_and_fallback():
    top = f"{POST}?comment_id={_b64('comment:111_222')}"
    comments = [
        _c("A", "gốc", top, "https://www.facebook.com/a.a?comment_id=x"),
        _c("B", "trả lời A", top + f"&reply_comment_id={_b64('comment:111_333')}"),
        # C answers B's reply: FB links only to top-level 222 -> resolve to B's 333
        _c("C", "trả lời B", top + f"&reply_comment_id={_b64('comment:111_444')}", reply_to="B"),
        _c("D", "không có link"),
    ]
    rows = to_common_rows(comments, "showbiz_141")
    assert all(list(r) == COMMON_FIELDS for r in rows)
    assert "labels" not in rows[0]
    assert [r["comment_id"] for r in rows[:3]] == ["222", "333", "444"]
    assert [r["reply_to_id"] for r in rows[:3]] == [None, "222", "333"]
    assert rows[0]["author_id"] == "a.a" and rows[1]["author_id"] is None
    assert all(r["platform"] == "facebook" and r["event_id"] == "showbiz_141" for r in rows)
    assert rows[3]["comment_id"].startswith("fbh_") and rows[3]["reply_to_id"] is None
    assert {r["post_id"] for r in rows} == {"111"}  # D inherits post id from siblings
    assert rows[0]["ts"] == "2026-11-14T17:00:00+00:00"
