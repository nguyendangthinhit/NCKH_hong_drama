---
name: facebook-info-enrichment
description: "Enrich customer profiles from Facebook — profile data, cross-source merge, quality scoring, GDPR/PDPA compliance. Build Customer 360° views with data lineage. v2.1.0 links with the new 09_crawl_profile.py output schema (profile + posts + photos)."
version: 2.1.0
author: Facebook Skills Suite
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [facebook, enrichment, customer-data, crm, gdpr, pdpa, data-lineage, profile-crawl]
    related_skills: [facebook-crawl, facebook-data-clean, facebook-customer-segment]
---

# Facebook Info Enrichment

Enrich customer profiles from Facebook data: combine public profile, post history, group memberships with other sources (CRM, email, phone). Goal: build a single customer view with quality score per field, GDPR/PDPA compliant.

## ⚠️ Privacy & Compliance Note

> **Enrichment data is often PII** (Personal Identifiable Information). Before applying this skill:
>
> 1. **Have lawful basis** (GDPR Article 6) — consent, contract, legitimate interest, etc.
> 2. **Have Data Processing Agreement (DPA)** with data processors
> 3. **Have retention policy** — delete data after purpose ends
> 4. **Have data subject rights workflow** — handle access/delete/rectify requests
> 5. **Vietnam PDPA** (Decree 13/2023) — similar to GDPR, requires clear consent
>
> Cross-border data transfer (VN → US/EU) has separate regulations. Check with legal counsel.

## When to use this skill

Load this skill when you need to:
- Enrich CRM contact (email/phone) with FB profile + activity data
- Merge 2 customer records with different data for the same entity
- Quality-score each field (high/medium/low confidence)
- Build 360° customer view from multiple sources
- Identify duplicate customers in database (matching)

DO NOT load this skill if:
- You only need FB data alone → use `facebook-crawl`
- CRM is already complete, no FB signals needed → skip
- Privacy/compliance not handled → STOP, do compliance first

## Core capabilities

- **Profile enrichment**: from `author_id` crawl, lookup public profile fields (name, bio, location hint, avatar)
- **Activity enrichment**: post count, comment count, last seen, top topics
- **Network enrichment**: pages liked, groups joined (limited)
- **Cross-source merge**: combine with CRM data (email, phone, transaction)
- **Identity resolution**: match 2 records with different data to the same user
- **Quality scoring**: each field has confidence score (high/medium/low)
- **Source attribution**: track which field came from which source (data lineage)
- **Compliance helpers**: consent tracking, retention tagging, deletion handling

## Decision tree: enrichment approach

```
Purpose?
├── Match FB user → CRM contact ──────► Cross-source merge (Step 3)
├── Enrich FB user with public data ───► Profile enrichment (Step 1)
├── Identity resolution (dedup users) ─► Matching algorithm (Step 4)
├── Build customer 360° ───────────────► Combine all + quality score
└── Prepare data for ML/segmentation ─► Quality-score + tag → next skill
```

## Step-by-step workflow

### Step 1 — Profile enrichment (FB → enriched)

For each `author_id`, lookup profile + activity stats.

