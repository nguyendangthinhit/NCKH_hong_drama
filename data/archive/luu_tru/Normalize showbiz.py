"""
normalize_showbiz_final.py
--------------------------

Script chuẩn hóa dữ liệu Showbiz cũ sang định dạng mới.

Mục đích:
- Chuyển mỗi mục trong Showbiz.json thành một file JSON riêng theo `id_content`.
- Gom các trường `post_content` của nhiều event thành một chuỗi `post_content` duy nhất.
- Chuẩn hoá cấu trúc comment/reply thành schema có `comment_id`, `order`, `text`, `likes`, `reply_count`, và `replies`.
- Xuất các file đã chuẩn hoá vào thư mục đích.

Yêu cầu:
- Python 3.x
- File input là một JSON mảng (ví dụ Showbiz.json) chứa các entry có `id_content` và `events`.

Cách dùng:
    python3 normalize_showbiz_final.py <input_file> <output_dir>

Ví dụ:
    python3 normalize_showbiz_final.py Showbiz.json ./output
"""

import json
import os
import sys


def normalize_comments(raw_comments, id_content):
    """
    Chuyển flat list comment (lẫn lộn top-level + reply) sang cấu trúc:
    [
      {
        comment_id, order, text, likes, reply_count,
        replies: [ { comment_id, order, reply_to_id, text, likes } ]
      }
    ]

    Logic xác định parent:
    - Không có 'parentReply' → top-level comment
    - Có 'parentReply' → reply, gắn vào top-level có profileName == parentReply.author.name
    - Reply của reply (lớp 3) → vẫn flatten vào cùng top-level thread đó
    """

    top_level = []   # list of raw top-level comment
    reply_pool = []  # list of raw reply comment

    for item in raw_comments:
        if item.get("parentReply"):
            reply_pool.append(item)
        else:
            top_level.append(item)

    # Map: profileName → comment_id (để reply của reply cũng tìm được thread gốc)
    # Ưu tiên top-level, sau đó các profileName trong reply_pool cũng có thể là parent
    name_to_cmt_id = {}

    result_comments = []
    cmt_order = 1

    for tl in top_level:
        cmt_id = f"cmt_{id_content}_{str(cmt_order).zfill(4)}"
        author_name = tl.get("profileName", "")
        name_to_cmt_id[author_name] = cmt_id

        result_comments.append({
            "_cmt_id": cmt_id,
            "_author": author_name,
            "comment_id": cmt_id,
            "order": cmt_order,
            "text": tl.get("text", ""),
            "likes": _to_int(tl.get("likesCount", 0)),
            "reply_count": 0,   # cập nhật sau
            "replies": []
        })
        cmt_order += 1

    # Gắn reply vào đúng top-level thread
    # Duyệt reply_pool nhiều lần để xử lý cả reply của reply (lớp 3)
    unmatched_prev = None
    while True:
        unmatched = []
        for rp in reply_pool:
            parent_name = ""
            try:
                parent_name = rp["parentReply"]["author"]["name"]
            except (KeyError, TypeError):
                pass

            # Tìm top-level thread chứa parent_name
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

                # Đăng ký author của reply này vào name_to_cmt_id
                # (để reply của reply tìm được thread)
                rp_author = rp.get("profileName", "")
                if rp_author and rp_author not in name_to_cmt_id:
                    name_to_cmt_id[rp_author] = thread["comment_id"]
            else:
                unmatched.append(rp)

        # Nếu không giảm được unmatched → dừng tránh infinite loop
        if unmatched_prev is not None and len(unmatched) >= len(unmatched_prev):
            break
        if not unmatched:
            break
        reply_pool = unmatched
        unmatched_prev = unmatched

    # Cập nhật reply_count và dọn internal fields
    final = []
    for c in result_comments:
        c["reply_count"] = len(c["replies"])
        c.pop("_cmt_id", None)
        c.pop("_author", None)
        final.append(c)

    return final


def _find_thread(result_comments, parent_name, name_to_cmt_id):
    """Tìm thread (top-level comment object) chứa author có tên parent_name."""
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


def process_entry(entry):
    id_content = entry.get("id_content", "unknown")
    events = entry.get("events", [])

    post_parts = []
    all_raw_comments = []

    for ev in events:
        pc = ev.get("post_content", "").strip()
        if pc:
            post_parts.append(pc)
        all_raw_comments.extend(ev.get("comments", []))

    return {
        "id_content": id_content,
        "sort_mode": "most_recent",
        "post_content": " ".join(post_parts),
        "comments": normalize_comments(all_raw_comments, id_content)
    }


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 normalize_showbiz_final.py <input.json> <output_dir>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = 0
    for entry in data:
        id_content = entry.get("id_content", "unknown")
        result = process_entry(entry)

        out_path = os.path.join(output_dir, f"{id_content}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✅  {id_content}.json")
        total += 1

    print(f"\n🎉 Hoàn tất! {total} files → {output_dir}/")


if __name__ == "__main__":
    main()