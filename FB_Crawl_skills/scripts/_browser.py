"""
Browser detection + cookie parsing/injection for FB scraping.

Supports:
  - Auto-detect installed browsers (chromium, chrome, brave, edge, opera, firefox)
  - Opera is Chromium-based (Blink) → uses the same CDP launch flags as chromium
  - Parse cookies from Netscape format (curl/wget export) + JSON (browser extension export)
  - Parse raw cookie string ("c_user=123; xs=abc")
  - Inject cookies via CDP (Network.setCookie)

Usage:
    from _browser import (
        detect_browsers, BrowserConfig,
        parse_cookie_file, parse_cookie_string,
        inject_cookies, get_default_user_data_dir,
    )

    # Detect installed browsers
    browsers = detect_browsers()
    for b in browsers:
        print(f"{b['name']}: {b['path']} (v{b['version']})")

    # Parse cookies
    cookies = parse_cookie_file("/tmp/fb_cookies.txt")
    # or
    cookies = parse_cookie_string("c_user=123; xs=abc", domain=".facebook.com")

    # Inject via CDP
    await inject_cookies(ws, cookies, domain=".facebook.com")
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# Browser detection
# ============================================================

# Candidate paths for each browser (in priority order)
BROWSER_PATHS = {
    "chromium": [
        "/snap/bin/chromium",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/local/bin/chromium",
    ],
    "google-chrome": [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/opt/google/chrome/chrome",
    ],
    "brave": [
        "/usr/bin/brave-browser",
        "/usr/bin/brave-browser-stable",
        "/opt/brave.com/brave/brave",
        "/snap/bin/brave",
    ],
    "microsoft-edge": [
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/opt/microsoft/msedge/msedge",
    ],
    "opera": [
        "/usr/bin/opera",
        "/usr/bin/opera-stable",
        "/usr/bin/opera-beta",
        "/opt/opera/opera",
        "/snap/bin/opera",
    ],
    "firefox": [
        "/usr/bin/firefox",
        "/usr/bin/firefox-esr",
        "/snap/bin/firefox",
    ],
}

# Default user-data-dir per browser (used when launching)
DEFAULT_USER_DATA_DIRS = {
    "chromium": "~/.config/chromium",
    "google-chrome": "~/.config/google-chrome",
    "brave": "~/.config/BraveSoftware/Brave-Browser",
    "microsoft-edge": "~/.config/microsoft-edge",
    "opera": "~/.config/opera",
    "firefox": "~/.mozilla/firefox",  # Firefox uses profile dir, not user-data-dir
}


def _get_version(exe_path: str) -> str:
    """Get browser version. Returns 'unknown' if not available."""
    try:
        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        # Output: "Chromium 149.0.7827.200" or similar
        match = re.search(r"(\d+\.\d+\.\d+\.?\d*)", result.stdout + result.stderr)
        return match.group(1) if match else "unknown"
    except Exception:
        return "unknown"


def detect_browsers() -> list[dict]:
    """Detect installed browsers in priority order.

    Returns:
        list of {name, path, version, user_data_dir}
        Sorted by BROWSER_PATHS dict order (chromium first).
    """
    found = []
    for name, paths in BROWSER_PATHS.items():
        for path in paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                version = _get_version(path)
                user_data_dir = DEFAULT_USER_DATA_DIRS.get(name, "")
                found.append({
                    "name": name,
                    "path": path,
                    "version": version,
                    "user_data_dir": user_data_dir,
                })
                break  # Use first match for this browser
    return found


def get_default_user_data_dir(browser_name: str) -> str:
    """Get default user-data-dir for a browser, expanding ~."""
    raw = DEFAULT_USER_DATA_DIRS.get(browser_name, "")
    return os.path.expanduser(raw)


@dataclass
class BrowserConfig:
    """Configuration for launching a browser."""
    name: str = "auto"  # auto | chromium | google-chrome | brave | microsoft-edge | opera | firefox
    path: str = ""      # Override executable path (empty = auto-detect)
    user_data_dir: str = ""  # Empty = browser default
    profile: str = "Default"  # Chrome profile (Default, Profile 1, etc.)
    port: int = 9222
    headless: bool = False
    extra_args: list[str] = field(default_factory=list)

    def resolve(self) -> dict:
        """Resolve to actual executable path + user-data-dir.

        Returns dict with: name, path, user_data_dir, profile, port, args
        """
        # Resolve browser executable
        if self.name == "auto":
            browsers = detect_browsers()
            if not browsers:
                raise RuntimeError("No browser detected. Install chromium/chrome/brave/edge/firefox.")
            chosen = browsers[0]
        else:
            # Try self.path first, then BROWSER_PATHS for self.name
            if self.path and os.path.isfile(self.path):
                chosen = {"name": self.name, "path": self.path, "version": _get_version(self.path)}
            else:
                candidates = BROWSER_PATHS.get(self.name, [])
                chosen = None
                for p in candidates:
                    if os.path.isfile(p) and os.access(p, os.X_OK):
                        chosen = {"name": self.name, "path": p, "version": _get_version(p)}
                        break
                if not chosen:
                    raise RuntimeError(f"Browser '{self.name}' not found. Searched: {candidates}")

        # Resolve user-data-dir
        if self.user_data_dir:
            user_data_dir = os.path.expanduser(self.user_data_dir)
        else:
            user_data_dir = get_default_user_data_dir(chosen["name"])
            if not os.path.exists(user_data_dir):
                user_data_dir = ""  # Let browser use its own default

        # Build args
        args = []
        if chosen["name"] != "firefox":
            # Chromium-based browsers
            if user_data_dir:
                args.append(f"--user-data-dir={user_data_dir}")
            args.extend([
                f"--remote-debugging-port={self.port}",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                # Keep the tab "visible" even when another window covers it: a hidden tab
                # (visibilityState=hidden) makes FB stop lazy-loading comments (14 vs ~50).
                "--disable-features=CalculateNativeWinOcclusion",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                # NOTE: Opera rejects --disable-blink-features (unsupported flag,
                # shows a stability/security warning banner). It only matters on
                # chromium/chrome/brave/edge where it clears navigator.webdriver;
                # for Opera the stealth init script already overrides that, so
                # dropping it is harmless.
                "--disable-blink-features=AutomationControlled" if chosen["name"] != "opera" else "",
                "--lang=vi-VN",
            ])
            # Drop any empty arg produced above
            args = [a for a in args if a]
            if self.headless:
                args.append("--headless=new")
        else:
            # Firefox: needs Marionette for CDP
            args.extend([
                "--marionette",
                f"--remote-debugging-port={self.port}",
            ])
            if user_data_dir:
                args.append(f"-profile")
                args.append(user_data_dir)
            if self.headless:
                args.append("--headless")

        args.extend(self.extra_args)

        return {
            "name": chosen["name"],
            "path": chosen["path"],
            "version": chosen.get("version", "unknown"),
            "user_data_dir": user_data_dir,
            "profile": self.profile,
            "port": self.port,
            "args": args,
        }


# ============================================================
# Cookie parsing
# ============================================================

# Netscape cookie file format:
#   domain  flag  path  secure  expiration  name  value
# Tab-separated. Lines starting with # are comments.
NETSCAPE_LINE_RE = re.compile(
    r"^(?P<domain>[^\s]+)\s+"
    r"(?P<flag>TRUE|FALSE)\s+"
    r"(?P<path>[^\s]+)\s+"
    r"(?P<secure>TRUE|FALSE)\s+"
    r"(?P<expiration>\d+)\s+"
    r"(?P<name>[^\s]+)\s+"
    r"(?P<value>.+)$"
)


def parse_cookie_file(path: str) -> list[dict]:
    """Parse cookie file in Netscape or JSON format.

    Returns list of dicts: {name, value, domain, path, secure, expiration}
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Cookie file not found: {path}")

    text = p.read_text(encoding="utf-8", errors="ignore").strip()

    # Try JSON first
    if text.startswith("["):
        return _parse_cookie_json(text)
    if text.startswith("{"):
        # Could be {cookies: [...]} or single cookie
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return _parse_cookie_json(text)
            elif isinstance(data, dict) and "cookies" in data:
                return _parse_cookie_json(json.dumps(data["cookies"]))
            else:
                # Single cookie
                return [_normalize_cookie_json(data)]
        except json.JSONDecodeError:
            pass

    # Fall back to Netscape
    return _parse_cookie_netscape(text)