```python
import json
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class EnrichedProfile:
    canonical_id: str  # primary key, format: "fb:{author_id}"
    sources: list[str] = field(default_factory=list)

    # Identity fields
    fb_id: Optional[str] = None
    fb_name: Optional[str] = None
    fb_username: Optional[str] = None  # if available

    # Public profile fields (limited availability)
    bio: Optional[str] = None
    category: Optional[str] = None  # e.g. "Public figure"
    website: Optional[str] = None

    # Activity (from clean.jsonl)
    post_count: int = 0
    comment_count: int = 0
    reaction_count: int = 0
    share_count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    # Quality scoring
    field_quality: dict = field(default_factory=dict)

    # Compliance
    consent_status: Optional[str] = None  # "given" / "withdrawn" / "unknown"
    retention_until: Optional[str] = None
    data_lineage: dict = field(default_factory=dict)

def enrich_from_fb(author_id: str, clean_posts: list, profile_data: dict = None) -> EnrichedProfile:
    profile = EnrichedProfile(canonical_id=f"fb:{author_id}")
    profile.sources.append("facebook")
    profile.fb_id = author_id

    # Aggregate activity
    author_posts = [p for p in clean_posts if p.get("author") == author_id or p.get("author_id") == author_id]
    profile.comment_count = len(author_posts)
    profile.reaction_count = sum(
        (p.get("reactions", {}) or {}).get("total", 0)
        if isinstance(p.get("reactions"), dict) else 0
        for p in author_posts
    )
    profile.share_count = sum(p.get("share_count", 0) or p.get("shares_count", 0) for p in author_posts)

    if author_posts:
        profile.first_seen = min(p.get("timestamp") or p.get("time") or "9999" for p in author_posts)
        profile.last_seen = max(p.get("timestamp") or p.get("time") or "0000" for p in author_posts)
        profile.fb_name = author_posts[0].get("author") or author_posts[0].get("author_name")

    # Quality scoring per field
    profile.field_quality = {
        "fb_id": "high",  # primary key, always high
        "fb_name": "high" if profile.fb_name else "missing",
        "comment_count": "high",
        "last_seen": "high" if profile.last_seen else "missing",
    }

    # Data lineage
    profile.data_lineage = {
        "fb_id": {"source": "facebook", "fetched_at": "...", "method": "crawl"},
        "comment_count": {"source": "facebook", "computed_from": "clean.jsonl"},
    }

    return profile
```

### Step 2 — Quality scoring for fields

Each field has confidence score:

```python
def score_field_quality(field_name: str, value, sources: list[dict]) -> str:
    """
    Score: high / medium / low / missing

    high: verified from >= 2 sources, recent (< 90 days)
    medium: from 1 trusted source, or verified but old
    low: from 1 untrusted source, or inferred/guessed
    missing: no data
    """
    if value is None or value == "":
        return "missing"

    if len(sources) >= 2:
        # Check recency
        latest = max(s.get("fetched_at", "1900-01-01") for s in sources)
        if is_recent(latest, days=90):
            return "high"
        return "medium"

    if len(sources) == 1:
        source = sources[0]
        if source.get("trust") == "high":
            return "medium"  # 1 trusted source but not cross-verified
        return "low"

    return "low"
```

### Step 3 — Cross-source merge (FB + CRM)

When you have 1 FB record and 1 CRM record (e.g. email match), merge:

```python
def merge_records(fb_record: EnrichedProfile, crm_record: dict, match_key: str) -> EnrichedProfile:
    """
    match_key: field used to match (e.g. "email", "phone", "fb_id")
    Strategy: CRM is source of truth for identity, FB enriches for activity.
    """
    merged = EnrichedProfile(canonical_id=crm_record.get("crm_id", fb_record.canonical_id))
    merged.sources = list(set(fb_record.sources + ["crm"]))

    # Identity: CRM wins (verified)
    if crm_record.get("email"):
        merged.email = crm_record["email"]
        merged.field_quality["email"] = "high"
        merged.data_lineage["email"] = {"source": "crm", "verified": True}

    if crm_record.get("phone"):
        merged.phone = crm_record["phone"]
        merged.field_quality["phone"] = "high"
        merged.data_lineage["phone"] = {"source": "crm", "verified": True}

    # FB ID: cross-link
    if fb_record.fb_id:
        merged.fb_id = fb_record.fb_id
        merged.field_quality["fb_id"] = "high"
        merged.data_lineage["fb_id"] = {"source": "facebook"}

    # Name conflict: CRM wins, FB name = secondary
    merged.crm_name = crm_record.get("name")
    merged.fb_name_alt = fb_record.fb_name

    # Activity: from FB
    merged.comment_count = fb_record.comment_count
    merged.reaction_count = fb_record.reaction_count
    merged.last_seen_fb = fb_record.last_seen

    return merged
```

### Step 4 — Identity resolution (dedup matching)

When database may have duplicate customers (same person, 2 records):

