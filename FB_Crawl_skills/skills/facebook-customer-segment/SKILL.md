---
name: facebook-customer-segment
description: "Customer segmentation from Facebook engagement data — RFM scoring, behavioral segments, lead scoring, lookalike clustering. Input: clean posts/comments from facebook-data-clean."
version: 2.0.0
author: Facebook Skills Suite
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [facebook, segmentation, rfm, lead-scoring, clustering, crm]
    related_skills: [facebook-data-clean, facebook-info-enrichment]
---

# Facebook Customer Segment

Segment and score customers from Facebook engagement data. Transform clean posts/comments into actionable segments (VIP, hot lead, churn risk, etc.) for CRM, ad targeting, or sales prioritization.

## When to use this skill

Load this skill when you need to:
- Group customers based on Facebook engagement (comments, reactions, shares)
- Score leads from signals on brand posts
- Find "lookalike" segments — groups resembling the best customers
- Predict churn risk (customer going cold)
- Enrich CRM (HubSpot, Salesforce) with segments from social signals

DO NOT load this skill if:
- You don't have clean data yet → run `facebook-data-clean` first
- You need segmentation based on transaction history → use data warehouse SQL, not FB context
- You need real-time segmentation (< 1 second) → need separate streaming pipeline

## Core capabilities

- **RFM scoring**: Recency (recent engagement), Frequency (post/comment count), Monetary (purchase signals if any)
- **Behavioral segments**: Engager, Lurker, Advocate, Detractor, Inactive
- **Demographic segmentation**: age range (if available), gender hint (name, avatar), location (if available)
- **Psychographic signals**: interests from liked pages/groups (limited), sentiment from comments
- **Lead scoring**: composite score from multiple signals
- **Lookalike clustering**: find groups resembling the best segment via embedding similarity
- **Output**: customer_id, segments[], scores, rationale

## Decision tree: choosing segmentation approach

```
Purpose?
├── Marketing / Ad targeting ─────► Behavioral segments + Lookalike clusters
├── Sales prioritization ──────────► Lead scoring (composite score)
├── Retention / Churn ─────────────► RFM (especially Recency)
├── Customer support routing ──────► Sentiment + activity segments
└── Product feedback ──────────────► Topic clusters (NMF/LDA) + sentiment
```

## Step-by-step workflow

### Step 1 — Aggregate per-author stats

From `clean.jsonl`, aggregate each author (user) into 1 row:

```python
import json
from collections import defaultdict
from datetime import datetime

author_stats = defaultdict(lambda: {
    "post_count": 0,
    "comment_count": 0,
    "reaction_count": 0,
    "share_count": 0,
    "first_seen": None,
    "last_seen": None,
    "pages_interacted": set(),
    "total_text_length": 0,
    "avg_text_length": 0,
})

with open("clean.jsonl") as f:
    for line in f:
        post = json.loads(line)
        author = post.get("author") or post.get("author_id")
        if not author:
            continue

        stats = author_stats[author]
        # Handle both comment-format (type=comment|reply) and post-format
        if post.get("type") in ("comment", "reply"):
            stats["comment_count"] += 1
        else:
            stats["post_count"] += 1

        stats["reaction_count"] += post.get("reactions", {}).get("total", 0) if isinstance(post.get("reactions"), dict) else 0
        stats["share_count"] += post.get("shares_count", 0)

        ts_str = post.get("timestamp") or post.get("time")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if not stats["first_seen"] or ts < stats["first_seen"]:
                    stats["first_seen"] = ts
                if not stats["last_seen"] or ts > stats["last_seen"]:
                    stats["last_seen"] = ts
            except (ValueError, AttributeError):
                pass

        if post.get("page_id"):
            stats["pages_interacted"].add(post["page_id"])

        text_len = len(post.get("text") or "")
        stats["total_text_length"] += text_len

# Finalize
for author, stats in author_stats.items():
    if stats["comment_count"] > 0:
        stats["avg_text_length"] = stats["total_text_length"] / stats["comment_count"]
    stats["pages_interacted"] = list(stats["pages_interacted"])
```

### Step 2 — RFM scoring

**Reference date**: pick a date (usually analysis date).

```python
from datetime import datetime, timezone
import numpy as np

REFERENCE_DATE = datetime(2026, 7, 7, tzinfo=timezone.utc)

def calculate_rfm(author_stats: dict, ref_date: datetime) -> dict:
    rfm = {}
    for author, stats in author_stats.items():
        last_seen = stats.get("last_seen")
        if last_seen:
            recency_days = (ref_date - last_seen).days
        else:
            recency_days = 999

        frequency = stats["comment_count"] + stats["reaction_count"] + stats["share_count"]

        # Monetary — from FB context, "monetary" = proxy signals
        # (e.g. mentions "buy", "order", price inquiries)
        monetary_proxy = stats.get("purchase_intent_score", 0)  # see step 4

        # Score 1-5 for each dimension (quintile)
        rfm[author] = {
            "R": score_recency(recency_days),  # low = good
            "F": score_frequency(frequency),  # high = good
            "M": score_monetary(monetary_proxy),  # high = good
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary": monetary_proxy,
        }
    return rfm

def score_recency(days: int) -> int:
    if days <= 7: return 5
    if days <= 30: return 4
    if days <= 90: return 3
    if days <= 180: return 2
    return 1

def score_frequency(freq: int) -> int:
    if freq >= 50: return 5
    if freq >= 20: return 4
    if freq >= 10: return 3
    if freq >= 3: return 2
    return 1

def score_monetary(score: float) -> int:
    if score >= 0.8: return 5
    if score >= 0.6: return 4
    if score >= 0.4: return 3
    if score >= 0.2: return 2
    return 1
```

