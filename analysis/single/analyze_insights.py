"""
analyze_insights.py  v2
------------------------
Đọc toàn bộ data đã gộp → phân tích tổng hợp → xuất JSON.

Hỗ trợ 2 schema:
  - Education: dùng 'analysis' (stance: tích cực/tiêu cực/trung lập/ý kiến riêng)
  - Showbiz:   dùng 'emotion_stats' + 'toxic_stats'

Input:
  output/education/   → các file education_XXX.json đã gộp
  output/showbiz/     → các file showbiz_XXX.json đã gộp

Output:
  insights.json

Cách dùng:
    python3 analyze_insights.py --input ./output --output ./insights.json
"""

import json
import os
import argparse
from collections import defaultdict


def load_category(cat_dir):
    """Đọc tất cả file JSON trong thư mục."""
    records = []
    if not os.path.isdir(cat_dir):
        return records
    for filename in sorted(os.listdir(cat_dir)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(cat_dir, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            records.extend([r for r in data if isinstance(r, dict)])
        elif isinstance(data, dict):
            records.append(data)
    return records


# ──────────────────────────────────────────────
# Education analysis (dùng 'analyzed.analysis' với stance)
# ──────────────────────────────────────────────

def analyze_education(records):
    STANCE_LABELS = ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng"]

    total_events         = len(records)
    events_with_analyzed = [r for r in records if "analyzed" in r]

    total_raw   = 0
    total_clean = 0
    total_trash = 0
    stance_totals = defaultdict(int)
    event_comment_counts = []
    events_by_year = defaultdict(int)

    for r in records:
        year = (r.get("time_event") or "")[:4] or "unknown"
        events_by_year[year] += 1

        analyzed = r.get("analyzed")
        if not analyzed:
            continue

        counts = analyzed.get("comment_counts", {})
        total  = counts.get("total", 0)
        trash  = counts.get("rác", 0)
        clean  = total - trash

        total_raw   += total
        total_clean += clean
        total_trash += trash

        for label, data in analyzed.get("analysis", {}).items():
            stance_totals[label] += data.get("count", 0)

        event_comment_counts.append({
            "id_content":  r.get("id_content"),
            "ten_su_kien": r.get("ten_su_kien", ""),
            "time_event":  r.get("time_event", ""),
            "total":       total,
            "clean":       clean,
            "trash":       trash
        })

    top_events = sorted(event_comment_counts, key=lambda x: x["clean"], reverse=True)[:10]

    total_clean_all = sum(stance_totals.values())
    stance_percent  = {
        label: {
            "count":   count,
            "percent": f"{round(count/total_clean_all*100, 1)}%" if total_clean_all > 0 else "0%"
        }
        for label, count in stance_totals.items()
    }

    return {
        "category":                  "education",
        "total_events":              total_events,
        "events_with_analysis":      len(events_with_analyzed),
        "events_without_analysis":   total_events - len(events_with_analyzed),
        "comment_stats": {
            "total_raw":   total_raw,
            "total_clean": total_clean,
            "total_trash": total_trash,
            "trash_rate":  f"{round(total_trash/total_raw*100, 1)}%" if total_raw > 0 else "0%"
        },
        "stance_distribution":       stance_percent,
        "top_events_by_comments":    top_events,
        "events_by_year":            dict(sorted(events_by_year.items()))
    }


# ──────────────────────────────────────────────
# Showbiz analysis (dùng 'analyzed.emotion_stats' + 'toxic_stats')
# ──────────────────────────────────────────────

def analyze_showbiz(records):
    EMOTION_LABELS = ["Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập"]

    total_events         = len(records)
    events_with_analyzed = [r for r in records if "analyzed" in r]

    total_raw    = 0
    total_clean  = 0
    total_trash  = 0
    emotion_totals = defaultdict(int)
    toxic_totals   = {
        "total_toxic":          0,
        "chửi bới":             0,
        "công kích cá nhân":    0,
        "công kích người thân": 0
    }
    event_comment_counts = []
    events_by_year = defaultdict(int)

    for r in records:
        year = (r.get("time_event") or "")[:4] or "unknown"
        events_by_year[year] += 1

        analyzed = r.get("analyzed")
        if not analyzed:
            continue

        # Showbiz summary có thể là trực tiếp (không wrap trong 'analyzed')
        # hoặc đã được gộp vào field 'analyzed'
        emotion_stats = analyzed.get("emotion_stats", {})
        toxic_stats   = analyzed.get("toxic_stats", {})
        total_cmt     = analyzed.get("total_comments", 0)

        # Tính trash từ total - sum(emotion)
        clean = sum(emotion_stats.values())
        trash = total_cmt - clean if total_cmt > clean else 0

        total_raw   += total_cmt
        total_clean += clean
        total_trash += trash

        for label in EMOTION_LABELS:
            emotion_totals[label] += emotion_stats.get(label, 0)

        for key in toxic_totals:
            toxic_totals[key] += toxic_stats.get(key, 0)

        event_comment_counts.append({
            "id_content":  r.get("id_content"),
            "ten_su_kien": r.get("ten_su_kien", ""),
            "time_event":  r.get("time_event", ""),
            "total":       total_cmt,
            "clean":       clean,
            "trash":       trash
        })

    top_events = sorted(event_comment_counts, key=lambda x: x["clean"], reverse=True)[:10]

    total_clean_all  = sum(emotion_totals.values())
    emotion_percent  = {
        label: {
            "count":   emotion_totals[label],
            "percent": f"{round(emotion_totals[label]/total_clean_all*100, 1)}%" if total_clean_all > 0 else "0%"
        }
        for label in EMOTION_LABELS
    }

    return {
        "category":                  "showbiz",
        "total_events":              total_events,
        "events_with_analysis":      len(events_with_analyzed),
        "events_without_analysis":   total_events - len(events_with_analyzed),
        "comment_stats": {
            "total_raw":   total_raw,
            "total_clean": total_clean,
            "total_trash": total_trash,
            "trash_rate":  f"{round(total_trash/total_raw*100, 1)}%" if total_raw > 0 else "0%"
        },
        "emotion_distribution": emotion_percent,
        "toxic_stats": {
            key: {
                "count":   val,
                "percent": f"{round(val/total_clean*100, 1)}%" if total_clean > 0 else "0%"
            }
            for key, val in toxic_totals.items()
        },
        "top_events_by_comments":    top_events,
        "events_by_year":            dict(sorted(events_by_year.items()))
    }


# ──────────────────────────────────────────────
# Overall
# ──────────────────────────────────────────────

def analyze_overall(edu, show):
    total_events = edu["total_events"] + show["total_events"]
    total_raw    = edu["comment_stats"]["total_raw"]   + show["comment_stats"]["total_raw"]
    total_clean  = edu["comment_stats"]["total_clean"] + show["comment_stats"]["total_clean"]
    total_trash  = edu["comment_stats"]["total_trash"] + show["comment_stats"]["total_trash"]

    return {
        "total_events":   total_events,
        "total_comments": {
            "raw":        total_raw,
            "clean":      total_clean,
            "trash":      total_trash,
            "trash_rate": f"{round(total_trash/total_raw*100, 1)}%" if total_raw > 0 else "0%"
        },
        "by_category": {
            "education": {
                "events":         edu["total_events"],
                "comments_clean": edu["comment_stats"]["total_clean"],
                "events_with_analysis": edu["events_with_analysis"]
            },
            "showbiz": {
                "events":         show["total_events"],
                "comments_clean": show["comment_stats"]["total_clean"],
                "events_with_analysis": show["events_with_analysis"]
            }
        }
    }


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  required=True, help="Thư mục chứa education/ và showbiz/")
    parser.add_argument("--output", default="insights.json")
    args = parser.parse_args()

    print("📂 Đọc data education...")
    edu_records  = load_category(os.path.join(args.input, "education"))
    print(f"  → {len(edu_records)} events")

    print("📂 Đọc data showbiz...")
    show_records = load_category(os.path.join(args.input, "showbiz"))
    print(f"  → {len(show_records)} events")

    print("\n📊 Phân tích education...")
    edu_insights  = analyze_education(edu_records)

    print("📊 Phân tích showbiz...")
    show_insights = analyze_showbiz(show_records)

    print("📊 Tổng hợp overall...")
    overall = analyze_overall(edu_insights, show_insights)

    result = {
        "overall":   overall,
        "education": edu_insights,
        "showbiz":   show_insights
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Hoàn tất! → {args.output}")
    print(f"\n📋 Tóm tắt:")
    print(f"   Tổng sự kiện    : {overall['total_events']}")
    print(f"   Comment raw     : {overall['total_comments']['raw']}")
    print(f"   Comment sạch    : {overall['total_comments']['clean']}")
    print(f"   Comment rác     : {overall['total_comments']['trash']} ({overall['total_comments']['trash_rate']})")
    print(f"\n   Education ({edu_insights['total_events']} sự kiện):")
    for label, data in edu_insights.get("stance_distribution", {}).items():
        print(f"     {label}: {data['count']} ({data['percent']})")
    print(f"\n   Showbiz ({show_insights['total_events']} sự kiện):")
    for label, data in show_insights.get("emotion_distribution", {}).items():
        print(f"     {label}: {data['count']} ({data['percent']})")


if __name__ == "__main__":
    main()