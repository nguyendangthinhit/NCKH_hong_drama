"""
merge_final_data.py  v2
------------------------
Gộp data web + data analyzed (summary) theo id_content.

Hỗ trợ format data_web.json:
  { "showbiz": [...], "giáo dục": [...] }

Cách dùng:
    py merge_final_data.py --web .\data_web.json --edu_sum .\analyzed\education\summary --output .\output
    py merge_final_data.py --web .\data_web.json --edu_sum .\analyzed\education\summary --show_sum .\analyzed\showbiz\summary --output .\output
"""

import json
import os
import argparse


def load_web_data(web_path):
    with open(web_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    education_map = {}
    showbiz_map   = {}

    def process_record(record):
        """Chuẩn hóa 1 record — bỏ field parse_error nhưng vẫn giữ record."""
        if "parse_error" in record:
            print(f"  ℹ️  Bỏ field parse_error: {record.get('id_content', '?')}")
        id_content = record.get("id_content", "").strip()
        if not id_content:
            return None
        return {
            "id_content":    id_content,
            "ten_su_kien":   record.get("ten_su_kien", ""),
            "content":       record.get("content", ""),
            "actor_related": record.get("actor_related", []),
            "time_event":    record.get("time_event", ""),
        }

    if isinstance(data, dict):
        # Format: { "showbiz": [...], "giáo dục": [...] }
        for key, records in data.items():
            if not isinstance(records, list):
                continue
            key_lower = key.lower().strip()
            is_edu = any(k in key_lower for k in ["giáo dục", "giao duc", "education", "giáo"])
            for record in records:
                clean = process_record(record)
                if clean:
                    if is_edu:
                        education_map[clean["id_content"]] = clean
                    else:
                        showbiz_map[clean["id_content"]] = clean

    elif isinstance(data, list):
        # Format: flat list với field danh_muc
        for record in data:
            danh_muc = record.get("danh_muc", "").lower().strip()
            is_edu   = any(k in danh_muc for k in ["giáo dục", "giao duc", "education"])
            clean    = process_record(record)
            if clean:
                if is_edu:
                    education_map[clean["id_content"]] = clean
                else:
                    showbiz_map[clean["id_content"]] = clean

    print(f"  📚 Education: {len(education_map)} records")
    print(f"  🎬 Showbiz:   {len(showbiz_map)} records")
    return education_map, showbiz_map


def load_summary_dir(summary_dir):
    if not summary_dir or not os.path.isdir(summary_dir):
        return {}
    result = {}
    for filename in sorted(os.listdir(summary_dir)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(summary_dir, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
        id_content = data.get("id_content", filename.replace(".json", ""))
        result[id_content] = data
    return result


# ── THAY THẾ hàm merge_records trong merge_final_data_v2.py ──

def merge_records(web_map, summary_map, category_label):
    merged  = []
    all_ids = set(web_map.keys()) | set(summary_map.keys())

    for id_content in sorted(all_ids):
        web_rec     = web_map.get(id_content)
        summary_rec = summary_map.get(id_content)

        if web_rec is None:
            print(f"  ⚠️  [{category_label}] {id_content}: có analyzed nhưng không có data web → bỏ qua")
            continue

        record = {**web_rec}

        if summary_rec:
            # Phân biệt schema education vs showbiz
            if category_label == "education":
                # Education: dùng comment_counts, analysis, conclusion
                record["analyzed"] = {
                    "comment_counts": summary_rec.get("comment_counts", {}),
                    "analysis":       summary_rec.get("analysis", {}),
                    "conclusion":     summary_rec.get("conclusion", {})
                }
            else:
                # Showbiz: dùng emotion_stats, toxic_stats, total_comments, top_comments, controversial_threads
                record["analyzed"] = {
                    "total_comments":       summary_rec.get("total_comments", 0),
                    "emotion_stats":        summary_rec.get("emotion_stats", {}),
                    "toxic_stats":          summary_rec.get("toxic_stats", {}),
                    "top_comments":         summary_rec.get("top_comments", {}),
                    "controversial_threads": summary_rec.get("controversial_threads", [])
                }
        else:
            print(f"  ℹ️  [{category_label}] {id_content}: chưa có analyzed data")

        merged.append(record)

    return merged
def save_output(records, output_dir, category):
    cat_dir = os.path.join(output_dir, category)
    os.makedirs(cat_dir, exist_ok=True)
    for record in records:
        id_content = record["id_content"]
        out_path   = os.path.join(cat_dir, f"{id_content}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Đã lưu {len(records)} files → {cat_dir}/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--web",      required=True)
    parser.add_argument("--edu_sum",  required=True)
    parser.add_argument("--show_sum", default="")
    parser.add_argument("--output",   required=True)
    args = parser.parse_args()

    print("📂 Đọc data web...")
    education_web, showbiz_web = load_web_data(args.web)

    print("\n📂 Đọc data analyzed education...")
    education_summary = load_summary_dir(args.edu_sum)
    print(f"  → {len(education_summary)} files summary")

    print("\n📂 Đọc data analyzed showbiz...")
    showbiz_summary = load_summary_dir(args.show_sum) if args.show_sum else {}
    print(f"  → {len(showbiz_summary)} files summary")

    print("\n🔀 Gộp education...")
    education_merged = merge_records(education_web, education_summary, "education")

    print("\n🔀 Gộp showbiz...")
    showbiz_merged = merge_records(showbiz_web, showbiz_summary, "showbiz")

    print("\n💾 Lưu output...")
    save_output(education_merged, args.output, "education")
    save_output(showbiz_merged,   args.output, "showbiz")

    print(f"\n🎉 Hoàn tất!")
    print(f"   Education: {len(education_merged)} files")
    print(f"   Showbiz:   {len(showbiz_merged)} files")
    print(f"   Output:    {args.output}/")


if __name__ == "__main__":
    main()