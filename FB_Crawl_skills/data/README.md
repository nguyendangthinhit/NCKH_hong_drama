# Facebook Data — Folder Structure

Each crawl request produces one folder. This makes per-post data easy to find, version, and share.

## Structure

```
data/
├── posts/
│   ├── <sanitized_post_url>/     # one folder per post
│   │   ├── raw.json              # raw scraped comments (overwritten on next scrape)
│   │   ├── raw_<timestamp>.json  # timestamped backups when raw.json already exists
│   │   ├── clean.jsonl           # cleaned comments (dedup + spam filter + PII redact)
│   │   ├── compact.json          # compact format for small models (~3K tokens for 60 comments)
│   │   ├── jsonl.jsonl           # line-per-comment JSONL
│   │   ├── full.json             # full data with images (alias of jsonl + extra fields)
│   │   ├── full_sort_relevant.json # optional: variant from default sort
│   │   ├── compact_sort_relevant.json # optional: compact variant from default sort
│   │   ├── stats.json            # extraction statistics
│   │   ├── quarantine.jsonl      # filtered spam
│   │   └── clean_<ts>.jsonl      # older cleaned versions
│   └── ...
├── tests/
│   └── <test_run>/
│       ├── compact.json
│       ├── compact.jsonl
│       └── full.json
└── archive/                      # files that don't fit post/test structure
    └── misc/                     # group feed files, deep mode runs
```

## Sanitized URL → Folder Name

URLs are converted to safe folder names:

| URL | Folder |
|-----|--------|
| `https://www.facebook.com/share/p/1AxneTWsfv/` | `share_p_1AxneTWsfv` |
| `https://www.facebook.com/groups/852586990732832/permalink/987297817261748/` | `groups_852586990732832_permalink_987297817261748` |
| `https://www.facebook.com/mrgoonie/posts/pfbid02ga5kqBVMVEd...` | `mrgoonie_posts_pfbid02ga5kqBVMVEdKS6drvsZ8KLHg2WA6e2BJED3SM25QRC3ZuwtLSzjidPqZpVaAhwZvl` |

The pfbid post URLs are long. Workaround: copy `raw.json` into a shorter folder name.

## Workflow

### Crawl a new post

```bash
# Run scraper — saves to posts/<slug>/raw.json (or raw_<ts>.json if exists)
python3 scripts/fb_cli.py crawl deep "https://www.facebook.com/share/p/1ABC/" --target 100

# Or directly:
python3 scripts/05_auto_scrape_cdp.py "https://www.facebook.com/share/p/1ABC/" --target 100
```

### Clean a post's raw data

```bash
# Auto-detects post folder from input location
python3 scripts/04_clean_data.py data/posts/share_p_1ABC/raw.json

# Explicit override
python3 scripts/04_clean_data.py path/to/raw.json --output-dir data/posts/share_p_1ABC/
```

### List all data

```bash
python3 scripts/fb_cli.py list
```

Output:
```
=== Posts (6) ===
  share_p_1AxneTWsfv                                  60 comments, 6 files
  share_p_1DLJccgZNY                                   5 comments, 3 files
  groups_852586990732832_permalink_987297817261748   60 comments, 12 files
  ...
```

### Custom folder for pfbid posts

If the slug is too long, rename the folder:

```bash
mv data/posts/mrgoonie_posts_pfbid02ga5kqBVMVEd... data/posts/mrgoonie_AI_Claude_post
```

The folder name is purely organizational — it doesn't affect scraping.

## File Naming Conventions

| File | Content | Stable? |
|------|---------|---------|
| `raw.json` | Most recent raw scrape | Overwritten |
| `raw_<ts>.json` | Backup of previous scrapes | Keep all |
| `clean.jsonl` | Most recent cleaned data | Overwritten |
| `compact.json` | Most recent compact format | Overwritten |
| `full.json` | Most recent full data (with images) | Overwritten |
| `jsonl.jsonl` | Most recent JSONL | Overwritten |
| `stats.json` | Most recent statistics | Overwritten |
| `quarantine.jsonl` | Most recent filtered spam | Overwritten |
| `<file>_<ts>.<ext>` | Older versions | Keep |

When you re-scrape a post, the **latest** version overwrites `raw.json`, but older versions remain as `raw_<ts>.json`. Compare them by running `diff` or treating them as snapshots.

## Implementation

Helper module: `scripts/_data_paths.py`

```python
from _data_paths import post_dir, post_paths

url = "https://www.facebook.com/share/p/1AxneTWsfv/"
d = post_dir(url)  # Creates posts/<slug>/ if missing, returns Path
print(d)  # data/posts/share_p_1AxneTWsfv

paths = post_paths(url)
# paths["raw"] → data/posts/share_p_1AxneTWsfv/raw.json
# paths["clean"] → data/posts/share_p_1AxneTWsfv/clean.jsonl
# paths["compact"] → data/posts/share_p_1AxneTWsfv/compact.json
# etc.
```