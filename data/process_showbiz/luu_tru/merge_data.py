"""
merge_data_gemini.py  (fixed O(n) union_comments)
---------------------------------------------------
Cách dùng:
    python3 merge_data.py <clean_data_dir> <output_dir>

Ví dụ:
    python3 merge_data.py ./clean_data ./output
    python3 merge_data.py ./clean_data ./output_edu
"""

import json
import os
import sys
import time
import requests

# ──────────────────────────────────────────────
# Điền Gemini API keys vào đây
# Lấy tại: https://aistudio.google.com/app/apikey
# ──────────────────────────────────────────────
API_KEYS = [

]
current_key_index = 0

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)


def get_current_key():
    return API_KEYS[current_key_index]


def rotate_key(reason=""):
    global current_key_index
    if current_key_index < len(API_KEYS) - 1:
        current_key_index += 1
        print(f"  ⚠️  Rotate sang API key #{current_key_index + 1} ({reason})")
        return True
    else:
        print("  ❌ Đã hết API key dự phòng!")
        return False


def call_llm(prompt, retries=3):
    """Gọi Gemini API, tự rotate key khi gặp rate limit."""
    for attempt in range(retries):
        url = GEMINI_URL_TEMPLATE.format(
            model=GEMINI_MODEL,
            api_key=get_current_key()
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 1000,
                "temperature": 0.3
            }
        }

        try:
            resp = requests.post(url, json=body, timeout=60)

            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

            elif resp.status_code == 429:
                if not rotate_key("rate limit 429"):
                    return None
                time.sleep(3)

            elif resp.status_code == 403:
                print(f"  ❌ Key #{current_key_index + 1} bị từ chối (403) — "
                      f"kiểm tra đã enable Gemini API chưa tại aistudio.google.com")
                if not rotate_key("403 forbidden"):
                    return None

            elif resp.status_code == 400:
                print(f"  ❌ Bad request: {resp.text[:300]}")
                return None

            else:
                print(f"  ⚠️  HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(2)

        except requests.exceptions.Timeout:
            print(f"  ⚠️  Timeout lần {attempt + 1}, thử lại...")
            time.sleep(3)
        except Exception as e:
            print(f"  ⚠️  Lỗi: {e}")
            time.sleep(2)

    return None


def synthesize_post_content(pc_clean, pc_output, event_name):
    """Dùng Gemini tổng hợp 2 post_content thành 1 bản rút gọn."""
    prompt = f"""Bạn đang hỗ trợ xây dựng hệ thống phân tích dư luận mạng xã hội.

Sự kiện: {event_name}

Dưới đây là 2 phiên bản mô tả cùng một sự kiện được thu thập từ các bài đăng Facebook khác nhau:

--- Phiên bản 1 ---
{pc_clean}

--- Phiên bản 2 ---
{pc_output}

Hãy tổng hợp 2 phiên bản trên thành 1 đoạn văn ngắn gọn, súc tích, đầy đủ thông tin quan trọng nhất về sự kiện. Yêu cầu:
- Giữ lại các thông tin chính: nhân vật, sự việc, thời gian, số liệu nổi bật
- Loại bỏ thông tin trùng lặp
- Không dùng bullet point, viết thành đoạn văn liền mạch
- Độ dài tối đa 200 từ
- Giữ nguyên ngôn ngữ tiếng Việt

Chỉ trả về đoạn văn tổng hợp, không giải thích thêm."""

    return call_llm(prompt)


def normalize_text(t):
    return " ".join(str(t).strip().split()).lower()


def union_comments(comments_clean, comments_output, id_content):
    """
    Gộp comments từ 2 nguồn, dedup theo text.
    Dùng dict lookup O(1) thay vì vòng lặp O(n²).
    """
    # Build index: normalized_text → comment object (từ clean)
    clean_index = {}
    for c in comments_clean:
        key = normalize_text(c.get("text", ""))
        clean_index[key] = c
        # index cả replies
        for r in c.get("replies", []):
            clean_index[normalize_text(r.get("text", ""))] = r

    seen_texts = set(clean_index.keys())
    merged = list(comments_clean)
    next_order = max((c.get("order", 0) for c in merged), default=0) + 1

    for c in comments_output:
        c_text = normalize_text(c.get("text", ""))

        if c_text not in seen_texts:
            # Comment hoàn toàn mới → thêm vào
            new_cmt_id = f"cmt_{id_content}_{str(next_order).zfill(4)}"
            new_cmt = {
                "comment_id": new_cmt_id,
                "order": next_order,
                "text": c.get("text", ""),
                "likes": c.get("likes", 0),
                "reply_count": 0,
                "replies": []
            }
            seen_texts.add(c_text)
            clean_index[c_text] = new_cmt

            r_order = 1
            for r in c.get("replies", []):
                r_text = normalize_text(r.get("text", ""))
                if r_text not in seen_texts:
                    new_cmt["replies"].append({
                        "comment_id": f"{new_cmt_id}_r{str(r_order).zfill(2)}",
                        "order": r_order,
                        "reply_to_id": new_cmt_id,
                        "text": r.get("text", ""),
                        "likes": r.get("likes", 0)
                    })
                    seen_texts.add(r_text)
                    r_order += 1

            new_cmt["reply_count"] = len(new_cmt["replies"])
            merged.append(new_cmt)
            next_order += 1

        else:
            # Comment đã có → bổ sung replies mới nếu có
            existing = clean_index.get(c_text)
            if existing and "replies" in existing:
                r_order = len(existing["replies"]) + 1
                for r in c.get("replies", []):
                    r_text = normalize_text(r.get("text", ""))
                    if r_text not in seen_texts:
                        existing["replies"].append({
                            "comment_id": f"{existing['comment_id']}_r{str(r_order).zfill(2)}",
                            "order": r_order,
                            "reply_to_id": existing["comment_id"],
                            "text": r.get("text", ""),
                            "likes": r.get("likes", 0)
                        })
                        seen_texts.add(r_text)
                        r_order += 1
                existing["reply_count"] = len(existing["replies"])

    return merged


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 merge_data_gemini.py <clean_data_dir> <output_dir>")
        sys.exit(1)

    clean_dir = sys.argv[1]
    output_dir = sys.argv[2]

    clean_files = {f for f in os.listdir(clean_dir) if f.endswith(".json")}
    output_files = {f for f in os.listdir(output_dir) if f.endswith(".json")}
    common = clean_files & output_files
    only_clean = clean_files - output_files

    print(f"📂 Tìm thấy {len(common)} file chung, {len(only_clean)} file chỉ có trong clean_data\n")

    for filename in sorted(common):
        id_content = filename.replace(".json", "")
        print(f"🔄 Đang xử lý: {id_content}")

        clean_data = load_json(os.path.join(clean_dir, filename))
        output_data = load_json(os.path.join(output_dir, filename))

        event_name = clean_data.get("event_name", id_content)
        pc_clean   = clean_data.get("post_content", "")
        pc_output  = output_data.get("post_content", "")

        # Tổng hợp post_content
        print(f"  🤖 Gemini đang tổng hợp post_content...")
        merged_pc = synthesize_post_content(pc_clean, pc_output, event_name)
        if merged_pc is None:
            print(f"  ⚠️  Gemini thất bại, giữ nguyên post_content từ clean_data")
            merged_pc = pc_clean

        # Gộp comments (nhanh)
        print(f"  💬 Gộp comments...")
        comments_clean  = clean_data.get("comments", [])
        comments_output = output_data.get("comments", [])
        merged_comments = union_comments(comments_clean, comments_output, id_content)

        result = {
            "id_content":  id_content,
            "event_name":  event_name,
            "sort_mode":   clean_data.get("sort_mode", "most_relevant"),
            "post_content": merged_pc,
            "comments":    merged_comments
        }

        save_json(os.path.join(clean_dir, filename), result)
        print(f"  ✅ Đã ghi đè: {filename} ({len(merged_comments)} comments)\n")

        time.sleep(1)

    if only_clean:
        print(f"ℹ️  {len(only_clean)} file chỉ có trong clean_data, giữ nguyên:")
        for f in sorted(only_clean):
            print(f"   - {f}")

    print("\n🎉 Hoàn tất!")


if __name__ == "__main__":
    main()