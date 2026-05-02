"""
merge_final_data là file tổng hợp cuối cùng, lấy data đã được làm sạch từ xulycontent.py và phân tích insights từ analyze_insights.py để tạo ra một file JSON tổng hợp toàn bộ thông tin.
Input:
  output/education/   → các file education_XXX.json đã gộp
  output/showbiz/     → các file showbiz_XXX.json đã gộp

Output:
  insights.json       → tổng hợp toàn bộ

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
            records.extend(data)
        elif isinstance(data, dict):
            records.append(data)
    return records


def analyze_category(records, category):
    """Phân tích insights cho 1 danh mục (education hoặc showbiz)."""
    

    total_events   = len(records)
    events_with_analyzed = [r for r in records if "analyzed" in r]

    # ── Tổng số comment ──
    total_comments_raw  = 0  # gồm cả rác
    total_comments_clean = 0  # đã lọc rác
    total_trash         = 0

    # ── Phân bố stance/emotion ──
    stance_totals = defaultdict(int)

    # ── Top events theo tổng comment ──
    event_comment_counts = []

    # ── Phân bố theo thời gian ──
    events_by_year = defaultdict(int)

    for r in records:
        time_event = r.get("time_event", "")
        year = time_event[:4] if time_event and len(time_event) >= 4 else "unknown"
        events_by_year[year] += 1

        analyzed = r.get("analyzed")
        if not analyzed:
            continue

        counts = analyzed.get("comment_counts", {})
        total  = counts.get("total", 0)
        trash  = counts.get("rác", 0)
        clean  = total - trash

        total_comments_raw   += total
        total_comments_clean += clean
        total_trash          += trash

        # Stance/emotion totals
        analysis = analyzed.get("analysis", {})
        for label, data in analysis.items():
            stance_totals[label] += data.get("count", 0)

        event_comment_counts.append({
            "id_content":  r.get("id_content"),
            "ten_su_kien": r.get("ten_su_kien", ""),
            "time_event":  r.get("time_event", ""),
            "total":       total,
            "clean":       clean,
            "trash":       trash
        })

    # Top 10 events được quan tâm nhất (theo clean comments)
    top_events = sorted(event_comment_counts, key=lambda x: x["clean"], reverse=True)[:10]

    # Tỷ lệ % stance
    total_clean_all = sum(stance_totals.values())
    stance_percent = {}
    for label, count in stance_totals.items():
        pct = round(count / total_clean_all * 100, 1) if total_clean_all > 0 else 0
        stance_percent[label] = {
            "count":   count,
            "percent": f"{pct}%"
        }

    return {
        "category":             category,
        "total_events":         total_events,
        "events_with_analysis": len(events_with_analyzed),
        "events_without_analysis": total_events - len(events_with_analyzed),
        "comment_stats": {
            "total_raw":   total_comments_raw,
            "total_clean": total_comments_clean,
            "total_trash": total_trash,
            "trash_rate":  f"{round(total_trash/total_comments_raw*100, 1)}%" if total_comments_raw > 0 else "0%"
        },
        "stance_distribution": stance_percent,
        "top_events_by_comments": top_events,
        "events_by_year": dict(sorted(events_by_year.items()))
    }


def analyze_overall(edu_insights, show_insights):
    """Tổng hợp toàn bộ 2 danh mục."""

    def safe_int(s):
        try:
            return int(str(s).replace("%", ""))
        except:
            return 0

    total_events   = edu_insights["total_events"] + show_insights["total_events"]
    total_raw      = edu_insights["comment_stats"]["total_raw"]   + show_insights["comment_stats"]["total_raw"]
    total_clean    = edu_insights["comment_stats"]["total_clean"] + show_insights["comment_stats"]["total_clean"]
    total_trash    = edu_insights["comment_stats"]["total_trash"] + show_insights["comment_stats"]["total_trash"]

    return {
        "total_events":   total_events,
        "total_comments": {
            "raw":      total_raw,
            "clean":    total_clean,
            "trash":    total_trash,
            "trash_rate": f"{round(total_trash/total_raw*100, 1)}%" if total_raw > 0 else "0%"
        },
        "by_category": {
            "education": {
                "events":         edu_insights["total_events"],
                "comments_clean": edu_insights["comment_stats"]["total_clean"]
            },
            "showbiz": {
                "events":         show_insights["total_events"],
                "comments_clean": show_insights["comment_stats"]["total_clean"]
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Phân tích tổng hợp data")
    parser.add_argument("--input",  required=True, help="Thư mục chứa education/ và showbiz/")
    parser.add_argument("--output", default="insights.json", help="File output JSON")
    args = parser.parse_args()

    print("📂 Đọc data education...")
    edu_records  = load_category(os.path.join(args.input, "education"))
    print(f"  → {len(edu_records)} events")

    print("📂 Đọc data showbiz...")
    show_records = load_category(os.path.join(args.input, "showbiz"))
    print(f"  → {len(show_records)} events")

    print("\n📊 Phân tích education...")
    edu_insights  = analyze_category(edu_records,  "education")

    print("📊 Phân tích showbiz...")
    show_insights = analyze_category(show_records, "showbiz")

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
    print(f"\n📋 Tóm tắt nhanh:")
    print(f"   Tổng sự kiện    : {overall['total_events']}")
    print(f"   Tổng comment    : {overall['total_comments']['raw']}")
    print(f"   Comment sạch    : {overall['total_comments']['clean']}")
    print(f"   Comment rác     : {overall['total_comments']['trash']} ({overall['total_comments']['trash_rate']})")


if __name__ == "__main__":
    main()