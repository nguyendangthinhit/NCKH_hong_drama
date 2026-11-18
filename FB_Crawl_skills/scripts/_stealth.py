"""
SeleniumBase-inspired stealth helpers for Facebook scraping.

Patterns adapted from SeleniumBase's `seleniumbase/undetected/` module:
- `seleniumbase/undetected/patcher.py` — chromedriver binary patching (cdc_ fingerprint removal)
- `seleniumbase/undetected/dprocess.py` — detached subprocess launching
- `seleniumbase/undetected/options.py` — anti-detection ChromeOptions

SeleniumBase is MIT licensed. Credit: https://github.com/seleniumbase/SeleniumBase
This is an ADAPTATION, not a copy. Original library not required.

Usage:
    from scripts._stealth import (
        patch_chromedriver_binary,
        build_stealth_init_script,
        start_chromium_detached,
        apply_stealth_via_cdp,
    )
"""
import atexit
import io
import json
import os
import random
import re
import shutil
import signal
import string
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Chromedriver binary patching (from SeleniumBase patcher.py:121-247)
# ---------------------------------------------------------------------------

# Regex patterns copied from SeleniumBase's Patcher.patch_exe()
_CDC_VAR_REGEX = re.compile(
    rb"window\.cdc_[a-zA-Z0-9]{22}_"
    rb"(Array|Promise|Symbol|Object|Proxy|JSON|Window) "
    rb"= window\.(Array|Promise|Symbol|Object|Proxy|JSON|Window);"
)
_CDC_PIPE_REGEX = re.compile(
    rb"window\.cdc_[a-zA-Z0-9]{22}_"
    rb"(Array|Promise|Symbol|Object|Proxy|JSON|Window) \|\|"
)
_CDC_CACHE_REGEX = re.compile(rb"'\$cdc_[a-zA-Z0-9]{22}_';")

# Sentinel strings for detection (must NOT appear in patched binary)
_CDC_FINGERPRINT = b"cdc_adoQpoasnfa76pfcZLmcfl_"


def is_binary_patched(executable_path: str) -> bool:
    """Check if a chromedriver binary still contains the cdc_ fingerprint.

    Returns True if patched (no fingerprint found), False if unpatched.
    Mirrors SeleniumBase's `Patcher.is_binary_patched()` (patcher.py:201-210).
    """
    with io.open(executable_path, "rb") as fh:
        if re.search(
            b"window.cdc_adoQpoasnfa76pfcZLmcfl_"
            b"(Array|Promise|Symbol|Object|Proxy|JSON|Window)",
            fh.read(),
        ):
            return False
    return True


def _gen_random_cdc() -> bytes:
    """Generate random replacement string (from SeleniumBase Patcher.gen_random_cdc)."""
    cdc = random.choices(string.ascii_lowercase, k=26)
    cdc[-6:-4] = map(str.upper, cdc[-6:-4])
    cdc[2] = cdc[0]
    cdc[3] = "_"
    return "".join(cdc).encode()


def _gen_call_function_js_cache_name(match: re.Match) -> bytes:
    """Replacement for cdc cache name (from SeleniumBase patcher.py:217-223)."""
    rep_len = len(match.group()) - 3
    ran_len = random.randint(6, rep_len)
    bb = b"'" + bytes(
        "".join(random.choices(population=string.ascii_letters, k=ran_len)),
        "ascii",
    ) + b"';" + (b"\n" * (rep_len - ran_len))
    return bb


def patch_chromedriver_binary(executable_path: str) -> bool:
    """Patch a chromedriver executable to remove the cdc_ fingerprint.

    Mirrors SeleniumBase's `Patcher.patch_exe()` (patcher.py:212-247).

    WARNING: This is DESTRUCTIVE. Always backup the binary first.

    Returns True on success, False if already patched or error.
    """
    if not os.path.exists(executable_path):
        raise FileNotFoundError(f"Chromedriver not found: {executable_path}")

    if is_binary_patched(executable_path):
        return False  # Already patched

    with io.open(executable_path, "r+b") as fh:
        file_bin = fh.read()
        file_bin = _CDC_VAR_REGEX.sub(lambda m: b"\n" * len(m.group()), file_bin)
        file_bin = _CDC_PIPE_REGEX.sub(lambda m: b"\n" * len(m.group()), file_bin)
        file_bin = _CDC_CACHE_REGEX.sub(_gen_call_function_js_cache_name, file_bin)
        fh.seek(0)
        fh.write(file_bin)

    return is_binary_patched(executable_path)


