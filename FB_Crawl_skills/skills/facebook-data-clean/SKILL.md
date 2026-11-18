---
name: facebook-data-clean
description: "Clean Facebook data after crawl — deduplication, Unicode normalization, spam/bot filtering, PII redaction, schema validation. Produces clean JSONL + quarantine + stats."
version: 2.0.0
author: Facebook Skills Suite
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [facebook, data-cleaning, etl, deduplication, pii-redaction, normalization]
    related_skills: [facebook-crawl, facebook-info-enrichment]
---

# Facebook Data Clean

Pipeline for cleaning raw Facebook data after crawl. Transforms raw JSONL from `facebook-crawl` (or `scripts/05_auto_scrape_cdp.py`) into clean datasets ready for analytics, segmentation, or training.

Focus areas: **deduplication**, **text normalization**, **spam/bot filtering**, **PII redaction**, **schema validation**.

## When to use this skill

Load this skill when you need to:
- Dedupe posts/comments crawled from multiple sources (post_id collision + near-duplicate content)
- Normalize text FB (emoji, ZWJ, RTL marks, Vietnamese diacritics)
- Filter spam posts / bot comments before analytics
- Redact PII (Vietnam phone, email, addresses) before sharing data
- Validate schema — ensure each record has required fields
- Separate good data from broken data (quarantine pattern)

DO NOT load this skill if:
- You haven't crawled data yet → use `facebook-crawl` first
- You only need a simple 1-2 rule filter → write inline, don't need this skill
- You need ML-based content moderation → use a separate model (OpenAI moderation, Perspective API)

## Core capabilities

- **Exact dedup** by `post_id` / `comment_id` (primary key)
- **Near-duplicate dedup** via MinHash + LSH for similar content (e.g. cross-posted content)
- **Text normalization**: Unicode NFC, lowercase with guard, emoji handling, Vietnamese diacritics
- **Spam/bot detection**: regex patterns, emoji density, link ratio, account age signals
- **PII redaction**: regex for Vietnamese phone, email, URL tracking
- **Schema validation**: Pydantic models, bad records → quarantine
- **Language detection**: identify primary language (vi, en, mixed)
- **Output**: `clean.jsonl` + `quarantine.jsonl` + `stats.json`

## Decision tree: cleaning order

```
Raw crawl data
    │
    ▼
1. Schema validation ────► Bad records → quarantine
    │
    ▼
2. Exact dedup (post_id) ────► Keep first occurrence
    │
    ▼
3. Text normalization (NFC, trim, lowercase opt)
    │
    ▼
4. Language detection + filter (keep vi + en, drop others if not needed)
    │
    ▼
5. Spam/bot filtering ────► Spam → quarantine
    │
    ▼
6. PII redaction (mask phone, email)
    │
    ▼
7. Near-duplicate dedup (MinHash LSH)
    │
    ▼
8. Stats report
    │
    ▼
clean.jsonl + quarantine.jsonl + stats.json
```

## Step-by-step workflow

### Step 1 — Schema validation

Use Pydantic to validate each record. Validation failure → quarantine, never drop silently.

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FBPost(BaseModel):
    post_id: str = Field(..., min_length=1)
    source: str = Field(..., pattern="^(graph_api|apify|playwright|unofficial)$")
    page_id: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    text: Optional[str] = None
    timestamp: datetime
    url: Optional[str] = None
    media_urls: list[str] = []
    reactions: dict = {}
    comments_count: int = 0
    shares_count: int = 0
    raw: dict = {}

def validate_post(raw: dict) -> tuple[FBPost | None, str | None]:
    try:
        return FBPost(**raw), None
    except Exception as e:
        return None, str(e)

class FBComment(BaseModel):
    """Schema for deep-extracted comments (with type=comment|reply)."""
    type: str = Field(..., pattern="^(comment|reply)$")
    author: str = Field(..., min_length=1)
    text: str = Field(..., min_length=2)
    time: Optional[str] = None
    raw: dict = {}
```

### Step 2 — Exact dedup

```python
import json
from collections import defaultdict

seen_ids = set()
deduped = []
with open("posts.jsonl") as f:
    for line in f:
        post = json.loads(line)
        pid = post.get("post_id") or post.get("comment_id")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        deduped.append(post)
```

### Step 3 — Text normalization

```python
import unicodedata
import re

