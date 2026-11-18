"""Best-effort NO-AUTH public post-text fetch for Facebook.

Facebook returns a PARTIAL comment set to a logged-out session (empirically
verified 2026-07-12: 6 of 10 comments came back behind the login wall on a public
post). So this module is now only a LAST-RESORT fallback for when even the
partial logged-out render yields zero comments. It salvages the public post BODY
via FB's lightweight JSON endpoint (`?__a=1`). This is UNOFFICIAL and may break at
any time — treat as graceful degradation, never a guarantee.

Usage:
    from _lightweight import fetch_public_post_text, post_id_from_url

    pid = post_id_from_url("https://www.facebook.com/share/p/1AxneTWsfv/")
    text = fetch_public_post_text(pid)   # may raise LightweightUnavailable
"""
from __future__ import annotations
import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


class LightweightUnavailable(Exception):
    """Raised when FB withholds the post (auth wall, 400, structure change)."""


# Desktop UA so FB returns the JSON payload rather than a mobile redirect.
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def post_id_from_url(url: str) -> str:
    """Extract a Facebook post/entity id from a URL.

    Handles:
      - https://www.facebook.com/share/p/<ID>/
      - https://www.facebook.com/<page>/posts/<ID>
      - https://www.facebook.com/permalink.php?story_fbid=<ID>
      - https://www.facebook.com/groups/<g>/permalink/<ID>
    Raises ValueError if no id can be found.
    """
    # share/p/<ID> is the most common crawl target
    m = re.search(r"/share/p/([A-Za-z0-9._\-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/posts/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"story_fbid=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/permalink/(\d+)", url)
    if m:
        return m.group(1)
    # Bare numeric id
    m = re.search(r"/(\d{10,})", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract post id from URL: {url}")


def _is_real_post_text(t: str) -> bool:
    """Reject FB error/wall/dead-end strings that are not post content."""
    low = t.lower()
    markers = (
        "không thể xử lý", "can't process", "something went wrong",
        "login_popup_cta_form", "đăng nhập", "log in", "sign up",
        "xem thêm trên facebook", "see more on facebook",
    )
    return not any(m in low for m in markers) and len(t) >= 8


def _walk_for_text(node) -> Optional[str]:
    """Recursively pull the first meaningful text from a parsed JS mod payload."""
    if isinstance(node, str):
        s = node.strip()
        # Skip tiny tokens / keys; FB text nodes are usually longer sentences.
        if len(s) >= 8:
            return s
        return None
    if isinstance(node, dict):
        # Common text-bearing keys in FB's __a=1 payload.
        for key in ("text", "message", "__txt", "name", "title"):
            if key in node and isinstance(node[key], str):
                t = node[key].strip()
                if len(t) >= 8:
                    return t
        for v in node.values():
            found = _walk_for_text(v)
            if found:
                return found
    if isinstance(node, list):
        for item in node:
            found = _walk_for_text(item)
            if found:
                return found
    return None


def fetch_public_post_text(post_id: str, timeout: float = 15.0) -> str:
    """Fetch public post body text without authentication.

    Args:
        post_id: FB entity id (from post_id_from_url).
        timeout: HTTP timeout in seconds.

    Returns:
        Post body text (may be partial).

    Raises:
        LightweightUnavailable: FB withheld the post (auth wall / 400 / changed).
    """
    url = f"https://www.facebook.com/{post_id}?__a=1&__d=dis"
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json, text/javascript, */*",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        raise LightweightUnavailable(f"HTTP {e.code} for post {post_id}") from e
    except Exception as e:
        raise LightweightUnavailable(str(e)) from e

    if not raw.strip():
        raise LightweightUnavailable("empty response")

    # FB prefixes the payload with "for (;;);" — strip it.
    if raw.startswith("for (;;);"):
        raw = raw[len("for (;;);"):]

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Some responses are JS-mod arrays, not strict JSON. Try to find text
        # without full parse — give up gracefully if it looks like a wall.
        if "login_popup_cta_form" in raw or "Đăng nhập" in raw:
            raise LightweightUnavailable("auth wall in payload")
        raise LightweightUnavailable("non-JSON payload")

    # Common shapes: {"jsmods": {...}} or a top-level dict with text.
    text = _walk_for_text(payload)
    if not text or not _is_real_post_text(text):
        raise LightweightUnavailable("no post text node found (auth wall or structure changed?)")
    return text


@dataclass
class LightweightResult:
    post_id: str
    text: Optional[str]
    available: bool
    note: str = ""


def try_public_post(url: str) -> LightweightResult:
    """Convenience: try the no-auth fetch for a URL. Never raises."""
    try:
        pid = post_id_from_url(url)
    except ValueError as e:
        return LightweightResult("", None, False, str(e))
    try:
        text = fetch_public_post_text(pid)
        return LightweightResult(pid, text, True, "")
    except LightweightUnavailable as e:
        return LightweightResult(pid, None, False, str(e))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        res = try_public_post(sys.argv[1])
        print(f"post_id   : {res.post_id}")
        print(f"available : {res.available}")
        if res.text:
            print(f"text      : {res.text[:200]}")
        else:
            print(f"note      : {res.note}")
    else:
        print("Usage: python3 _lightweight.py <FB_POST_URL>")
