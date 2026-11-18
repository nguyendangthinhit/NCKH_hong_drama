"""Dựng file full (từng comment có nhãn + thông tin cụm) và summary theo sự kiện.

Summary giữ các khoá mà analysis/single/analyze_insights.py đang đọc:
  showbiz:   total_comments, emotion_stats, toxic_stats, top_comments, controversial_threads
  education: comment_counts, analysis{stance:{count,percent,summary,examples}}, conclusion
"""

from collections import Counter

from analysis_new import config
from analysis_new.request_planner import trash_label
from analysis_new.thread_loader import to_int


def _thread_stats(domain, nodes, labels) -> dict:
    cfg = config.domain_cfg(domain)
    valid = [labels[n["id"]] for n in nodes if not labels[n["id"]]["is_trash"]]
    counts = Counter(x[cfg["label_field"]] for x in valid if x.get(cfg["label_field"]))
    total = len(valid)
    top = max(counts.values()) if counts else 0
    stats = {"total": total, "labels": dict(counts),
             "controversial": total > 1 and top / total < config.CONTROVERSIAL_RATIO}
    if cfg["toxic"]:
        stats["toxic_count"] = sum(1 for x in valid if x.get("toxic"))
    return stats


def build_full(domain, event, clusters, labels, summaries) -> dict:
    """Comment giữ trường gốc + level/root_id/nhãn; clusters giữ tóm tắt và thống kê cụm."""
    originals = {str(c.get("id")): c for c in event.get("comments", [])}
    comments, cluster_out = [], []
    for cl in clusters:
        for n in cl["nodes"]:
            lab = labels.get(n["id"]) or trash_label(domain, "rule")
            comments.append({**originals.get(n["id"], {}), "level": n["level"],
                             "root_id": cl["root_id"], "orphan": n["orphan"], **lab})
        cluster_out.append({"root_id": cl["root_id"], "size": len(cl["nodes"]),
                            "summary": summaries.get(cl["root_id"], ""),
                            "thread_stats": _thread_stats(domain, cl["nodes"], labels)})
    return {"event_id": event.get("event_id"), "name": event.get("name", ""),
            "event_key": event.get("event_key", ""), "post_title": event.get("post_title", ""),
            "domain": domain, "comments": comments, "clusters": cluster_out}


def _score(c):
    return to_int(c.get("likes")) + to_int(c.get("reply_count"))


def _showbiz_summary(full) -> dict:
    cfg = config.domain_cfg("showbiz")
    valid = [c for c in full["comments"] if not c["is_trash"]]
    emotion_stats = {lab: sum(1 for c in valid if c.get("emotion") == lab) for lab in cfg["labels"]}
    toxic = [c for c in valid if c.get("toxic")]
    toxic_stats = {"total_toxic": len(toxic),
                   **{t: sum(1 for c in toxic if c.get("toxic_type") == t) for t in config.TOXIC_TYPES}}
    top_level = sorted((c for c in valid if c["level"] == 1), key=_score, reverse=True)
    by_emotion = {}
    for lab in cfg["labels"]:
        best = next((c for c in top_level if c.get("emotion") == lab), None)
        if best:
            by_emotion[lab] = {"comment_id": best["id"], "text": best.get("text", ""),
                               "score": _score(best)}
    texts = {c["id"]: c.get("text", "") for c in full["comments"]}
    return {
        "total_comments": len(valid), "emotion_stats": emotion_stats, "toxic_stats": toxic_stats,
        "top_comments": {
            "most_popular": [{"comment_id": c["id"], "text": c.get("text", ""),
                              "likes": c.get("likes"), "reply_count": c.get("reply_count"),
                              "score": _score(c), "emotion": c.get("emotion")}
                             for c in top_level[:3]],
            "by_emotion": by_emotion, "notable_opinions": []},
        "controversial_threads": [
            {"comment_id": cl["root_id"], "text": texts.get(cl["root_id"], ""),
             "summary": cl["summary"], "thread_stats": cl["thread_stats"]}
            for cl in full["clusters"] if cl["thread_stats"]["controversial"]],
    }


def education_counts_examples(full) -> tuple:
    """Đếm theo stance (+ rác) và lấy tối đa 3 comment cấp 1 nhiều like nhất mỗi stance."""
    labels = config.domain_cfg("education")["labels"]
    counts = Counter("rác" if c["is_trash"] else c.get("stance") for c in full["comments"])
    top_level = sorted((c for c in full["comments"] if c["level"] == 1 and not c["is_trash"]),
                       key=lambda c: _score(c), reverse=True)
    examples = {s: [c.get("text", "")[:150] for c in top_level if c.get("stance") == s][:3]
                for s in labels}
    return {k: counts.get(k, 0) for k in labels + ["rác"]}, examples


def _education_summary(full, digest) -> dict:
    counts, examples = education_counts_examples(full)
    labels = config.domain_cfg("education")["labels"]
    total_valid = sum(counts[s] for s in labels)

    def pct(n):
        return f"{n / total_valid * 100:.1f}%" if total_valid else "0%"

    sums = (digest or {}).get("summaries") or {}
    return {
        "comment_counts": {"total": total_valid + counts["rác"],
                           **{s.replace(" ", "_"): counts[s] for s in labels}, "rác": counts["rác"]},
        "analysis": {s: {"count": counts[s], "percent": pct(counts[s]),
                         "summary": sums.get(s, "") if isinstance(sums, dict) else "",
                         "examples": examples[s]} for s in labels},
        "conclusion": {"focus": (digest or {}).get("focus", ""),
                       "trend": (digest or {}).get("trend", "")},
    }


def build_summary(domain, full, digest=None) -> dict:
    """digest: kết quả request tổng hợp sự kiện (chỉ Giáo dục); None thì để trống phần chữ."""
    head = {"id_content": full["event_id"], "event_name": full["name"],
            "label_sources": dict(Counter(c["label_source"] for c in full["comments"]))}
    body = _showbiz_summary(full) if domain == "showbiz" else _education_summary(full, digest)
    return {**head, **body}