def normalize_text(text: str) -> str:
    """Unicode NFC + strip control chars + collapse whitespace + strip ZW chars."""
    if not text:
        return ""
    # 1. Unicode NFC (composed) — critical for Vietnamese diacritics
    text = unicodedata.normalize("NFC", text)
    # 2. Strip control chars (keep emoji + newlines)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    # 3. Collapse whitespace runs
    text = re.sub(r"\s+", " ", text).strip()
    # 4. Strip zero-width chars (ZWS, ZWJ excess, RTL marks)
    text = re.sub(r"[​-‏‪-‮⁠]", "", text)
    return text
```

**Important**: keep emoji ZWJ sequences (e.g. 👨‍👩‍👧 = 👨 + ZWJ + 👩 + ZWJ + 👧) — they carry meaning. Only strip standalone ZWS (U+200B), ZWNJ (U+200C), ZWSP (U+200B).

### Step 4 — Language detection

```python
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # deterministic

def detect_lang(text: str) -> str:
    try:
        return detect(text[:500])  # sample first 500 chars
    except:
        return "unknown"
```

Filter: keep `vi` and `en`, drop `zh`, `ja`, etc. if not needed.

### Step 5 — Spam/bot filtering

Combine heuristics → flag spam:

```python
SPAM_PATTERNS = [
    r"\b(?:click|tap|nhấn)\s+(?:here|ngay|vào đây)\b",
    r"http[s]?://(?:bit\.ly|tinyurl\.com|goo\.gl)/\S+",  # shortened links
    r"\$\d+[Kk]?\s*(?:/month|per month|tháng)",  # money bait
    r"\bDM\s+me\s+for",  # DM bait
    r"nhắn tin\s+cho\s+tôi",
]

def is_spam(record: dict) -> tuple[bool, list[str]]:
    text = record.get("text", "") or ""
    reasons = []

    # 1. Pattern match
    for pat in SPAM_PATTERNS:
        if re.search(pat, text, re.I):
            reasons.append(f"pattern:{pat[:30]}")

    # 2. Link density
    urls = re.findall(r"http[s]?://\S+", text)
    if len(urls) >= 3:
        reasons.append(f"link_count={len(urls)}")

    # 3. Emoji density
    emoji_count = sum(1 for c in text if ord(c) > 0x1F000)
    if len(text) > 0 and emoji_count / len(text) > 0.3:
        reasons.append(f"emoji_density={emoji_count/len(text):.2f}")

    # 4. Uppercase ratio
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.6:
        reasons.append("all_caps")

    # 5. Account age signal (if available)
    account_age_days = post.get("raw", {}).get("account_age_days")
    if account_age_days is not None and account_age_days < 30:
        reasons.append(f"young_account={account_age_days}d")

    return (len(reasons) > 0, reasons)
