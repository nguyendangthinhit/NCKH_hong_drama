---
name: facebook-anti-bot
description: "Anti-bot / anti-detection patterns for Facebook crawling — fingerprinting, proxies, pacing, account warming, SeleniumBase-inspired chromedriver patching, multi-browser + cookie injection support. INCLUDES mandatory legal/ToS warnings."
version: 2.2.0
author: Facebook Skills Suite
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [facebook, anti-bot, stealth, scraping, fingerprinting, legal-warning, chromedriver-patch, multi-browser, cookies]
    related_skills: [facebook-crawl, facebook-data-clean]
---

# Facebook Anti-Bot

Patterns for reducing Facebook detection when crawling: IP fingerprinting, browser fingerprinting, behavior signals, account warming. **READ THE LEGAL WARNING BEFORE APPLYING.**

## ⚠️ Legal & ToS Warning

> **IMPORTANT — READ BEFORE USING THIS SKILL:**

1. **Violates Meta ToS**: Automatically crawling Facebook Graph API unofficially, scraping HTML, or using unofficial libraries **violates Meta Terms of Service** and **Platform Policy**. Accounts can be permanently banned (personal + business), IPs blacklisted, or sued.

2. **May violate laws depending on jurisdiction**:
   - **EU**: GDPR may apply if collecting publicly-available data of EU residents without lawful basis
   - **Vietnam**: Decree 13/2023/NĐ-CP on personal data protection. Collecting PII without consent can be fined
   - **California (CCPA)**, **Brazil (LGPD)**: similar
   - **USA (CFAA)**: unauthorized access to computer systems can be a criminal offense

3. **Safest path**: **Only use official Graph API** with your own tokens (pages you own, reviewed app). The techniques in this skill are for **research/educational** and **authorized use cases** (e.g. competitor monitoring for brand audit with legal review).

4. **No warranty**: Techniques may stop working at any time. Facebook updates detection continuously.

5. **Liability**: User is solely responsible for legal compliance. The skill author bears no responsibility.

**If you do not have explicit authorization from the data owner or legal counsel → STOP. Use official API or buy data from data providers (Apify, Bright Data, Meltwater, etc.).**

## When to use this skill

Load this skill when you:
- **Have legal clearance** to crawl (e.g. IRB-approved research, contracted brand audit)
- Need to reduce detection rate for unofficial scrapers (`facebook-scraper`, playwright)
- Need to manage multiple accounts to distribute load
- Need fallback strategy when an account hits a checkpoint

DO NOT load this skill if:
- You already have official Graph API access + token
- Your use case needs large scale (>1M posts/day) → use a data provider with infrastructure
- You haven't read the legal warning above

## Core capabilities

- **IP fingerprinting awareness**: understand how FB detects IP (ASN, datacenter, residential, mobile)
- **Browser fingerprinting awareness**: understand how FB detects browser (canvas, WebGL, audio, fonts)
- **Countermeasure patterns**: stealth plugins, fingerprint randomization
- **Proxy rotation**: residential proxy, mobile proxy, datacenter proxy (tradeoffs)
- **Account warming**: ramp-up volume so the account "looks like a real person"
- **Cookie/session management**: persist session, refresh strategy
- **Behavior signals**: pacing, scroll patterns, mouse movements
- **Checkpoint handling**: what to do when FB asks for CAPTCHA/checkpoint

## Detection vectors of Facebook

### 1. IP-level signals

| Signal | Risk level | Description |
|--------|-----------|-------------|
| Datacenter IP (AWS, GCP, Azure) | **High** | FB blocks or rate-limits heavily |
| Residential IP | Low | Same subnet as real users → hard to detect |
| Mobile IP (3G/4G carrier) | **Lowest** | FB can't easily distinguish from real mobile users |
| IP shared with spam accounts | **High** | ASN reputation, blacklists exist |
| Geo mismatch (token VN but IP US) | **High** | Login from unusual country = red flag |
| IP rotation too fast | Medium | 10 different IPs in 1 minute = bot pattern |

### 2. Browser fingerprint signals