# ---------------------------------------------------------------------------
# 2. Stealth init script (JavaScript injected before page loads)
# ---------------------------------------------------------------------------


def build_stealth_init_script(locale: str = "vi-VN") -> str:
    """Build a JavaScript init script that neutralizes common bot-detection vectors.

    Inspired by SeleniumBase's approach (simpler than playwright-stealth).
    Inject via CDP's `Page.addScriptToEvaluateOnNewDocument` after browser launch.

    Args:
        locale: 2-letter or BCP-47 locale code for navigator.language override.

    Returns:
        JavaScript source as string. Run once per page load.
    """
    lang_chain = {
        "vi-VN": "['vi-VN', 'vi', 'en-US', 'en']",
        "en-US": "['en-US', 'en']",
    }.get(locale, "['vi-VN', 'vi', 'en-US', 'en']")

    return f"""(() => {{
    // 1. Remove webdriver flag (SeleniumBase Counter 2)
    Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});

    // 2. Fake plugins array (some sites check this)
    Object.defineProperty(navigator, 'plugins', {{
        get: () => [1, 2, 3, 4, 5],
    }});

    // 3. Languages stack
    Object.defineProperty(navigator, 'languages', {{ get: () => {lang_chain} }});

    // 4. Realistic hardware concurrency (4-16 cores)
    Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => 8 }});

    // 5. Device memory (4-16 GB)
    Object.defineProperty(navigator, 'deviceMemory', {{ get: () => 8 }});

    // 6. Remove cdc_ variable if exposed
    if (typeof window !== 'undefined') {{
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_;
    }}

    // 7. Chrome runtime stub (so `window.chrome.runtime` is truthy)
    if (typeof window.chrome === 'undefined') {{
        window.chrome = {{ runtime: {{}}, loadTimes: function() {{}}, csi: function() {{}} }};
    }}
}})();
"""


# ---------------------------------------------------------------------------
# 3. Detached subprocess launcher (from SeleniumBase dprocess.py:39-53)
# ---------------------------------------------------------------------------

# Track spawned PIDs for cleanup (like SeleniumBase's REGISTERED list)
_SPAWNED_PIDS: list[int] = []


def _cleanup_spawned():
    """SIGTERM all spawned chromium processes on script exit (atexit hook)."""
    for pid in _SPAWNED_PIDS:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


atexit.register(_cleanup_spawned)


def start_chromium_detached(
    user_data_dir: str,
    extra_args: Optional[list[str]] = None,
    port: int = 9222,
    chromium_path: Optional[str] = None,
    wait_ready: bool = True,
    timeout: float = 30.0,
) -> dict:
    """Launch Chromium as a fully detached subprocess with CDP enabled.

    Mirrors SeleniumBase's `start_detached()` (dprocess.py:15-36) using
    `start_new_session=True` (POSIX) so chromedriver can't be detected
    via parent process inspection.

    Args:
        user_data_dir: path to Chromium profile directory
        extra_args: additional chromium flags (e.g. ['--window-size=1366,768'])
        port: CDP remote debugging port
        chromium_path: path to chromium binary (auto-detected if None)
        wait_ready: poll CDP /json/version until ready (default True)
        timeout: max seconds to wait for browser ready

    Returns:
        dict with keys: pid, port, ws_url (CDP browser WebSocket), browser (path)
    """
    # Find chromium binary
    if chromium_path is None:
        chromium_path = shutil.which("chromium") or "/snap/bin/chromium"
    if not os.path.exists(chromium_path):
        raise FileNotFoundError(f"Chromium not found at {chromium_path}")

    os.makedirs(user_data_dir, exist_ok=True)

    # Build args
    args = [
        chromium_path,
        f"--user-data-dir={user_data_dir}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-sandbox",  # needed for snap on Ubuntu
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process,InterestFeedContentSuggestion",
        "--lang=vi-VN",
        "--window-size=1366,768",
    ]
    if extra_args:
        args.extend(extra_args)

    # Detached subprocess (start_new_session=True on POSIX, CREATE_NEW_PROCESS_GROUP on Windows)
    # This mirrors SeleniumBase's dprocess._start_detached() (dprocess.py:39-53)
    kwargs = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:  # Windows
        kwargs["creationflags"] = 0x00000200 | 0x00000008  # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS

    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    _SPAWNED_PIDS.append(proc.pid)

    result = {
        "pid": proc.pid,
        "port": port,
        "ws_url": None,
        "browser": chromium_path,
    }

    # Wait for CDP ready
    if wait_ready:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                    ver = json.loads(r.read())
                    result["ws_url"] = ver.get("webSocketDebuggerUrl")
                    return result
            except Exception:
                time.sleep(0.5)

    return result


