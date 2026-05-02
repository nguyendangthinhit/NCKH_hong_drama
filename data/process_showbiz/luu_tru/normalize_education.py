"""
normalize_education.py
----------------------
Tách education.json ra từng file {id_content}.json

Cấu trúc input:
{
  "ten_su_kien.json": {
    "id_content": "education_037",
    "title": "...",
    "post": [
      {
        "post_content": "...",
        "comments": [ { "text", "profileName", "likesCount", "commentsCount", "parentReply"? } ]
      }
    ]
  }
}

Output mỗi file:
{
  "id_content": "education_037",
  "sort_mode": "most_recent",
  "post_content": "post 1 + post 2 + ...",
  "comments": [ chuẩn format mới ]
}

Cách dùng:
    python3 normalize_education.py <input.json> <output_dir>

Ví dụ:
    python3 normalize_education.py education.json ./output_edu
"""

import json
import os
import sys
from collections import defaultdict


def normalize_text(t):
    return " ".join(str(t).strip().split()).lower()


def normalize_comments(raw_comments, id_content):
    """
    Flat list comment (lẫn top-level + reply) → format chuẩn mới.
    Logic giống showbiz: dùng parentReply.author.name để xác định thread.
    """
    top_level = []
    reply_pool = []

    for item in raw_comments:
        if item.get("parentReply"):
            reply_pool.append(item)
        else:
            top_level.append(item)

    name_to_cmt_id = {}
    result_comments = []
    cmt_order = 1

    for tl in top_level:
        cmt_id = f"cmt_{id_content}_{str(cmt_order).zfill(4)}"
        author_name = tl.get("profileName", "")
        name_to_cmt_id[author_name] = cmt_id

        result_comments.append({
            "comment_id": cmt_id,
            "order": cmt_order,
            "text": tl.get("text", ""),
            "likes": _to_int(tl.get("likesCount", 0)),
            "reply_count": 0,
            "replies": []
        })
        cmt_order += 1

    # Gắn replies vào đúng thread (kể cả reply của reply → flatten)
    unmatched_prev = None
    while True:
        unmatched = []
        for rp in reply_pool:
            parent_name = ""
            try:
                parent_name = rp["parentReply"]["author"]["name"]
            except (KeyError, TypeError):
                pass

            thread = _find_thread(result_comments, parent_name, name_to_cmt_id)

            if thread is not None:
                r_order = len(thread["replies"]) + 1
                r_id = f"{thread['comment_id']}_r{str(r_order).zfill(2)}"
                thread["replies"].append({
                    "comment_id": r_id,
                    "order": r_order,
                    "reply_to_id": thread["comment_id"],
                    "text": rp.get("text", ""),
                    "likes": _to_int(rp.get("likesCount", 0))
                })
                rp_author = rp.get("profileName", "")
                if rp_author and rp_author not in name_to_cmt_id:
                    name_to_cmt_id[rp_author] = thread["comment_id"]
            else:
                unmatched.append(rp)

        if unmatched_prev is not None and len(unmatched) >= len(unmatched_prev):
            break
        if not unmatched:
            break
        reply_pool = unmatched
        unmatched_prev = unmatched

    for c in result_comments:
        c["reply_count"] = len(c["replies"])

    return result_comments


def _find_thread(result_comments, parent_name, name_to_cmt_id):
    target_cmt_id = name_to_cmt_id.get(parent_name)
    if not target_cmt_id:
        return None
    for c in result_comments:
        if c["comment_id"] == target_cmt_id:
            return c
    return None


def _to_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def process_entry(id_content, entry):
    """Xử lý 1 sự kiện education."""
    posts = entry.get("post", [])

    post_parts = []
    all_raw_comments = []

    for p in posts:
        pc = p.get("post_content", "").strip()
        if pc:
            post_parts.append(pc)
        all_raw_comments.extend(p.get("comments", []))

    return {
        "id_content": id_content,
        "sort_mode": "most_recent",
        "post_content": " ".join(post_parts),
        "comments": normalize_comments(all_raw_comments, id_content)
    }


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 normalize_education.py <input.json> <output_dir>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # data là dict: { "ten_file.json": { id_content, title, post, ... } }
    # Group theo id_content để xử lý trùng lặp nếu có
    grouped = defaultdict(list)
    for _filename, entry in data.items():
        id_content = entry.get("id_content", "unknown")
        grouped[id_content].append(entry)

    total = 0
    for id_content, entries in grouped.items():
        if len(entries) > 1:
            print(f"  ⚠️  '{id_content}' có {len(entries)} entry trùng → gộp posts lại")
            merged_entry = {"post": []}
            for e in entries:
                merged_entry["post"].extend(e.get("post", []))
            result = process_entry(id_content, merged_entry)
        else:
            result = process_entry(id_content, entries[0])

        out_path = os.path.join(output_dir, f"{id_content}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✅  {id_content}.json ({len(result['comments'])} comments)")
        total += 1

    print(f"\n🎉 Hoàn tất! {total} files → {output_dir}/")


if __name__ == "__main__":
    main()