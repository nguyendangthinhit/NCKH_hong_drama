r"""
aggregate_comments_v2.py
------------------------
Gộp tất cả comments từ full folders.

Input:
  - D:\py\git\NCKH_hong_drama\data\process_education\analyzed_dataa\full
  - D:\py\git\NCKH_hong_drama\data\process_showbiz\analyzed_data\full

Output:
  - D:\py\git\NCKH_hong_drama\data\showbiz_comments.json
  - D:\py\git\NCKH_hong_drama\data\education_comments.json

Cách dùng từ D:\py\git\NCKH_hong_drama:
    python aggregate_comments_v2.py
"""

import json
import os

# Absolute paths
BASE_DIR = r"D:\py\git\NCKH_hong_drama"
DATA_DIR = os.path.join(BASE_DIR, "data")

SHOWBIZ_FULL = os.path.join(DATA_DIR, "process_showbiz", "analyzed_data", "full")
EDUCATION_FULL = os.path.join(DATA_DIR, "process_education", "analyzed_dataa", "full")

SHOWBIZ_OUTPUT = os.path.join(DATA_DIR, "showbiz_comments.json")
EDUCATION_OUTPUT = os.path.join(DATA_DIR, "education_comments.json")


def extract_comments_from_file(file_path, is_education=False):
    """Trích xuất comments từ 1 file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"    ❌ Lỗi: {e}")
        return []
    
    comments = []
    
    # Showbiz format
    if not is_education:
        for comment in data.get("comments", []):
            comment_id = comment.get("comment_id", "").strip()
            text = comment.get("text", "").strip()
            emotion = comment.get("emotion", "")
            is_trash = comment.get("is_trash", False)
            
            # Chỉ lấy nếu không phải rác
            if comment_id and text and not is_trash:
                comments.append({
                    "comment_id": comment_id,
                    "text": text,
                    "emotion": emotion
                })
    
    # Education format
    else:
        for comment in data.get("comments", []):
            comment_id = comment.get("comment_id", "").strip()
            text = comment.get("text", "").strip()
            stance = comment.get("stance", "")
            is_trash = comment.get("is_trash", False)
            
            # Chỉ lấy nếu không phải rác
            if comment_id and text and not is_trash:
                comments.append({
                    "comment_id": comment_id,
                    "text": text,
                    "stance": stance
                })
    
    return comments


def aggregate_from_directory(input_dir, is_education=False):
    """Gộp tất cả comments từ full directory."""
    all_comments = []
    
    if not os.path.isdir(input_dir):
        print(f"  ❌ Thư mục không tồn tại: {input_dir}")
        return all_comments
    
    json_files = sorted([f for f in os.listdir(input_dir) if f.endswith(".json")])
    print(f"  📁 Tìm thấy {len(json_files)} files")
    
    for idx, json_file in enumerate(json_files, 1):
        file_path = os.path.join(input_dir, json_file)
        comments = extract_comments_from_file(file_path, is_education)
        all_comments.extend(comments)
        
        if idx % 10 == 0 or idx == len(json_files):
            print(f"    ✓ [{idx}/{len(json_files)}] {json_file}: {len(comments)} comments (tổng: {len(all_comments)})")
    
    return all_comments


def main():
    print("=" * 70)
    print("🎬 XỬ LÝ SHOWBIZ COMMENTS")
    print("=" * 70)
    
    print(f"\n📂 Đọc từ: {SHOWBIZ_FULL}")
    showbiz_comments = aggregate_from_directory(SHOWBIZ_FULL, is_education=False)
    
    print(f"\n  📊 Tổng Showbiz: {len(showbiz_comments):,} comments")
    
    with open(SHOWBIZ_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(showbiz_comments, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Lưu: {SHOWBIZ_OUTPUT}")
    
    # ===== EDUCATION =====
    print("\n" + "=" * 70)
    print("📚 XỬ LÝ EDUCATION COMMENTS")
    print("=" * 70)
    
    print(f"\n📂 Đọc từ: {EDUCATION_FULL}")
    education_comments = aggregate_from_directory(EDUCATION_FULL, is_education=True)
    
    print(f"\n  📊 Tổng Education: {len(education_comments):,} comments")
    
    with open(EDUCATION_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(education_comments, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Lưu: {EDUCATION_OUTPUT}")
    
    # ===== SUMMARY =====
    print("\n" + "=" * 70)
    print("🎉 HOÀN TẤT!")
    print("=" * 70)
    print(f"\n📝 Kết quả:")
    print(f"  🎬 Showbiz:    {len(showbiz_comments):,} comments")
    print(f"  📚 Education:  {len(education_comments):,} comments")
    print(f"  📊 TỔNG:       {len(showbiz_comments) + len(education_comments):,} comments")
    print(f"\n💾 Output directory: {DATA_DIR}")


if __name__ == "__main__":
    main()
