#!/usr/bin/env python3
"""Persistent browser watchdog for FB CDP crawls.

Keeps a Chromium (or other Chromium-based) browser alive on the CDP port. If
the browser app crashes, gets OOM-killed, or otherwise disappears, the watchdog
relaunches it with the SAME flags and the SAME user-data-dir, so the session
(cookies / login) is preserved and a connected crawler can recover.

This is the "browser tự mở lại" (auto-reopen) half of crash recovery. The other
half lives in 05_auto_scrape_cdp.py main(), which detects BrowserDisconnected,
waits for CDP, and resumes from the click-loop checkpoint.

Design:
  - Polls http://127.0.0.1:<port>/json/version every --interval seconds.
  - If CDP is unreachable, relaunch via the same BrowserConfig the launcher uses.
  - Honors --max-restarts (guards against a browser that crashes instantly in a
    loop); once exceeded it exits non-zero.
  - Stops cleanly if --stop-file exists (touched by a stop command) or SIGINT.

Usage:
  # Persistent (started by 01_open_browser.sh when FB_WATCHDOG=1):
  python3 scripts/09_browser_watchdog.py --port 9222 --interval 5 --max-restarts 50

  # One-shot: relaunch if down, then exit:
  python3 scripts/09_browser_watchdog.py --once

Env vars (same as 01_open_browser.sh):
  FB_BROWSER, FB_TARGET_URL, FB_CDP_PORT, FB_USER_DATA_DIR, FB_PROFILE,
  FB_HEADLESS
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_DEFAULT_PORT = int(os.environ.get("FB_CDP_PORT", "9222"))


def cdp_alive(port: int) -> bool:
    """Return True if the CDP HTTP endpoint answers."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                    timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def build_launch_command(port: int) -> tuple[str, list[str], str]:
    """Resolve the browser launch command via _browser.BrowserConfig.

    Returns (browser_path, args_list, user_data_dir) so the caller can relaunch
    identically to 01_open_browser.sh.
    """
    import _browser  # local import; requires scripts/ on sys.path
    from _browser import BrowserConfig

    browser = os.environ.get("FB_BROWSER", "auto")
    target_url = os.environ.get("FB_TARGET_URL", "https://www.facebook.com/")
    user_data_dir = os.environ.get("FB_USER_DATA_DIR", "")
    profile = os.environ.get("FB_PROFILE", "Default")
    headless = os.environ.get("FB_HEADLESS", "0") == "1"

    config = BrowserConfig(
        name=browser,
        user_data_dir=user_data_dir,
        profile=profile,
        port=port,
        headless=headless,
    ).resolve()

    path = config["path"]
    args = list(config["args"])
    udd = config.get("user_data_dir", "")
    # Ensure the post/page URL is the final positional arg.
    return path, args + [target_url], udd


def launch(path: str, args: list[str], port: int, log_path: str) -> int:
    """Relaunch the browser in the background; return its PID."""
    with open(log_path, "ab") as logf:
        logf.write(
            f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] relaunch "
            f"{path} {args}\n".encode("utf-8", "replace")
        )
    # Popen needs a file object for stdout/stderr, not a path string.
    logf = open(log_path, "ab")
    proc = subprocess.Popen(
        [path, *args],
        stdout=logf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return proc.pid


def main() -> int:
    parser = argparse.ArgumentParser(description="FB CDP browser watchdog")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT,
                        help="CDP port to watch (default: FB_CDP_PORT or 9222)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds between liveness checks (default: 5)")
    parser.add_argument("--max-restarts", type=int, default=50,
                        help="Max relaunches before giving up (default: 50)")
    parser.add_argument("--once", action="store_true",
                        help="Relaunch once if down, then exit (no persistent loop)")
    parser.add_argument("--stop-file", type=str, default=None,
                        help="If this file exists, the watchdog exits cleanly")
    parser.add_argument("--target-url", type=str, default=None,
                        help="Override FB_TARGET_URL for relaunch navigation")
    args = parser.parse_args()

    if args.target_url:
        os.environ["FB_TARGET_URL"] = args.target_url

    port = args.port
    log_path = f"/tmp/fb-watchdog-{port}.log"
    stop_file = Path(args.stop_file) if args.stop_file else None

    # Graceful shutdown
    _running = {"go": True}

    def _sig(_signum, _frame):
        _running["go"] = False

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    print(f"[watchdog] port={port} interval={args.interval}s "
          f"max_restarts={args.max_restarts} once={args.once}", flush=True)

    restarts = 0
    # Prime CDP liveness so we don't immediately relaunch a healthy browser.
    first = True
    while _running["go"]:
        if stop_file and stop_file.exists():
            print("[watchdog] stop-file present — exiting cleanly", flush=True)
            return 0

        if cdp_alive(port):
            if first:
                print("[watchdog] browser already up — watching", flush=True)
            first = False
            if args.once:
                print("[watchdog] browser up (once mode) — exiting", flush=True)
                return 0
            time.sleep(args.interval)
            continue

        # Browser is down → relaunch.
        if restarts >= args.max_restarts:
            print(f"[watchdog] exceeded max_restarts={args.max_restarts} — "
                  f"giving up", file=sys.stderr, flush=True)
            return 1

        restarts += 1
        print(f"[watchdog] browser DOWN (crash/kill) — relaunch #{restarts}",
              flush=True)
        try:
            path, launch_args, udd = build_launch_command(port)
            pid = launch(path, launch_args, port, log_path)
            print(f"[watchdog] relaunched pid={pid} profile={udd or 'default'}",
                  flush=True)
        except Exception as e:
            print(f"[watchdog] relaunch failed: {e}", file=sys.stderr, flush=True)

        # Give it time to bind CDP before the next check.
        time.sleep(max(args.interval, 3.0))
        first = False
        if args.once:
            # In once mode, wait a bit to confirm, then exit regardless.
            time.sleep(3.0)
            return 0 if cdp_alive(port) else 1

    print("[watchdog] interrupted — exiting", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
