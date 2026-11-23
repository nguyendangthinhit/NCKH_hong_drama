"""Gom full + summary của analysis_new thành 1 JSON gọn cho dashboard bài viết (dùng chung 2 lĩnh vực)."""

from collections import Counter

import settings  # noqa: F401  (thêm gốc repo vào sys.path)
from analysis_new import config  # noqa: E402

TOP_CLUSTERS = 15
EXAMPLES_PER_LABEL = 5
TEXT_CHARS = 400

DOMAIN_NAMES = {"showbiz": "Showbiz", "education": "Giáo dục"}


def _clip(text) -> str:
    t = str(text or "").strip()
    return t if len(t) <= TEXT_CHARS else t[:TEXT_CHARS].rstrip() + "…"


def _label_counts(comments, field, labels) -> list:
    counts = Counter(c.get(field) for c in comments if not c.get("is_trash"))
    return [{"label": lab, "count": counts.get(lab, 0)} for lab in labels]


def _examples(comments, field, labels) -> dict:
    """Mỗi nhãn: tối đa 5 comment cấp 1 dài nhất (crawler không có like nên lấy độ dài làm độ "đáng đọc")."""
    top = sorted((c for c in comments if not c.get("is_trash") and c.get("level") == 1),
                 key=lambda c: len(str(c.get("text") or "")), reverse=True)
    return {lab: [_clip(c.get("text")) for c in top if c.get(field) == lab][:EXAMPLES_PER_LABEL] for lab in labels}


def _clusters(full) -> list:
    texts = {c.get("id"): c.get("text") for c in full["comments"]}
    ranked = sorted(full["clusters"], key=lambda cl: cl["size"], reverse=True)[:TOP_CLUSTERS]
    return [{"root_id": cl["root_id"], "root_text": _clip(texts.get(cl["root_id"])), "size": cl["size"],
             "summary": cl.get("summary") or "", "labels": cl["thread_stats"].get("labels", {}),
             "controversial": bool(cl["thread_stats"].get("controversial")),
             "toxic_count": cl["thread_stats"].get("toxic_count")} for cl in ranked]


def _toxic(full) -> dict:
    valid = [c for c in full["comments"] if not c.get("is_trash")]
    toxic = [c for c in valid if c.get("toxic")]
    return {"total": len(toxic), "ratio": round(len(toxic) / len(valid), 3) if valid else 0,
            "by_type": [{"type": t, "count": sum(1 for c in toxic if c.get("toxic_type") == t)}
                        for t in config.TOXIC_TYPES]}


def build_view(job: dict, full: dict, summary: dict, post_content: str) -> dict:
    domain = full["domain"]
    cfg = config.domain_cfg(domain)
    comments = full["comments"]
    n_trash = sum(1 for c in comments if c.get("is_trash"))
    view = {
        "job_id": job["id"], "url": job["url"], "max_comments": job["max_comments"],
        "event_name": full.get("name", ""), "post_content": _clip(post_content) if post_content else "",
        "domain": domain, "domain_name": DOMAIN_NAMES.get(domain, domain), "domain_info": job["meta"].get("domain"),
        "label_field": cfg["label_field"],
        "totals": {"comments": len(comments), "top_level": sum(1 for c in comments if c.get("level") == 1),
                   "replies": sum(1 for c in comments if (c.get("level") or 1) > 1),
                   "trash": n_trash, "valid": len(comments) - n_trash,
                   "clusters": len(full["clusters"]),
                   "controversial": sum(1 for cl in full["clusters"] if cl["thread_stats"].get("controversial"))},
        "labels": _label_counts(comments, cfg["label_field"], cfg["labels"]),
        "examples": _examples(comments, cfg["label_field"], cfg["labels"]),
        "clusters": _clusters(full),
        "toxic": _toxic(full) if cfg["toxic"] else None,
        "conclusion": None,
    }
    if domain == "education":
        analysis = summary.get("analysis") or {}
        view["conclusion"] = {**(summary.get("conclusion") or {}),
                              "by_label": {lab: (analysis.get(lab) or {}).get("summary", "") for lab in cfg["labels"]}}
    return view
