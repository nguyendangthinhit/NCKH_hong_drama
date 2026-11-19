"""
Convert raw crawled FB comments into the project's shared multi-platform schema.

Shared schema (one JSON object per line, file `common.jsonl` in the post folder):
  comment_id   — FB comment id (numeric, from the comment permalink). Fallback when FB
                 gives no link: "fbh_<hash>" (stable hash of post_url|author|text[:80]).
  event_id     — event this post belongs to; passed in by the operator (--event-id).
  post_id      — numeric FB post id (decoded from comment_id), else id parsed from URL.
  platform     — always "facebook".
  author_id    — numeric profile id or username slug from the author's profile link.
  reply_to_id  — comment_id of the parent (null for top-level comments).
  ts           — ISO-8601 UTC. FB only shows RELATIVE time ("8 giờ trước"), so ts is
                 scraped_at minus that offset: approximate (coarser for weeks/years).
  text         — comment text.
`labels` is NOT produced here: labeling is a later step joined on comment_id.

CLI (re-convert an existing raw.json, e.g. after fixing event_id):
  python scripts/_common_schema.py <raw.json> --event-id <ID> [--out common.jsonl]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

PLATFORM = "facebook"
COMMON_FIELDS = ["comment_id", "event_id", "post_id", "platform",
                 "author_id", "reply_to_id", "ts", "text"]

# ---------------------------------------------------------------------------
# IDs from FB links
# ---------------------------------------------------------------------------
_DECODED_RE = re.compile(r"^comment:(\d+)_(\d+)$")


def _decode_fb_comment_param(value: str) -> tuple[str | None, str | None]:
    """FB comment params are either a bare number or base64("comment:<post>_<cid>").

    Returns (post_id, comment_id); either may be None.
    """
    value = unquote(value or "").strip()
    if not value:
        return None, None
    if value.isdigit():
        return None, value
    m = _DECODED_RE.match(value)  # already decoded form
    if not m:
        try:
            raw = base64.b64decode(value + "=" * (-len(value) % 4)).decode("ascii")
            m = _DECODED_RE.match(raw)
        except Exception:
            m = None
    return (m.group(1), m.group(2)) if m else (None, None)


def parse_comment_link(href: str | None) -> dict:
    """Read ids from a comment permalink (...?comment_id=X[&reply_comment_id=Y]).

    Returns {comment_id, parent_id, post_id}. For a reply, parent_id is the
    TOP-LEVEL comment FB puts in `comment_id` (nested parents resolved later).
    """
    out = {"comment_id": None, "parent_id": None, "post_id": None}
    if not href:
        return out
    qs = parse_qs(urlparse(href).query)
    post_a, top_cid = _decode_fb_comment_param((qs.get("comment_id") or [""])[0])
    post_b, reply_cid = _decode_fb_comment_param((qs.get("reply_comment_id") or [""])[0])
    out["post_id"] = post_b or post_a
    if reply_cid:
        out["comment_id"], out["parent_id"] = reply_cid, top_cid
    else:
        out["comment_id"] = top_cid
    return out


_NON_PROFILE = {"photo", "photo.php", "watch", "groups", "hashtag", "share", "story.php",
                "permalink.php", "posts", "reel", "events", "pages", "login", "help"}


def parse_author_id(href: str | None) -> str | None:
    """Numeric id (profile.php?id=, /people/<name>/<id>, /user/<id>) or username slug."""
    if not href:
        return None
    u = urlparse(href)
    if "facebook.com" not in (u.netloc or "facebook.com"):
        return None
    qs = parse_qs(u.query)
    if u.path.rstrip("/").endswith("profile.php"):
        return (qs.get("id") or [None])[0]
    parts = [p for p in u.path.split("/") if p]
    if not parts:
        return None
    if parts[0] == "people" and len(parts) >= 3:
        return parts[2]
    if "user" in parts:  # /groups/<g>/user/<id>/
        i = parts.index("user")
        return parts[i + 1] if i + 1 < len(parts) else None
    return None if parts[0].lower() in _NON_PROFILE else parts[0]


def parse_post_id_from_url(url: str | None) -> str | None:
    """Fallback post id from the post URL (story_fbid, /posts/<id>, /permalink/<id>, pfbid)."""
    if not url:
        return None
    u = urlparse(url)
    qs = parse_qs(u.query)
    for key in ("story_fbid", "fbid"):
        if qs.get(key):
            return qs[key][0]
    m = re.search(r"/(?:posts|permalink|videos|reel)/([\w]+)", u.path)
    return m.group(1) if m else None


def comment_post_id(c: dict) -> str | None:
    """Numeric post id of a raw comment: the timestamp link usually has a bare
    numeric comment_id, while the profile link carries base64("comment:<post>_<cid>")."""
    return (parse_comment_link(c.get("comment_href"))["post_id"]
            or parse_comment_link(c.get("profile_href"))["post_id"])


def _owner(url: str | None) -> str | None:
    """Page/group that owns a post URL: 'danangtv.vn', 'groups/<id>', ..."""
    parts = [p for p in urlparse(url or "").path.split("/") if p]
    if not parts or parts[0] in ("share", "permalink.php", "story.php"):
        return None
    return "/".join(parts[:2]) if parts[0] == "groups" and len(parts) > 1 else parts[0]


def filter_to_post(comments: list[dict], post_url: str | None) -> list[dict]:
    """Keep only comments of the crawled post (the page also shows feed/other posts).

    The same post appears under different pfbid encodings, so the URL path cannot
    be compared directly. Instead: among comments whose timestamp link belongs to
    the same page/group as post_url, take the most frequent numeric post id; if no
    owner matches, take the most frequent post id overall. Comments without any
    post id are kept.
    """
    pids = [comment_post_id(c) for c in comments]
    target = _owner(post_url)
    same_owner = [p for c, p in zip(comments, pids)
                  if p and target and _owner(c.get("comment_href")) == target]
    counts = Counter(same_owner) or Counter(p for p in pids if p)
    if not counts:
        return comments
    main = counts.most_common(1)[0][0]
    return [c for c, p in zip(comments, pids) if p is None or p == main]


# ---------------------------------------------------------------------------
# Relative time -> approximate ISO timestamp
# ---------------------------------------------------------------------------
_UNIT_SECONDS = {
    "giây": 1, "second": 1, "sec": 1, "s": 1,
    "phút": 60, "minute": 60, "min": 60, "m": 60,
    "giờ": 3600, "hour": 3600, "hr": 3600, "h": 3600,
    "ngày": 86400, "day": 86400, "d": 86400,
    "tuần": 604800, "week": 604800, "w": 604800,
    "tháng": 2592000, "month": 2592000, "mo": 2592000,
    "năm": 31536000, "year": 31536000, "y": 31536000,
}
_REL_RE = re.compile(
    r"(\d+|a|an|một)\s*(giây|phút|giờ|ngày|tuần|tháng|năm|seconds?|minutes?|hours?|days?|"
    r"weeks?|months?|years?|mins?|hrs?|mo|s|m|h|d|w|y)\b", re.IGNORECASE)


def relative_to_iso(time_str: str | None, scraped_at: str | None) -> str | None:
    """'8 giờ trước' / 'khoảng 1 giờ trước' / '3 weeks ago' / 'Hôm qua' -> ISO UTC."""
    if not time_str or not scraped_at:
        return None
    try:
        base = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    t = time_str.strip().lower()
    if re.search(r"vừa xong|vài giây|just now|few seconds", t):
        delta = 0
    elif re.search(r"hôm qua|yesterday", t):
        delta = 86400
    else:
        m = _REL_RE.search(t)
        if not m:
            return None
        n = 1 if m.group(1).lower() in ("a", "an", "một") else int(m.group(1))
        unit = m.group(2).lower()
        unit = unit if unit in _UNIT_SECONDS else unit.rstrip("s")
        if unit not in _UNIT_SECONDS:
            return None
        delta = n * _UNIT_SECONDS[unit]
    return (base - timedelta(seconds=delta)).astimezone(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Raw comments -> common rows
# ---------------------------------------------------------------------------
def _fallback_id(c: dict) -> str:
    key = f"{c.get('post_url', '')}|{c.get('author', '')}|{(c.get('text') or '')[:80]}"
    return "fbh_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def to_common_rows(comments: list[dict], event_id: str | None,
                   post_url: str | None = None) -> list[dict]:
    """Map raw comments (discovery order) to shared-schema rows.

    Nested replies ("X đáp lại phản hồi của Y"): FB links only to the top-level
    comment, so the parent is the latest earlier reply by Y in the same thread;
    falls back to the top-level comment when Y is not found.
    """
    rows, thread_last_by_author = [], {}  # (top_cid, author) -> latest comment_id
    for c in comments:
        ids = parse_comment_link(c.get("comment_href"))
        cid = ids["comment_id"] or _fallback_id(c)
        parent = ids["parent_id"]
        if parent and c.get("reply_to_author"):
            parent = thread_last_by_author.get((parent, c["reply_to_author"]), parent)
        top = ids["parent_id"] or ids["comment_id"]
        if top:
            thread_last_by_author[(top, c.get("author"))] = cid
        rows.append({
            "comment_id": cid,
            "event_id": event_id,
            "post_id": comment_post_id(c) or parse_post_id_from_url(c.get("post_url") or post_url),
            "platform": PLATFORM,
            "author_id": parse_author_id(c.get("profile_href")),
            "reply_to_id": parent,
            "ts": relative_to_iso(c.get("time"), c.get("scraped_at")),
            "text": c.get("text"),
        })
    # Comments without a permalink fall back to the post id seen on sibling rows.
    known = next((r["post_id"] for r in rows if r["post_id"] and r["post_id"].isdigit()), None)
    for r in rows:
        if known and not (r["post_id"] or "").isdigit():
            r["post_id"] = known
    return rows


def write_common_jsonl(rows: list[dict], out_path: Path) -> Path:
    out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                        encoding="utf-8")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="raw.json -> common.jsonl (shared schema)")
    ap.add_argument("raw", type=Path)
    ap.add_argument("--event-id", default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    comments = json.loads(a.raw.read_text(encoding="utf-8"))
    rows = to_common_rows(comments, a.event_id)
    out = write_common_jsonl(rows, a.out or a.raw.with_name("common.jsonl"))
    real = sum(1 for r in rows if not r["comment_id"].startswith("fbh_"))
    print(f"✓ {len(rows)} rows -> {out} (FB comment_id: {real}, fallback hash: {len(rows) - real})")


if __name__ == "__main__":
    main()