**RFM segments** (by R+F+M sum, range 3-15):

| RFM sum | Segment |
|---------|---------|
| 13-15 | **Champions** — recent engagement, frequent, high intent |
| 10-12 | **Loyal Customers** — regular, stable engagement |
| 7-9 | **Potential Loyalists** — recent but low frequency |
| 5-6 | **At Risk** — used to engage, going cold |
| 3-4 | **Hibernating** — very low/inactive |

### Step 3 — Behavioral segments

Based on activity pattern:

```python
def behavioral_segment(stats: dict, recency_days: int) -> str:
    cc = stats["comment_count"]
    rc = stats["reaction_count"]
    sc = stats["share_count"]
    avg_text = stats["avg_text_length"]

    if sc >= 5 and recency_days <= 30:
        return "Advocate"  # share a lot + active

    if cc >= 10 and avg_text >= 50:
        return "Engager"  # long comments, frequent

    if cc >= 5 and avg_text < 20:
        return "Reactor"  # only react + short

    if rc >= 10 and cc == 0:
        return "Lurker"  # like but never comment

    if any(neg in (stats.get("sentiment_summary", {}) or {})
           for neg in ["negative"]):
        return "Detractor"

    if recency_days > 180:
        return "Inactive"

    return "Casual"
```

### Step 4 — Lead scoring (composite)

Lead score = weighted sum of signals:

```python
LEAD_SCORE_WEIGHTS = {
    "purchase_intent_keywords": 0.30,  # text contains "buy", "price", "order"
    "comment_quality": 0.20,           # long substantive comments
    "frequency": 0.15,                  # frequent engagement
    "recency": 0.15,                    # recent engagement
    "share_count": 0.10,                # share = advocacy
    "demographic_match": 0.10,          # match ICP
}

PURCHASE_INTENT_PATTERNS = [
    r"\b(buy|mua|mình mua|tôi mua|order|đặt hàng)\b",
    r"\b(price|giá|bao nhiêu|bao nhiêu tiền|cost)\b",
    r"\b(in stock|stock|còn hàng|hết hàng|out of stock)\b",
    r"\b(shop|boutique|cửa hàng)\s+(ở đâu|tại|where)\b",
    r"\b(ship|giao hàng|delivery|vận chuyển)\b",
    r"\b(size|kích thước|color|màu)\b",
]

def calculate_lead_score(stats: dict, rfm: dict, demographics: dict = None) -> dict:
    scores = {}

    # 1. Purchase intent (0-1)
    text_sample = " ".join(stats.get("recent_texts", []))
    matches = sum(1 for pat in PURCHASE_INTENT_PATTERNS
                 if re.search(pat, text_sample, re.I))
    scores["purchase_intent"] = min(matches / 3, 1.0)

    # 2. Comment quality (0-1)
    avg_len = stats["avg_text_length"]
    scores["comment_quality"] = min(avg_len / 100, 1.0)

    # 3. Frequency (0-1)
    scores["frequency"] = min(rfm["F"] / 5, 1.0)

    # 4. Recency (0-1)
    scores["recency"] = min(rfm["R"] / 5, 1.0)

    # 5. Share count (0-1)
    scores["share_count"] = min(stats["share_count"] / 10, 1.0)

    # 6. Demographic match (0-1, requires external data)
    scores["demographic_match"] = demographics.get("match_score", 0.5) if demographics else 0.5

    # Weighted sum
    lead_score = sum(scores[k] * LEAD_SCORE_WEIGHTS[k] for k in scores)

    # Tier
    if lead_score >= 0.7: tier = "Hot"
    elif lead_score >= 0.5: tier = "Warm"
    elif lead_score >= 0.3: tier = "Cold"
    else: tier = "Unqualified"

    return {
        "lead_score": round(lead_score, 3),
        "tier": tier,
        "component_scores": scores,
    }
```

### Step 5 — Lookalike clustering (optional, advanced)

Use embedding from author activity (post text + comments) → cluster → find centroid of "best" segment.