def _parse_cookie_json(text: str) -> list[dict]:
    """Parse JSON array of cookies (browser extension format)."""
    raw = json.loads(text)
    if not isinstance(raw, list):
        raise ValueError("JSON must be an array of cookies")
    return [_normalize_cookie_json(c) for c in raw]


def _normalize_cookie_json(c: dict) -> dict:
    """Normalize a single cookie from JSON to our schema."""
    return {
        "name": c.get("name", ""),
        "value": c.get("value", ""),
        "domain": c.get("domain", ".facebook.com"),
        "path": c.get("path", "/"),
        "secure": c.get("secure", False),
        "expiration": c.get("expirationDate") or c.get("expires") or c.get("expiry") or 0,
        "httpOnly": c.get("httpOnly", False),
    }


def _parse_cookie_netscape(text: str) -> list[dict]:
    """Parse Netscape cookie file format."""
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Handle HttpOnly prefix (e.g. "#HttpOnly_facebook.com")
        http_only = False
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_"):]

        m = NETSCAPE_LINE_RE.match(line)
        if not m:
            continue

        # Convert expiration to seconds-since-epoch
        try:
            exp = int(m.group("expiration"))
        except ValueError:
            exp = 0

        cookies.append({
            "name": m.group("name"),
            "value": m.group("value"),
            "domain": m.group("domain"),
            "path": m.group("path"),
            "secure": m.group("secure") == "TRUE",
            "expiration": exp,
            "httpOnly": http_only,
        })
    return cookies