| Signal | Detection method | Counter |
|--------|-----------------|---------|
| User-Agent | Header check | Rotate per session |
| Canvas fingerprint | Render text → hash | Spoof / randomize |
| WebGL fingerprint | GPU vendor/renderer | Spoof |
| Audio context | AudioContext API | Spoof |
| Fonts | Enumerate installed fonts | Spoof list |
| Screen resolution | `window.screen` | Match common resolutions |
| Timezone | `Intl.DateTimeFormat` | Match proxy IP geo |
| Language | `navigator.language` | Match geo |
| WebRTC leaks | STUN servers leak real IP | Disable WebRTC |
| Plugins / mimeTypes | `navigator.plugins` | Spoof to default |
| Hardware concurrency | `navigator.hardwareConcurrency` | Randomize 4-16 |
| Device memory | `navigator.deviceMemory` | Randomize 4-16 |

### 3. Behavior signals

| Signal | Bot pattern | Human pattern |
|--------|------------|---------------|
| Request interval | Constant 100ms | Variable 2-30s |
| Mouse movements | None or straight lines | Curves, jitter, hover |
| Scroll | Instant jump to bottom | Variable speed, pauses |
| Click coordinates | Always center / always same spot | Variable |
| Time on page | < 2s before next action | > 10s for feed browsing |
| Sequential actions | All clicks within 1s | Spread out, idle gaps |
| URL navigation | Direct GET | Real referrer chain |

### 4. Account-level signals

| Signal | Risk |
|--------|------|
| Account age < 30 days | **Very high** — new account + active = bot signal |
| Account without profile pic/cover | Medium |
| Account without friends (< 50) | Medium |
| Account never posts | Medium |
| Login from many countries | **High** |
| Many Graph API calls without user behavior | **High** |

## Countermeasures

### Counter 1 — Residential / Mobile proxy rotation

**Setup**:
- Buy residential proxy (e.g. Bright Data, Smartproxy, IPRoyal) — $5-15/GB
- Mobile proxy (carrier-grade NAT) — more expensive but FB rate-limits lightest
- Rotate per session (one IP per account, sticky 30-60 minutes)

```python
# Example with Bright Data
PROXY = "http://user:pass@brd.superproxy.io:22225"
proxies = {"http": PROXY, "https": PROXY}

# Rotate session every 100 requests
session_id = random.randint(1, 10000)
proxy_url = f"http://user:pass-{session_id}:@brd.superproxy.io:22225"
```

**Note**: Free proxy **cannot be used** — already all blacklisted.

### Counter 2 — Browser fingerprint randomization (playwright)

Use `playwright-stealth` or `undetected-playwright`:

```python
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth  # 2.x API

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False less detected
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )

        # Apply stealth to context (works for all pages)
        stealth = Stealth(
            navigator_languages_override=("vi-VN", "vi", "en-US", "en"),
            navigator_platform_override="Win32",
        )
        await stealth.apply_stealth_async(context)

        page = await context.new_page()

        # Extra stealth props
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']});
        """)

        await page.goto("https://www.facebook.com")
        # ... manual login wait + cookie save
```

### Counter 3 — Human-like pacing

```python
import random
import time

def human_pause(mean: float = 5.0, sigma: float = 2.0):
    """Pause with human-like distribution (Gaussian + occasional long pause)."""
    delay = max(0.5, random.gauss(mean, sigma))
    time.sleep(delay)

def human_action_sequence(actions: list):
    """Occasionally insert long pause (simulating user reading content)."""
    for i, action in enumerate(actions):
        action()
        if random.random() < 0.1:  # 10% long pause
            human_pause(mean=30, sigma=10)
        else:
            human_pause(mean=5, sigma=2)
```

### Counter 4 — Account warming strategy

**Rule**: New accounts need ramp-up volume.

| Week | Actions/day | Notes |
|------|-------------|-------|
| Week 1 | 5-10 | Like, light comment, no scrape |
| Week 2 | 20-30 | Add friends, join groups |
| Week 3 | 50-80 | Post occasional content |
| Week 4+ | 100-200 | Start light crawling |