```python
import numpy as np
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")  # supports Vietnamese

# Embed recent texts per author
author_texts = {}
for author, stats in author_stats.items():
    texts = stats.get("recent_texts", [])[:10]  # max 10 recent
    if texts:
        author_texts[author] = model.encode(texts).mean(axis=0)

# Stack to matrix
authors = list(author_texts.keys())
embeddings = np.stack([author_texts[a] for a in authors])

# Cluster
kmeans = KMeans(n_clusters=10, random_state=42)
clusters = kmeans.fit_predict(embeddings)

# Find cluster with highest avg lead score
cluster_scores = defaultdict(list)
for author, cluster_id in zip(authors, clusters):
    if author in lead_scores:
        cluster_scores[cluster_id].append(lead_scores[author]["lead_score"])

best_cluster = max(cluster_scores, key=lambda c: np.mean(cluster_scores[c]))

# Tag authors in best_cluster = "lookalike of high-value"
for author, cluster_id in zip(authors, clusters):
    if cluster_id == best_cluster:
        segments[author]["lookalike"] = "high_value_lookalike"
```

### Step 6 — Output schema

```json
{
  "author_id": "...",
  "author_name": "...",
  "rfm": {
    "R": 5,
    "F": 3,
    "M": 4,
    "recency_days": 3,
    "frequency": 23,
    "monetary": 0.7
  },
  "segments": [
    "Engager",
    "Potential Loyalist",
    "Warm"
  ],
  "lead_score": 0.68,
  "lead_tier": "Warm",
  "lead_components": {
    "purchase_intent": 0.67,
    "comment_quality": 0.45,
    "frequency": 0.6,
    "recency": 1.0,
    "share_count": 0.2,
    "demographic_match": 0.5
  },
  "lookalike": null,
  "rationale": "Engaged 23 times in 90 days, avg 45 chars per comment, mentioned 'price' and 'buy' 2 times → warm lead with purchase intent.",
  "computed_at": "2026-07-07T..."
}
```

## Anti-patterns

- ❌ **Random score thresholds** — no business meaning. Calibrate with actual conversion data
- ❌ **Too many segments (> 20)** — hard to action. Keep 5-10 main segments
- ❌ **Monetary score from FB context is "fake"** — no actual transaction. Call it "monetary_proxy" or "purchase_intent"
- ❌ **Lead score without rationale** — sales team doesn't know why lead is "hot" → wrong action
- ❌ **recency_days = 0 for every post same day** — use exact timestamp
- ❌ **Clustering with non-interpretable cluster_id** — each cluster needs keyword/label
- ❌ **Don't refresh score** — engagement data stale after 7-30 days. Refresh periodically
- ❌ **Demographic from name/avatar guess** — high error rate, don't use for big decisions

## Pitfalls

1. **Sample bias**: only have data of users who *engage* → missing lurkers (silent majority). Segments will bias toward active users
2. **Survivorship bias**: deleted posts / deactivated users → no data → undercount
3. **Cold start**: new user without much data → lead score unreliable. Need minimum threshold (e.g. > 5 interactions)
4. **Comment quality ≠ purchase intent**: long comment may be complaint, not advocate. Combine with sentiment
5. **Bot/spam slipped through clean step** — if bot comments exist, RFM will skew. Re-check with `facebook-data-clean` heuristics
6. **Cross-page**: user engaging on multiple unrelated pages may not be relevant (competing brands). Consider scope per page
7. **RFM date range too narrow**: 30 days only sees seasonal spikes. Use 90-180 days for better picture
8. **Lookalike clustering bias**: if "best" cluster has only 5 users → overfitting. Need minimum cluster size
9. **Reply nesting effect**: in deep comment extraction, users replying to themselves can inflate comment_count. Filter self-replies if needed

## Verification commands

```bash
# Output sanity
jq -r '.author_id' segments.jsonl | sort | uniq -d | wc -l  # should be 0

# Segment distribution
jq -r '.segments[]' segments.jsonl | sort | uniq -c | sort -rn

# Lead score distribution
jq -r '.lead_score' segments.jsonl | awk '{ if ($1 >= 0.7) h++; else if ($1 >= 0.5) w++; else if ($1 >= 0.3) c++; else u++ } END { print "Hot:", h, "Warm:", w, "Cold:", c, "Unqualified:", u }'

# RFM tier distribution
jq -r '(.rfm.R + .rfm.F + .rfm.M)' segments.jsonl | awk '{ if ($1 >= 13) c++; else if ($1 >= 10) l++; else if ($1 >= 7) p++; else if ($1 >= 5) a++; else h++ } END { print "Champions:", c, "Loyal:", l, "Potential:", p, "At Risk:", a, "Hibernating:", h }'
```

## Output files

```
segments.jsonl         # each author 1 line, full schema in step 6
segments_summary.json  # distribution stats, tier counts
hot_leads.jsonl        # subset lead_score >= 0.7, for sales team
rfm_matrix.csv         # R+F+M grid for marketing team visualization
```

## Reference

- RFM methodology: https://en.wikipedia.org/wiki/RFM_(market_research)
- Lead scoring best practices: https://blog.hubspot.com/sales/lead-scoring
- `sentence-transformers` multilingual: https://www.sbert.net/docs/pretrained_models.html
- KMeans clustering: https://scikit-learn.org/stable/modules/clustering.html