def parse_cookie_string(cookie_str: str, domain: str = ".facebook.com") -> list[dict]:
    """Parse raw cookie string like 'c_user=123; xs=abc; fr=xyz'.

    Returns list of dicts in standard schema.
    """
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
            "secure": True,
            "expiration": 0,  # Session cookie
            "httpOnly": False,
        })
    return cookies


# ============================================================
# Cookie injection via CDP
# ============================================================

async def inject_cookies(ws, cookies: list[dict], default_domain: str = ".facebook.com") -> int:
    """Inject cookies via Chrome DevTools Protocol (Network.setCookie).

    Args:
        ws: websocket connection to browser
        cookies: list of {name, value, domain, path, secure, expiration, httpOnly}
        default_domain: domain to use if cookie doesn't specify one

    Returns:
        number of cookies injected successfully
    """
    if not cookies:
        return 0

    msg_id = [0]
    async def cdp_send(method, params=None):
        msg_id[0] += 1
        await ws.send(json.dumps({"id": msg_id[0], "method": method, "params": params or {}}))
        while True:
            resp = json.loads(await ws.recv())
            if resp.get("id") == msg_id[0]:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    # Enable Network domain (required for setCookie)
    await cdp_send("Network.enable")

    success = 0
    for c in cookies:
        params = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain") or default_domain,
            "path": c.get("path", "/"),
        }
        # Only set secure/httpOnly/expiration if explicitly provided
        if c.get("secure"):
            params["secure"] = True
        if c.get("httpOnly"):
            params["httpOnly"] = True
        if c.get("expiration") and c.get("expiration") > 0:
            # CDP expects seconds since epoch
            params["expires"] = c["expiration"]
        try:
            await cdp_send("Network.setCookie", params)
            success += 1
        except Exception as e:
            print(f"⚠ Failed to set cookie {c.get('name')}: {e}")

    return success


# ============================================================
# CLI for testing
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BROWSER DETECTION TEST")
    print("=" * 60)
    browsers = detect_browsers()
    if not browsers:
        print("❌ No browsers detected")
        sys.exit(1)
    for b in browsers:
        print(f"  ✓ {b['name']:20s} {b['path']:50s} v{b['version']}")
        print(f"      user-data-dir: {b['user_data_dir'] or '(default)'}")

    print()
    print("=" * 60)
    print("DEFAULT USER DATA DIRS")
    print("=" * 60)
    for name in BROWSER_PATHS:
        d = get_default_user_data_dir(name)
        exists = "✓" if os.path.exists(d) else "✗"
        print(f"  {exists} {name:20s} {d}")

    # Test cookie parsing if file provided
    if len(sys.argv) > 1:
        cookie_file = sys.argv[1]
        print()
        print("=" * 60)
        print(f"COOKIE PARSE TEST: {cookie_file}")
        print("=" * 60)
        try:
            cookies = parse_cookie_file(cookie_file)
            print(f"  Found {len(cookies)} cookies:")
            for c in cookies[:5]:
                v = c["value"][:20] + "..." if len(c["value"]) > 20 else c["value"]
                print(f"    {c['name']:15s} = {v:30s} (domain: {c['domain']})")
            if len(cookies) > 5:
                print(f"    ... and {len(cookies) - 5} more")
        except Exception as e:
            print(f"  ❌ {e}")