```

### Step 6 — PII redaction

```python
# Vietnamese phone numbers (10 digits, common prefixes)
PHONE_VN = re.compile(r"\b(0|\+84)(3[2-9]|5[6|8|9]|7[0|6-9]|8[1-9]|9[0-9])\d{7}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

def redact_pii(text: str) -> tuple[str, dict]:
    counts = {"phone": 0, "email": 0}

    def phone_repl(m):
        counts["phone"] += 1
        return "[REDACTED_PHONE]"

    def email_repl(m):
        counts["email"] += 1
        return "[REDACTED_EMAIL]"

    text = PHONE_VN.sub(phone_repl, text)
    text = EMAIL.sub(email_repl, text)
    return text, counts
```

**Do NOT redact** if user explicitly needs raw PII (e.g. legal CRM use case). Default is redact — opt-out requires explicit config.

### Step 7 — Near-duplicate dedup

MinHash + LSH for similar content (cross-posted):

```python
from datasketch import MinHash, MinHashLSH

def build_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    # 3-gram shingles (characters)
    shingles = {text[i:i+3] for i in range(len(text) - 2)}
    for s in shingles:
        m.update(s.encode("utf-8"))
    return m

# Build LSH index
lsh = MinHashLSH(threshold=0.7, num_perm=128)
minhashes = {}

for post in posts:
    text = post.get("text", "") or ""
    if len(text) < 50:
        continue
    mh = build_minhash(text)
    minhashes[post["post_id"]] = mh
    lsh.insert(post["post_id"], mh)

# Query duplicates
duplicates = set()
for pid, mh in minhashes.items():
    if pid in duplicates:
        continue
    similar = lsh.query(mh)
    similar.remove(pid)  # remove self
    duplicates.update(similar)
```

Keep the first `post_id` in each near-dup cluster; quarantine the rest.

### Step 8 — Stats report

```python
import json
from collections import Counter

stats = {
    "total_input": len(raw_posts),
    "valid_schema": len(validated),
    "exact_dup_removed": dup_count,
    "near_dup_removed": near_dup_count,
    "spam_filtered": spam_count,
    "pii_redactions": pii_totals,
    "language_distribution": dict(Counter(langs).most_common(10)),
    "date_range": [min(ts), max(ts)],
    "total_output_clean": len(clean_posts),
    "total_output_quarantine": len(quarantine_posts),
}

with open("stats.json", "w") as f:
    json.dump(stats, f, indent=2, ensure_ascii=False)
```

## Anti-patterns

- ❌ **Drop bad records silently** — always write to `quarantine.jsonl` with reason
- ❌ **Lowercase everything** — loses proper nouns, brand names, Vietnamese tone marks
- ❌ **Strip all emoji** — loses semantic + sentiment signals. Filter by density, not blanket strip
- ❌ **Normalize to Unicode NFD for Vietnamese** — NFD splits diacritics → bad dedup. Use **NFC**
- ❌ **Redact PII before schema validation** — hard to debug. Validate first, redact last
- ❌ **Generic regex for international phones** — VN, US patterns differ. Tune per region
- ❌ **Don't preserve `raw` fields** — when debugging schema drift, need `raw` available
- ❌ **Dedup on lowercased text** — loses case-sensitive proper nouns → false positives
- ❌ **Skip quarantine for spam** — quarantine enables later re-analysis with new rules

## Pitfalls

1. **Vietnamese diacritics** — "Tiếng Việt" vs "Tieng Viet" are 2 different strings. Can have both in data. Decide: keep as-is (recommended) or add variant matching
2. **Emoji + ZWJ** — 👨‍👩‍👧 is 1 emoji sequence, not 3. Count emoji sequences, not codepoints
3. **Mixed language** — Vietnamese + English mix is common. `langdetect` may return `en` for "Cảm ơn thanks" — accept, don't over-engineer
4. **PII in media URLs** — sometimes phone/email in `media_urls` filenames. May need to redact URLs too
5. **Near-dup threshold** — 0.7 may be too high or low depending on corpus. Tune on sample first
6. **Spam patterns by language** — Vietnamese patterns differ from English. Need 2 sets running in parallel
7. **Quote replies / reposts** — when user shares a post with their own comment, original + new comment can trigger near-dup false positive
8. **Emoji-only comments** — text can be just emoji (e.g. "👍"). Loosen `text.length >= 2` if needed
9. **Nested reply dup** — in deep comment extraction, same reply can render multiple times in nested threads. Dedupe by `author + text[:80]`

## Verification commands

```bash
# Schema validity
jq -r 'select(.post_id == null) | .' posts.jsonl | wc -l  # should be 0 (moved to quarantine)

# Dedup check
jq -r '.post_id' clean.jsonl | sort | uniq -d | wc -l  # should be 0

# Language distribution
jq -r '.language // empty' clean.jsonl | sort | uniq -c | sort -rn

# Spam check
jq -r 'select(.spam_reasons != null) | .post_id' clean.jsonl | wc -l  # should be 0

# PII leak check (regex sweep on clean.jsonl)
grep -E '\b0[3-9][0-9]{8}\b' clean.jsonl | wc -l  # should be 0

# Stats summary
cat stats.json | jq .
```

## Output schema

### clean.jsonl
Each record gets extra fields:
```json
{
  "post_id": "...",
  "text": "...",  // normalized
  "text_hash": "sha256...",  // for exact re-dedup
  "language": "vi",
  "spam_reasons": [],
  "pii_redactions": {"phone": 0, "email": 0},
  "cleaned_at": "2026-07-07T...",
  // ... all original fields preserved
}
```

### quarantine.jsonl
```json
{
  "reason": "schema_invalid" | "exact_dup" | "near_dup" | "spam" | "other",
  "details": "validation error message / spam_reasons / dup_id",
  "original": { /* raw record */ }
}
```

### stats.json
See step 8 above.

## Reference

- Pydantic: https://docs.pydantic.dev/
- `datasketch` MinHash: https://ekzhu.github.io/datasketch/minhash.html
- `langdetect`: https://pypi.org/project/langdetect/
- Unicode normalization: https://docs.python.org/3/library/unicodedata.html
- Vietnamese phone prefixes: https://vi.wikipedia.org/wiki/M%C3%A3_Qu%E1%BB%91c_%C4%91i%E1%BB%87n_tho%E1%BA%A1i_Vi%E1%BB%87t_Nam