```python
from jellyfish import jaro_winkler_similarity
from phonenumbers import PhoneNumberMatcher
import re

def match_score(rec_a: dict, rec_b: dict) -> tuple[float, list[str]]:
    """
    Returns (score 0-1, list of matching fields).
    """
    matches = []
    score = 0.0

    # 1. Exact email match
    if rec_a.get("email") and rec_a["email"].lower() == rec_b.get("email", "").lower():
        matches.append("email_exact")
        score += 0.5

    # 2. Phone match (normalized)
    phone_a = normalize_phone(rec_a.get("phone"))
    phone_b = normalize_phone(rec_b.get("phone"))
    if phone_a and phone_a == phone_b:
        matches.append("phone_exact")
        score += 0.5

    # 3. FB ID match
    if rec_a.get("fb_id") and rec_a["fb_id"] == rec_b.get("fb_id"):
        matches.append("fb_id_exact")
        score += 0.7

    # 4. Name fuzzy match (Vietnamese names: need custom logic)
    name_a = normalize_vn_name(rec_a.get("name"))
    name_b = normalize_vn_name(rec_b.get("name"))
    if name_a and name_b:
        sim = jaro_winkler_similarity(name_a, name_b)
        if sim >= 0.9:
            matches.append(f"name_fuzzy={sim:.2f}")
            score += 0.2 * sim

    return min(score, 1.0), matches

def normalize_vn_name(name: str) -> str:
    """Lowercase, remove diacritics for fuzzy matching only."""
    import unicodedata
    if not name:
        return ""
    # NFD then strip diacritics
    nfd = unicodedata.normalize("NFD", name)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

def normalize_phone(phone: str) -> str:
    """Convert +84/84/0xxx → 0xxx standard."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits

# Block matching — find duplicate pairs
def find_duplicates(records: list[dict], threshold: float = 0.5) -> list[tuple]:
    duplicates = []
    for i, rec_a in enumerate(records):
        for rec_b in records[i+1:]:
            score, matches = match_score(rec_a, rec_b)
            if score >= threshold:
                duplicates.append((rec_a["_id"], rec_b["_id"], score, matches))
    return duplicates
```

### Step 5 — Compliance tagging

Every enriched record must have compliance metadata:

```python
from datetime import datetime, timedelta

RETENTION_DAYS = {
    "high_intent": 365,
    "low_intent": 90,
    "no_consent": 30,  # delete early if no consent
}

def tag_compliance(profile: EnrichedProfile, consent: dict = None) -> EnrichedProfile:
    # Consent status
    profile.consent_status = consent.get("status", "unknown") if consent else "unknown"
    profile.consent_timestamp = consent.get("timestamp") if consent else None
    profile.consent_source = consent.get("source") if consent else None

    # Retention
    tier = "no_consent"
    if profile.field_quality.get("email") == "high" and profile.comment_count >= 5:
        tier = "high_intent"
    elif profile.comment_count >= 1:
        tier = "low_intent"

    retention_days = RETENTION_DAYS[tier]
    profile.retention_until = (
        datetime.utcnow() + timedelta(days=retention_days)
    ).isoformat()

    # PII flags (for downstream filtering)
    profile.has_pii = bool(profile.email or profile.phone)

    return profile

def should_delete(profile: EnrichedProfile) -> bool:
    """Check retention expiry + consent withdrawal."""
    if profile.consent_status == "withdrawn":
        return True
    if profile.retention_until:
        if datetime.fromisoformat(profile.retention_until) < datetime.utcnow():
            return True
    return False
```

### Step 6 — Output schema (Customer 360°)

```json
{
  "canonical_id": "crm:contact_12345",
  "sources": ["crm", "facebook"],

  "identity": {
    "crm_id": "contact_12345",
    "fb_id": "100012345678901",
    "email": "user@example.com",
    "email_quality": "high",
    "phone": "+84912345678",
    "phone_quality": "high",
    "crm_name": "Nguyen Van A",
    "fb_name_alt": "Nguyen Van A"
  },

  "facebook_activity": {
    "comment_count": 23,
    "reaction_count": 156,
    "share_count": 4,
    "first_seen": "2025-09-15T...",
    "last_seen": "2026-07-05T...",
    "top_topics": ["điện thoại", "phụ kiện", "review"]
  },

  "quality_summary": {
    "overall": "high",
    "high_confidence_fields": ["email", "phone", "fb_id"],
    "medium_confidence_fields": ["last_seen"],
    "low_confidence_fields": ["bio"],
    "missing_fields": ["website", "location"]
  },

  "data_lineage": {
    "email": {"source": "crm", "verified": true, "fetched_at": "..."},
    "fb_id": {"source": "facebook", "method": "crawl"},
    "comment_count": {"source": "facebook", "computed_from": "clean.jsonl"}
  },

  "compliance": {
    "consent_status": "given",
    "consent_timestamp": "2025-08-01T...",
    "consent_source": "web_form",
    "retention_until": "2026-08-01T...",
    "has_pii": true
  },

  "computed_at": "2026-07-07T..."
}
```