**Daily pattern**:
- Don't crawl all day — 2-3 sessions, each 30-90 minutes
- Each session: scroll feed naturally 5-10 minutes before entering target page
- Rest 2-4 hours between sessions
- Avoid crawling at the same hour each day (random hour between 7AM-11PM local)

### Counter 5 — Cookie/session management

```python
import json
from pathlib import Path

COOKIE_DIR = Path("./cookies")
COOKIE_DIR.mkdir(exist_ok=True)

async def login_and_save(email, password, account_name):
    context = await browser.new_context(...)
    page = await context.new_page()
    await page.goto("https://www.facebook.com/login")
    await page.fill('input[name="email"]', email)
    await page.fill('input[name="pass"]', password)
    await page.click('button[name="login"]')
    await page.wait_for_url("https://www.facebook.com/")

    # Save cookies
    cookies = await context.cookies()
    with open(COOKIE_DIR / f"{account_name}.json", "w") as f:
        json.dump(cookies, f, indent=2)

async def load_session(account_name):
    cookies_file = COOKIE_DIR / f"{account_name}.json"
    if not cookies_file.exists():
        return None
    cookies = json.loads(cookies_file.read_text())
    context = await browser.new_context(...)
    await context.add_cookies(cookies)
    return context
```

Cookies typically valid 30-90 days if account is active. Refresh when nearing expiry.

### Counter 6 — Checkpoint handling

When FB shows CAPTCHA / "Suspicious Login" / "Confirm your identity":

