# Facebook Skills Suite

> A toolkit to scrape, clean, and analyze Facebook data — designed so non-technical users can use it too.

[![CI Status](https://github.com/Enzosama/FB_Crawl_skills/actions/workflows/ci.yml/badge.svg)](https://github.com/Enzosama/FB_Crawl_skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Skills: 5](https://img.shields.io/badge/Skills-5-green.svg)](skills/)

## 📌 What does this repo do?

**Real-world example**: You see a Facebook post with many interesting comments about "Deepseek is so cheap, $10 lasts a whole month". You want to:

1. ✅ Collect all comments on that topic (including nested replies)
2. ✅ Save them locally to read offline
3. ✅ Find potential customers from commenters
4. ✅ Segment them into groups (VIP, new, repeat buyers...)

**This repo automates all 4 tasks** with just a few simple commands.

---

## 🚀 Quick Start (5 minutes)

### Method 1: Install via `npx skills` (recommended, 30 seconds)

If you use an AI agent that supports Skills (Claude Code, Hermes Agent, Cursor, Aider...), the fastest way is:

```bash
# Install ALL 5 skills to your agent
npx skills add github:Enzosama/FB_Crawl_skills -g -y

# Or install individual skills
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-crawl -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-data-clean -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-customer-segment -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-info-enrichment -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-anti-bot -g -y
```

After installing, reopen your AI agent — it will **automatically know** how to use each skill when you ask.

If you fork this repo to your own GitHub, replace `username` with your GitHub username. To install from local:

```bash
# Install from local directory
npx skills add /home/enzo/Documents/Facebook -g -y

# Or just one skill
npx skills add /home/enzo/Documents/Facebook --skill facebook-crawl -g -y
```

### Method 2: Manual setup (if you don't use an AI agent)

### Step 1: Open Facebook Browser

Open Terminal / Command Prompt and run:

```bash
bash scripts/01_open_chromium.sh
```

A Chromium browser will open. **Log in to Facebook manually** (use a secondary account, not your main one — for safety).

### Step 2: Collect Comments from a Post

Open the post you want in the browser, copy its URL, then run:

```bash
# Collect all comments (including nested replies) from a post
python3 scripts/fb_cli.py crawl deep "https://www.facebook.com/share/p/1ABCxyz/" --target 100
```

Results save to `data/posts/<post_name>/raw.json`.

### Step 3: Clean the Data

```bash
# Automatically removes duplicates, spam, and personal info
python3 scripts/04_clean_data.py data/posts/<post_name>/raw.json
```

Outputs: `clean.jsonl`, `quarantine.jsonl` (spam), `stats.json`.

### Step 4: View the Data

```bash
# List all crawled posts
python3 scripts/fb_cli.py list
```

Or open `data/posts/<post_name>/compact.json` with any text editor.

### Step 5: Advanced — page timeline, profile, bulk, export

**Crawl a fanpage timeline** (e.g. `/Nintendo`):
```bash
python3 scripts/fb_cli.py crawl timeline "https://www.facebook.com/<page-slug>" 30
# → data/posts/<page-slug>/raw.json (posts with reactions/comments/shares counts + pinned flag)
```

**Crawl a personal profile** (⚠️ only public profiles, with authorization):
```bash
python3 scripts/fb_cli.py crawl profile "https://www.facebook.com/<username>" --with-about --with-photos
# 3-stage: About (bio/work/education) + Posts (timeline) + Photos
```

**Bulk crawl from URL list** (50+ posts at once):
```bash
# urls.txt: one URL per line
python3 scripts/fb_cli.py bulk urls.txt --count 50
# → data/tests/<n>posts_<ts>/{full, compact, jsonl, manifest}.json
```

**Export to CSV / Parquet for analytics**:
```bash
python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl csv
python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl parquet
# 15-column flat schema (record_id, post_url, author, text, time_iso, n_images, ...)
```

**Audit past runs**:
```bash
python3 scripts/fb_cli.py audit             # summary of all crawls
python3 scripts/fb_cli.py audit --since 7d  # last 7 days
```

**Done!** You now have clean data to read or analyze further.

---

## ⚡ One-liner install (`npx skills`)

If you use an AI agent that supports Skills (Claude Code, Hermes Agent, Cursor, Aider...), copy any of these one-liners:

```bash
# Install ALL 5 skills globally (recommended for new users)
npx skills add Enzosama/FB_Crawl_skills -g -y

# Install individual skills
npx skills add Enzosama/FB_Crawl_skills --skill facebook-crawl -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-data-clean -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-customer-segment -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-info-enrichment -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-anti-bot -g -y

# Remove a skill
npx skills remove facebook-crawl

# Update to latest version
npx skills update
```

After installing, reopen your AI agent — it will **automatically know** how to use each skill when you ask about Facebook data.

---

## 🎯 Main Features

### 1. Collect Comments (Crawl)

| Command | Purpose |
|---------|---------|
| `python3 scripts/fb_cli.py crawl post <URL>` | Get top ~30 comments |
| `python3 scripts/fb_cli.py crawl deep <URL> --target N` | Get up to N comments (max ~60-100) |
| `python3 scripts/fb_cli.py crawl group <URL> [N]` | Get N posts from a group |
| `python3 scripts/fb_cli.py crawl page <URL> [N]` | Get N posts from a fanpage |

### 2. Clean Data (ETL)

| Task | Command |
|------|---------|
| Remove duplicates | Automatic in `04_clean_data.py` |
| Filter spam (promo links, group invitations) | Automatic |
| Mask emails, phone numbers | Automatic |
| Normalize Unicode (Vietnamese diacritics) | Automatic |

### 3. Analyze (AI Skills)

If you use an AI agent (like Hermes), it will automatically read files in `skills/` to know how to analyze:

- `skills/facebook-customer-segment/` — Segment customers (VIP, new, repeat)
- `skills/facebook-info-enrichment/` — Merge customer profiles across sources
- `skills/facebook-anti-bot/` — Tips to avoid Facebook detection (for developers)

### 4. Install individual skills

You don't need to install all 5 skills. Each is independent:

| Skill | When to use | Install command |
|-------|-------------|-----------------|
| `facebook-crawl` | Want to fetch new data from FB | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-crawl -g -y` |
| `facebook-data-clean` | Have raw data that needs cleaning | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-data-clean -g -y` |
| `facebook-customer-segment` | Want to segment customers | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-customer-segment -g -y` |
| `facebook-info-enrichment` | Want to merge profiles across sources | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-info-enrichment -g -y` |
| `facebook-anti-bot` | You're a dev wanting to avoid detection | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-anti-bot -g -y` |

**Remove installed skills**:

```bash
npx skills remove facebook-crawl
# or remove multiple at once
npx skills remove facebook-crawl facebook-data-clean
```

**Update skills to latest version**:

```bash
npx skills update
```

**List installed skills**:

```bash
npx skills list
```

---

## 📂 Folder Structure (simplified)

```
Facebook/
├── data/
│   ├── posts/                          ← Data for each post
│   │   ├── share_p_1AxneTWsfv/         ← Each post = 1 folder
│   │   │   ├── raw.json                ← Raw data just scraped
│   │   │   ├── clean.jsonl             ← Cleaned data
│   │   │   ├── compact.json            ← Compact file for reading/AI
│   │   │   └── stats.json              ← Statistics
│   │   └── ...
│   ├── tests/                          ← Automated test results
│   └── README.md                       ← Data folder guide
├── scripts/                            ← Main commands
│   ├── 01_open_chromium.sh             ← Open browser
│   ├── 04_clean_data.py                ← Clean data
│   ├── 05_auto_scrape_cdp.py           ← Auto-scrape comments
│   └── fb_cli.py                       ← User-friendly wrapper
├── skills/                             ← Guides for AI agents
│   ├── facebook-crawl/                 ← How to scrape
│   ├── facebook-data-clean/            ← How to clean
│   ├── facebook-customer-segment/      ← How to segment customers
│   ├── facebook-info-enrichment/       ← How to enrich profiles
│   └── facebook-anti-bot/              ← How to avoid detection
└── README.md                           ← This file (English)
```

**Simple explanation**:

- `data/posts/<name>/` — Each Facebook post = 1 folder. Inside are different data files.
- `scripts/` — Commands to run. You usually only need `01_open_chromium.sh` + `fb_cli.py crawl` + `04_clean_data.py`.
- `skills/` — Read by AI agents. You don't need to read directly.

---

## 📚 Detailed Guides by Scenario

### Scenario 1: I want to get comments from 1 post

```bash
# 1. Open browser
bash scripts/01_open_chromium.sh

# 2. Open the post you want in the browser, copy URL

# 3. Back in Terminal, run:
python3 scripts/fb_cli.py crawl deep "YOUR_URL" --target 100

# 4. Wait 1-2 minutes. Results at data/posts/<post_name>/raw.json

# 5. Clean:
python3 scripts/04_clean_data.py data/posts/<post_name>/raw.json

# 6. Open compact.json to view:
cat data/posts/<post_name>/compact.json
```

### Scenario 2: I want to get posts from a Facebook group

```bash
# Get 20 latest posts from a group
python3 scripts/fb_cli.py crawl group "https://www.facebook.com/groups/your-group" 20
```

Results save to `data/posts/groups_<group_id>/`.

### Scenario 3: I want to send data to AI for analysis

Open `data/posts/<post_name>/compact.json` (about 3,000 tokens for 60 comments) and send it to AI with your question:

```
These are comments from a Facebook post about [topic]. Please:
1. Summarize the main opinions
2. Classify sentiment (positive/negative)
3. Identify potential customers showing interest
```

### Scenario 4: I want to see how much data I have

```bash
python3 scripts/fb_cli.py list
```

Output:
```
=== Posts (6) ===
  share_p_1AxneTWsfv             60 comments, 6 files
  share_p_1DLJccgZNY              5 comments, 3 files
  groups_852586990732832_...     60 comments, 12 files
```

---

## ⚠️ Important Notes

### 🛡️ Account Safety

1. **ALWAYS use a secondary account**, never your main account
2. Don't scrape too much (max a few dozen posts per day)
3. Wait a few seconds between scraping requests
4. If Facebook asks for verification (captcha, OTP), log in manually

### ⚖️ Legal Compliance

1. **Do NOT scrape private data** (friends, strangers, locked profiles)
2. **Do NOT sell personal data** — violates data protection laws (PDPA Vietnam, GDPR EU)
3. **Do NOT spam** or use data for unauthorized marketing
4. **Respect privacy**: anonymize users if you use their data

### 🔧 Technical

1. Tool works with **pre-installed Chromium browser**
2. Requires **Python 3.10+**
3. Browser must be logged into Facebook before running commands
4. If errors occur, check `data/posts/<name>/stats.json` for details

---

## 🆘 Troubleshooting

### "Cannot find Facebook tab"

**Cause**: Browser not opened or not logged in.
**Fix**: Run `bash scripts/01_open_chromium.sh` and log in to Facebook.

### "Got 0 comments"

**Cause**: Post has no public comments, or Facebook changed its UI.
**Fix**: Try a different post. If still fails, report to a developer.

### "Permission denied"

**Cause**: Snap Chromium can't write to home directory.
**Fix**: No fix needed — tool already uses `/home/enzo/snap/chromium/common/`.

### "compact.json is too large for AI"

**Cause**: Post has more than 100 comments.
**Fix**: Split the file, or send only top 30-50 comments (skip replies).

---

## 📖 Glossary

| Term | Meaning |
|------|---------|
| **Crawl / Scrape** | Automatically collect data from websites |
| **Post** | A Facebook post/article |
| **Comment** | A comment on a post |
| **Reply** | A response to a comment |
| **Group** | Facebook group |
| **Page** | Fanpage / public page |
| **CDP** | Chrome DevTools Protocol — how the tool talks to browser |
| **JSON** | A data format (like a spreadsheet) |
| **JSONL** | One JSON record per line |
| **PII** | Personally Identifiable Information (emails, phones, names) |

---

## 🛠️ For Developers

If you know code and want to extend:

```bash
# Quick test
python3 scripts/05_auto_scrape_cdp.py --help

# Debug
python3 scripts/fb_cli.py status  # Check browser connection

# View data structure
python3 scripts/_data_paths.py  # Test path helpers
```

Read files in `skills/` to understand how the tool works in detail.

---

## 📜 License

MIT License — Free to use, modify, distribute. As long as you comply with laws and Facebook ToS.

---

## 🤝 Contributing

Have improvement ideas? Create an issue or pull request. Especially needed:

- More language support (currently Vietnamese + English)
- Speed optimizations
- New analysis features

See `README.md` (Vietnamese) for the Vietnamese version.