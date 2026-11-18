#!/usr/bin/env bash
# DEPRECATED: Use 01_open_browser.sh instead.
# This script is kept for backward compatibility.
#
# Forwards all args to 01_open_browser.sh, with FB_BROWSER=chromium as default.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/01_open_browser.sh" "$@"