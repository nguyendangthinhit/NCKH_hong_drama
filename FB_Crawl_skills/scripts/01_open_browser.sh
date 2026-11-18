#!/usr/bin/env bash
# Mở browser (chromium/chrome/brave/edge/opera/firefox) với CDP + stealth flags.
# Login Facebook thủ công, hoặc inject cookies qua --cookie-file.
#
# Approach:
# - An toàn cho account (không có automation → không trigger bot detection)
# - Sau khi browser mở, dùng scripts/05_auto_scrape_cdp.py để extract data
#
# Env vars:
#   FB_BROWSER       = auto | chromium | google-chrome | brave | microsoft-edge | opera | firefox (default: auto)
#   FB_TARGET_URL    = URL mở ban đầu (default: https://www.facebook.com/login)
#   FB_CDP_PORT      = port cho Chrome DevTools Protocol (default: 9222)
#   FB_USER_DATA_DIR = override user data dir (default: browser-specific)
#   FB_PROFILE       = Chrome profile name (default: "Default")
#   FB_HEADLESS      = 1 để chạy headless (default: 0)
#   FB_COOKIE_FILE   = path to Netscape/JSON cookie file (optional, injected via CDP after launch)
#   FB_DISMISS_LOGIN_WALL = 1 to dismiss FB's logged-out login overlay during crawl (default: 0)
#
# Usage:
#   bash scripts/01_open_browser.sh                                    # Auto-detect browser, default settings
#   FB_BROWSER=firefox bash scripts/01_open_browser.sh                # Use Firefox
#   FB_BROWSER=google-chrome bash scripts/01_open_browser.sh          # Use Google Chrome
#   FB_USER_DATA_DIR=~/my-profile bash scripts/01_open_browser.sh     # Custom user data dir
#   FB_COOKIE_FILE=/tmp/fb_cookies.txt bash scripts/01_open_browser.sh # Auto-inject cookies
#
# Backward compat: 01_open_chromium.sh is now a thin wrapper around this script.
#
# Related:
#   scripts/_browser.py       — browser detection + cookie parsing
#   scripts/_stealth.py       — SeleniumBase-inspired stealth helpers
#   skills/facebook-anti-bot/ — methodology documentation

set -e

# Defaults
TARGET_URL="${FB_TARGET_URL:-https://www.facebook.com/login}"
CDP_PORT="${FB_CDP_PORT:-9222}"
BROWSER="${FB_BROWSER:-auto}"
HEADLESS="${FB_HEADLESS:-0}"
PROFILE="${FB_PROFILE:-Default}"

# Snap chromium AppArmor: needs special user data dir
SNAP_USERDATA_DIR="${HOME}/snap/chromium/common/chromium-fb-userdata"

# Resolve browser config via Python helper
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build Python command to resolve browser path
if [ -n "${FB_USER_DATA_DIR:-}" ]; then
    USER_DATA_ARG="--user-data-dir ${FB_USER_DATA_DIR}"
else
    USER_DATA_ARG=""
fi

RESOLVED=$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPTS_DIR')
from _browser import BrowserConfig
try:
    config = BrowserConfig(
        name='$BROWSER',
        user_data_dir='${FB_USER_DATA_DIR:-}',
        profile='$PROFILE',
        port=$CDP_PORT,
        headless=$([ "$HEADLESS" = "1" ] && echo True || echo False),
    ).resolve()
    print(config['path'])
    print(config['name'])
    print(config['version'])
    print(config['user_data_dir'])
    print(' '.join(config['args']))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1) || {
    echo "❌ Browser resolution failed"
    echo "$RESOLVED"
    exit 1
}

BROWSER_PATH=$(echo "$RESOLVED" | sed -n '1p')
BROWSER_NAME=$(echo "$RESOLVED" | sed -n '2p')
BROWSER_VERSION=$(echo "$RESOLVED" | sed -n '3p')
BROWSER_USER_DATA_DIR=$(echo "$RESOLVED" | sed -n '4p')
BROWSER_ARGS=$(echo "$RESOLVED" | sed -n '5p')

# Snap chromium AppArmor work-around
if [ "$BROWSER_NAME" = "chromium" ] && [[ "$BROWSER_PATH" == "/snap/"* ]] && [ -z "$FB_USER_DATA_DIR" ]; then
    mkdir -p "$SNAP_USERDATA_DIR"
    BROWSER_ARGS=$(echo "$BROWSER_ARGS" | sed "s|--user-data-dir=[^ ]*|--user-data-dir=$SNAP_USERDATA_DIR|")
fi

echo "=========================================="
echo "BROWSER LAUNCH (SeleniumBase-hardened)"
echo "=========================================="
echo "Browser     : $BROWSER_NAME v$BROWSER_VERSION"
echo "Executable  : $BROWSER_PATH"
echo "Target URL  : $TARGET_URL"
echo "CDP port    : $CDP_PORT"
echo "User data   : ${FB_USER_DATA_DIR:-$SNAP_USERDATA_DIR (snap default)}"
echo "Profile     : $PROFILE"
echo "Headless    : $HEADLESS"
echo ""
echo "Sau khi browser mở:"
echo "  1. Login Facebook bình thường (hoặc dùng --cookie-file)"
echo "  2. Navigate tới post muốn scrape"
echo "  3. Chạy scripts/05_auto_scrape_cdp.py để extract data"
echo ""
echo "Optional: apply stealth via CDP"
echo "  python3 scripts/fb_cli.py stealth status"
echo "=========================================="
echo ""

# Launch browser in background so this script can exit
# (Don't use `exec` so the script can return after launch)
nohup $BROWSER_PATH $BROWSER_ARGS "$TARGET_URL" > /tmp/fb-browser-${CDP_PORT}.log 2>&1 &
BROWSER_PID=$!

sleep 3

# Verify CDP is up
if curl -s --max-time 3 "http://127.0.0.1:${CDP_PORT}/json/version" > /dev/null 2>&1; then
    echo "✓ Browser launched (PID: $BROWSER_PID), CDP ready on port $CDP_PORT"
    echo "  Log: /tmp/fb-browser-${CDP_PORT}.log"
else
    echo "⚠ Browser launched (PID: $BROWSER_PID) but CDP not yet ready"
    echo "  Log: /tmp/fb-browser-${CDP_PORT}.log"
    echo "  Wait a few seconds and check: curl http://127.0.0.1:${CDP_PORT}/json/version"
fi

# Optional persistent watchdog: relaunch the browser if it crashes, preserving
# the session (same user-data-dir). Started in the background; kill via
# `touch /tmp/fb-watchdog-<port>.stop` or pkill -f 09_browser_watchdog.py.
if [ "${FB_WATCHDOG:-0}" = "1" ]; then
    STOP_FILE="/tmp/fb-watchdog-${CDP_PORT}.stop"
    echo ""
    echo "→ Watchdog enabled (FB_WATCHDOG=1): browser auto-relaunches on crash"
    echo "  Stop: touch $STOP_FILE   |   Log: /tmp/fb-watchdog-${CDP_PORT}.log"
    nohup python3 "$SCRIPTS_DIR/09_browser_watchdog.py" \
        --port "$CDP_PORT" \
        --interval "${FB_WATCHDOG_INTERVAL:-5}" \
        --max-restarts "${FB_WATCHDOG_MAX_RESTARTS:-50}" \
        --stop-file "$STOP_FILE" \
        > /tmp/fb-watchdog-${CDP_PORT}.log 2>&1 &
    WATCHDOG_PID=$!
    echo "  Watchdog PID: $WATCHDOG_PID"
fi