# ---------------------------------------------------------------------------
# 4. Apply stealth to running browser via CDP (retroactive)
# ---------------------------------------------------------------------------


async def apply_stealth_via_cdp(ws_url: str, locale: str = "vi-VN") -> bool:
    """Inject stealth init script into all NEW documents in a running browser.

    Uses CDP's `Page.addScriptToEvaluateOnNewDocument` so the init runs before
    every page load. Works retroactively on browsers already running.

    Args:
        ws_url: WebSocket URL of a page target (e.g. from /json)
        locale: locale string for navigator.language override

    Returns:
        True if injection succeeded, False otherwise.
    """
    import websockets  # optional dep

    init_js = build_stealth_init_script(locale)
    msg_id = 0

    async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
        msg_id += 1
        await ws.send(json.dumps({
            "id": msg_id,
            "method": "Page.enable",
        }))
        await ws.recv()

        msg_id += 1
        await ws.send(json.dumps({
            "id": msg_id,
            "method": "Page.addScriptToEvaluateOnNewDocument",
            "params": {"source": init_js},
        }))
        resp = json.loads(await ws.recv())
        if "error" in resp:
            return False
        return True


def apply_stealth_to_all_tabs(ws_browser_url: str, locale: str = "vi-VN") -> dict:
    """Apply stealth to all open tabs via the browser-level WebSocket.

    Args:
        ws_browser_url: WebSocket URL of the browser target (from /json/version)
        locale: locale string

    Returns:
        dict {tab_url: success_bool}
    """
    import websockets
    import asyncio

    async def _apply():
        # Get all tabs
        with urllib.request.urlopen("http://127.0.0.1:9222/json") as r:
            tabs = json.loads(r.read())

        results = {}
        # Connect via browser-level WebSocket to inject on each target
        async with websockets.connect(ws_browser_url, max_size=10 * 1024 * 1024) as bws:
            init_js = build_stealth_init_script(locale)
            msg_id = 0
            for tab in tabs:
                if tab.get("type") != "page":
                    continue
                target_id = tab["id"]
                msg_id += 1
                await bws.send(json.dumps({
                    "id": msg_id,
                    "method": "Target.attachToTarget",
                    "params": {"targetId": target_id, "flatten": True},
                }))
                resp = json.loads(await bws.recv())
                session_id = resp.get("params", {}).get("sessionId")

                if not session_id:
                    results[tab.get("url", "?")] = False
                    continue

                # Enable Page domain in session
                msg_id += 1
                await bws.send(json.dumps({
                    "id": msg_id,
                    "method": "Page.enable",
                    "params": {},
                    "sessionId": session_id,
                }))
                await bws.recv()

                # Add init script
                msg_id += 1
                await bws.send(json.dumps({
                    "id": msg_id,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": init_js},
                    "sessionId": session_id,
                }))
                resp = json.loads(await bws.recv())
                results[tab.get("url", "?")] = "error" not in resp

        return results

    return asyncio.run(_apply())