1. **STOP IMMEDIATELY** the bot running with that account
2. **Mark** the account as "burned", switch to another account
3. **Wait 24-48 hours** before retrying (if there's still a chance)
4. **Investigate**: was it due to new IP? stale cookie? sudden action volume spike?
5. **Tune** strategy: rotate IP, reduce volume, change user agent
6. **Consider abandoning** the account if checkpoint appears > 3 times in a week → account is flagged

**Do NOT solve CAPTCHA automatically** — violates ToS, may trigger permanent ban.

## Step-by-step workflow: setting up anti-bot crawl

### Step 1 — Risk assessment

Ask yourself:
- Do I have legal clearance?
- What's the volume? (< 1K posts/day lower risk than > 100K)
- Do I have budget for proxies + account farms?
- Do I have time to monitor checkpoints?

If risk too high → use data provider.

### Step 2 — Acquire resources

- Residential proxy subscription ($50-200/month depending on volume)
- 5-20 warmed accounts (buy from farms or self-warm — both have legal risk)
- CAPTCHA solving budget (if unavoidable — not recommended)

### Step 3 — Build test crawl

- Run one small session (10-20 posts) with 1 account + 1 IP
- Monitor response: CAPTCHA? Full data returned?
- Tune fingerprint, pacing

### Step 4 — Scale gradually

- Week 1: 1 account, 1 IP, 50-100 posts/day
- Week 2: 2 accounts, 2 IPs, 200-500 posts/day
- Week 3+: scale if no checkpoint

### Step 5 — Monitor & adapt

- Daily check: checkpoint? IP blocked? Account locked?
- Weekly: review volume, success rate
- If success rate drops → pause, investigate

## Anti-patterns

- ❌ **Use datacenter IP** — FB blocks almost immediately
- ❌ **headless=True without stealth** — `navigator.webdriver = true` is giveaway
- ❌ **Crawl 24/7** — anomaly detection triggers within hours
- ❌ **Skip checkpoint** — forcing account to verify burns it faster
- ❌ **Auto-solve CAPTCHA with ML** — ToS violation, permanent ban
- ❌ **Use accounts just created (< 7 days)** — almost guaranteed checkpoint
- ❌ **Same User-Agent across multiple accounts** — linkable signal
- ❌ **Skip referrer header** — direct GET with no referrer = bot signature
- ❌ **No proxy rotation** — 1 IP for 100 accounts = cluster detected
- ❌ **Save fingerprinting config to git** — leaks detection evasion to FB engineers

## Pitfalls

1. **Stealth plugin outdated** — playwright-stealth needs updating per playwright version. Stealth breaks often
2. **Account farms have legal risk** — bought accounts may be stolen
3. **Mobile proxy expensive** — $50-200/month/IP, scaling costs a lot
4. **IP reputation decay** — residential IP used heavily = reputation drops → need to rotate pool
5. **FB changes detection** — techniques today may be useless next week. Must monitor + adapt
6. **2FA bypass** — don't try. When account has 2FA, treat as burned
7. **Checkpoint false positives** — sometimes checkpoint due to real user (e.g. login from new IP). Not always bot
8. **Cookie sharing across IPs** — cookie has session IP info, load cookie + use different IP → immediate checkpoint
9. **Detection signatures in HTML** — FB analyzes response timing, header order, TLS fingerprint. Pure browser stealth isn't enough
10. **Snap chromium + AppArmor** — sandboxing issues can leak fingerprint via unusual permissions

## Verification commands

```bash
# Check IP type (datacenter vs residential)
curl -s https://ipinfo.io/json | jq '{ip, org, country}'

# Check WebRTC leak (in browser)
# javascript: RTCPeerConnection → see if IP leaks

# Test fingerprint (via browser)
# https://bot.sannysoft.com → see bot detection signals
# https://browserleaks.com → check canvas, WebGL, fonts

# Monitor checkpoint count
grep -c "checkpoint" crawl_log.txt  # should be 0 or very low
```

## Quick start (playwright stealth)

```python
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

PROXY = "http://user:pass@residential-proxy.example.com:8000"

async def scrape_page(page_id: str, max_posts: int = 50):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            proxy={"server": PROXY},
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        stealth = Stealth(navigator_languages_override=("vi-VN", "vi", "en-US", "en"))
        await stealth.apply_stealth_async(context)
        page = await context.new_page()

        # Manual login first (once), save cookies
        # ... (see Counter 5)

        await page.goto(f"https://www.facebook.com/{page_id}/posts/")
        # ... scroll + extract posts
        await browser.close()

asyncio.run(scrape_page("nintendo"))
```

## Multi-browser + cookie injection

Run scraping from any Chromium-based browser, with optional cookie-based auth (no manual login needed).

### Supported browsers

| Browser | Linux path | CDP support |
|---------|-----------|-------------|
| `chromium` (snap) | `/snap/bin/chromium` | ✓ |
| `google-chrome` | `/usr/bin/google-chrome` | ✓ |
| `brave` | `/usr/bin/brave-browser` | ✓ |
| `microsoft-edge` | `/usr/bin/microsoft-edge` | ✓ |
| `opera` | `/usr/bin/opera` | ✓ |
| `firefox` | `/usr/bin/firefox` | Partial (Marionette, not full CDP) |

Auto-detect is the default. Set explicitly with `FB_BROWSER=chrome bash scripts/01_open_browser.sh`.

### Login-wall (logged-out) handling

When a session is not authenticated, Facebook renders a fixed overlay
(`<form id="login_popup_cta_form">`, the "Xem thêm trên Facebook" CTA) on top of
post content. The crawler can dismiss this overlay via CDP (`--dismiss-login-wall`
or `FB_DISMISS_LOGIN_WALL=1`) to expose any DOM behind it.

**Partial, not zero (corrected 2026-07-12)**: FB *does* render a PARTIAL comment set
behind the wall to a logged-out session — a fresh chromium pulled 6 of 10 comments
on a public post. Dismissing the overlay then lets the normal extractor capture
that partial set (saved as `partial_logged_out`). The FULL set (all comments, deep
replies) is only available with cookie auth (`--cookie-file` / `--cookie-string`) or
manual login. A best-effort no-auth fallback (`_lightweight.py`, the `?__a=1` public
post-text endpoint) can salvage the public post body when Facebook serves it, but
this endpoint is unofficial and
may break.

### Launch any browser

```bash
# Default: auto-detect (chromium → chrome → brave → edge)
bash scripts/01_open_browser.sh

# Explicit browser
FB_BROWSER=google-chrome bash scripts/01_open_browser.sh
FB_BROWSER=brave bash scripts/01_open_browser.sh
FB_BROWSER=firefox bash scripts/01_open_browser.sh

# Custom user data dir
FB_USER_DATA_DIR=~/my-profile bash scripts/01_open_browser.sh

# Headless
FB_HEADLESS=1 bash scripts/01_open_browser.sh
```

### Cookie-based auth (no manual login)

Export cookies from a logged-in browser session, then inject via CDP. Two formats supported:

**Format 1: Netscape (curl/wget style)**

```text
# Netscape HTTP Cookie File
.facebook.com	TRUE	/	TRUE	1735689600	c_user	1234567890
.facebook.com	TRUE	/	TRUE	1735689600	xs	abc:def:ghi
#HttpOnly_.facebook.com	TRUE	/	TRUE	1735689600	xs	abc:def:ghi
```

Export via:
- Chrome extension "EditThisCookie" → Export → Netscape
- Firefox extension "Cookie-Editor" → Export → Netscape
- `curl` with cookie jar: `curl -c cookies.txt https://facebook.com/login`

**Format 2: JSON (browser extension array)**

```json
[
  {"name": "c_user", "value": "1234567890", "domain": ".facebook.com", "secure": true},
  {"name": "xs", "value": "abc:def:ghi", "domain": ".facebook.com", "secure": true, "httpOnly": true}
]
```

**Format 3: Raw string (one-time use, expires after session)**

```bash
# Format: name=value; name2=value2
python3 scripts/05_auto_scrape_cdp.py "https://facebook.com/..." \
    --cookie-string "c_user=1234567890; xs=abc:def:ghi" \
    --target 100
```

### Cookie injection via CDP

`Network.setCookie` per cookie, after `Network.enable`:

```javascript
// JS snippet (used internally by _browser.py)
{
  "id": N,
  "method": "Network.setCookie",
  "params": {
    "name": "c_user",
    "value": "1234567890",
    "domain": ".facebook.com",  // or specific subdomain
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "expires": 1735689600  // seconds since epoch (0 = session)
  }
}
```

**Important gotchas**:
- Must `Network.enable` FIRST before any `setCookie` call
- Cookies are per-page (per-target). Need to inject into each open page
- Domain must match or be parent of where cookie is set
- `c_user` and `xs` cookies are required for FB auth; `fr` is also useful
- If cookie is `HttpOnly`, must set `httpOnly: true` (won't be set otherwise)

### Browser auto-detection (for agents)

```python
from _browser import detect_browsers, BrowserConfig

browsers = detect_browsers()
# Returns: [{name, path, version, user_data_dir}, ...]
# chromium first (priority), then chrome, brave, edge, firefox

config = BrowserConfig(name="auto", port=9222).resolve()
# Returns: {name, path, version, user_data_dir, profile, port, args}
```

### Headless server deployment

For cron jobs or server-side scraping without GUI:

```bash
# 1. Export cookies from your local browser (Netscape or JSON)
# 2. Save to /opt/cookies/fb.txt
# 3. Run headless:
FB_HEADLESS=1 FB_BROWSER=chromium bash scripts/01_open_browser.sh
python3 scripts/05_auto_scrape_cdp.py "https://facebook.com/share/p/POST_ID/" \
    --cookie-file /opt/cookies/fb.txt \
    --target 100 \
    --headless
```

**Critical**: cookies expire (xs lasts ~hours, c_user lasts ~year). Re-export periodically.

## SeleniumBase-inspired techniques

Patterns adapted from SeleniumBase's `seleniumbase/undetected/` module (MIT licensed — https://github.com/seleniumbase/SeleniumBase). We adopt techniques, not the library — keeps our lean bash+CDP stack.

### 1. Chromedriver binary patching (cdc_ fingerprint removal)

SeleniumBase's signature technique (from `seleniumbase/undetected/patcher.py:121-247`). The `cdc_adoQpoasnfa76pfcZLmcfl_*` variable in chromedriver binary is the most reliable detection vector — sites inspect `window.cdc_adoQpoasnfa76pfcZLmcfl_Array` to identify automated browsers.

**3 regex substitutions** (copied verbatim from SeleniumBase):

```python
import io
import re
import random
import string

# From SeleniumBase patcher.py:226-244
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

def patch_chromedriver_binary(path: str) -> bool:
    """Patch chromedriver to remove cdc_ fingerprint. Returns True if changed."""
    with io.open(path, "r+b") as fh:
        content = fh.read()
        content = _CDC_VAR_REGEX.sub(lambda m: b"\n" * len(m.group()), content)
        content = _CDC_PIPE_REGEX.sub(lambda m: b"\n" * len(m.group()), content)
        content = _CDC_CACHE_REGEX.sub(
            lambda m: b"'" + bytes(
                "".join(random.choices(string.ascii_letters, k=random.randint(6, len(m.group())-3))),
                "ascii",
            ) + b"';",
            content,
        )
        fh.seek(0)
        fh.write(content)
    return True
```

**Usage**: Only applies if you use Selenium WebDriver. With bash+CDP (our default), no chromedriver binary is loaded — this technique is moot.

**Check if patched** (from `patcher.py:201-210`):
```python
def is_binary_patched(path: str) -> bool:
    with io.open(path, "rb") as fh:
        if re.search(
            b"window.cdc_adoQpoasnfa76pfcZLmcfl_"
            b"(Array|Promise|Symbol|Object|Proxy|JSON|Window)",
            fh.read(),
        ):
            return False  # unpatched
    return True  # patched
```

**Warning**: Patching is destructive. Always backup first. Only valid for chromedriver < v115 (newer uses different binary structure).

### 2. Detached subprocess launch

From `seleniumbase/undetected/dprocess.py:39-53`. Spawns chromedriver as a fully independent subprocess so the parent process doesn't leak via `/proc/<pid>/status` inspection.

```python
import subprocess
import os

def start_chromium_detached(args: list, user_data_dir: str, port: int = 9222):
    """Launch chromium as detached subprocess with start_new_session=True."""
    args = [
        "chromium",
        f"--user-data-dir={user_data_dir}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",  # chromium-only; Opera rejects it
        # ... more flags
    ]
    kwargs = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True  # POSIX: detach from parent
    else:
        kwargs["creationflags"] = 0x00000200 | 0x00000008  # Windows
    return subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
```

**Plus `atexit` cleanup** (from `dprocess.py:56-65`) — SIGTERM orphaned processes on script exit:

```python
import atexit
import signal

_SPAWNED = []

def _cleanup():
    for pid in _SPAWNED:
        try: os.kill(pid, signal.SIGTERM)
        except: pass

atexit.register(_cleanup)
```

### 3. Stealth init script (minimal)

SeleniumBase's approach is simpler than `playwright-stealth`. We inject this via CDP's `Page.addScriptToEvaluateOnNewDocument` so it runs before every page load:

```javascript
(() => {
    // 1. Remove webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // 2. Fake plugins array
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

    // 3. Languages stack
    Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });

    // 4. Realistic hardware
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // 5. Remove cdc_ variable if exposed
    if (typeof window !== 'undefined') {
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_;
    }

    // 6. Chrome runtime stub
    if (typeof window.chrome === 'undefined') {
        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
    }
})();
```

### 4. Anti-fingerprint chromium flags

The combination SeleniumBase uses (extracted from `Chrome.__init__` defaults):

```bash
chromium \
    --user-data-dir=/path/to/profile \
    --no-first-run \
    --no-default-browser-check \
    --password-store=basic \
    --disable-blink-features=AutomationControlled \  # chromium-only; Opera rejects it
    --disable-features=IsolateOrigins,site-per-process,InterestFeedContentSuggestion \
    --lang=vi-VN \
    --window-size=1366,768 \
    --remote-debugging-port=9222 \
    --remote-allow-origins=* \
    "$URL"
```

**Flag rationale**:
- `--no-first-run` — skip "Welcome to Chrome" first-run dialog
- `--no-default-browser-check` — skip "Make Chrome your default" prompt
- `--password-store=basic` — use basic password store (no GNOME Keyring prompts)
- `--disable-blink-features=AutomationControlled` — removes `navigator.webdriver = true` flag (though we override in init script too). **Chromium/Chrome/Brave/Edge only** — Opera rejects this flag with a stability/security banner, so the launcher omits it for Opera (the stealth init script already overrides `navigator.webdriver`).
- `--disable-features=IsolateOrigins,site-per-process` — disable per-site process isolation (reduces fingerprint variance)
- `--remote-allow-origins=*` — needed for CDP from non-localhost origins (newer Chromium requires this)

### 5. `ChromeOptions.handle_prefs()` pattern

From `seleniumbase/undetected/options.py:40-72`. When using Selenium WebDriver, strip these from `experimental_options` before passing to Chrome:

```python
# Remove these — they leave tell-tale flags in Chrome's state
exclude_switches = self.experimental_options.get("excludeSwitches")
if exclude_switches is not None:
    del self._experimental_options["excludeSwitches"]

use_auto_ext = self.experimental_options.get("useAutomationExtension")
if use_auto_ext is not None:
    del self._experimental_options["useAutomationExtension"]
```

**Why**: Chrome stores these in `~/.../Default/Preferences`. If left enabled, FB can detect automation mode even after browser restart.

### 6. CDP events enable

From `Chrome.__init__(enable_cdp_events=True)`. Our bash+CDP approach already uses websocket directly — no change needed. Just note this if you migrate to SeleniumBase library.

### When these techniques DON'T apply

- **bash+CDP approach** (our default): no chromedriver, no Selenium — patches/init scripts are unnecessary. Only the flag selection (#4) matters.
- **Playwright stealth** (alternative): uses `playwright-stealth` library which has its own approach — don't mix with SeleniumBase patterns.
- **HTTP-only Graph API** (cleanest): no browser, no anti-bot needed at all.

### Attribution

SeleniumBase is MIT licensed. Original code by Michael Mintz (https://github.com/seleniumbase/SeleniumBase/blob/master/LICENSE). Patterns above are **adapted** (not copied verbatim) — see `scripts/_stealth.py` for our implementation.

## Changelog

- **v2.2.0** (current): Added multi-browser support (chromium/chrome/brave/edge/firefox) with auto-detect. Added cookie-based auth via `--cookie-file` (Netscape/JSON) and `--cookie-string` (raw). New `_browser.py` module with `BrowserConfig` + `parse_cookie_file` + `parse_cookie_string` + `inject_cookies`. New `01_open_browser.sh` generic launcher + `01_open_chromium.sh` deprecated alias. New `stealth_cli.py cookies` subcommand.
- **v2.1.0**: Added `stealth_cli.py` subcommands (`stealth status`, `stealth patch`, `stealth inject`, `stealth launch`). Documented SeleniumBase's `start_new_session=True` for fully-detached process.
- **v2.0.0**: English rewrite. Added 3 reproduction templates (SeleniumBase / undetected-playwright / DIY cdc_ patch).

## Reference

- SeleniumBase undetected module: https://github.com/seleniumbase/SeleniumBase/tree/master/seleniumbase/undetected
- SeleniumBase Patcher: https://github.com/seleniumbase/SeleniumBase/blob/master/seleniumbase/undetected/patcher.py
- SeleniumBase dprocess: https://github.com/seleniumbase/SeleniumBase/blob/master/seleniumbase/undetected/dprocess.py
- Chrome DevTools Protocol: https://chromedevtools.github.io/devtools-protocol/
- playwright-stealth: https://github.com/nicpenning/playwright-stealth
- Bright Data residential proxy: https://brightdata.com/proxy-types/residential
- Meta ToS: https://www.facebook.com/terms.php
- Meta Platform Policy: https://transparency.meta.com/policies/community-standards
- GDPR crawler guidance: https://edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-012020-measures-supplement-transfer_en
- Vietnam PDPA (Decree 13/2023): https://vanban.chinhphu.vn/?pageid=27160&docid=204991