## Anti-patterns

- ❌ **Enrich without consent** — violates GDPR/PDPA, can be fined heavily
- ❌ **Store PII unencrypted** — need encryption at-rest and in-transit
- ❌ **Overwrite CRM data with FB data** — CRM is usually source of truth for identity
- ❌ **Match only on name** — names are easily duplicated (millions of "Nguyen Van A"). Need stronger match keys (email/phone/fb_id)
- ❌ **Generic quality score** — each field has its own context, don't score uniformly
- ❌ **Indefinite retention** — must have expiry. GDPR has right to erasure
- ❌ **Cross-border transfer without check** — VN → US needs Standard Contractual Clauses (SCC)
- ❌ **No access log** — need audit trail for every PII read
- ❌ **Skip data lineage** — don't know which field from where → can't debug

## Pitfalls

1. **Vietnamese name normalization caution** — "Nguyễn" vs "Nguyen" — when stripping diacritics to match, **don't use normalized name as canonical** (loses info). Only use for compare
2. **VN phone format** — `+84`, `84`, `0xxx` all valid. Normalize to `0xxx` to compare
3. **Email with dot variations** — `user.name@example.com` vs `username@example.com` (Gmail). May need to normalize
4. **FB profile name may be fake** — "Nguyen Van A" on FB may be nickname. Don't match strict with CRM name
5. **Identity resolution expensive** — O(N²) matching doesn't scale. With > 10K records, use blocking first (group by email domain, phone prefix, etc.)
6. **Multiple FB accounts / 1 person** — 1 person can have personal FB + business FB. Match 1 CRM contact → multiple FB IDs is normal
7. **Deactivated FB users** — `fb_id` can't be accessed anymore. Enrich fails gracefully
8. **Consent withdrawal must cascade** — if user withdraws consent, delete derived data (segments, scores)
9. **Field conflicts on merge** — when CRM and FB have different values for same field, define tie-breaker rule upfront (usually CRM > FB > inferred)
10. **Quality score without lineage** — quality is meaningless if you can't trace why a field is low/high

## Verification commands

```bash
# Schema validity
jq -r '.canonical_id' enriched.jsonl | sort | uniq -d | wc -l  # should be 0

# Quality distribution
jq -r '.quality_summary.overall' enriched.jsonl | sort | uniq -c

# PII count
jq -r 'select(.compliance.has_pii == true) | .canonical_id' enriched.jsonl | wc -l

# Consent status
jq -r '.compliance.consent_status' enriched.jsonl | sort | uniq -c

# Retention check (near expiry)
jq -r 'select(.compliance.retention_until < "2026-08-01") | .canonical_id' enriched.jsonl | wc -l

# Data lineage completeness
jq -r '.data_lineage | keys[]' enriched.jsonl | sort | uniq -c
```

## Output files

```
enriched.jsonl                  # each customer 1 record, full schema
enriched_summary.json           # distribution stats
duplicates.csv                  # duplicate pairs for manual review
expiring_soon.jsonl             # records near retention
consent_withdrawn.jsonl         # records needing deletion (GDPR request)
```

## Reference

- GDPR lawful basis: https://gdpr-info.eu/art-6-gdpr/
- Vietnam PDPA (Decree 13/2023): https://vanban.chinhphu.vn/?pageid=27160&docid=204991
- `jellyfish` (string similarity): https://github.com/jamesturk/jellyfish
- `phonenumbers` (Google lib): https://github.com/daviddrysdale/python-phonenumbers
- Customer 360 best practices: https://www.salesforce.com/resources/customer-360/