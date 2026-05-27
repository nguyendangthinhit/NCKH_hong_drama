"""
Script chuẩn hóa dữ liệu cũ sang định dạng mới.

Mục đích:
- Đọc dữ liệu đầu vào (FILE_DATA_OLD) và chuyển về cấu trúc chuẩn (FILE_OUTPUT).
- Kiểm tra trùng lặp bằng model Gemini (Google Generative AI) và tự động xoay API keys khi gặp lỗi Quota (429).
- Trích xuất danh sách nhân vật liên quan cho mục giải trí bằng Gemini.
- Gán id mới (`showbiz_xxx`, `education_xxx`) dựa trên dữ liệu hiện có trong FILE_DATA_NEW.

Yêu cầu:
- Điền các API key vào `API_KEYS`.
- Cài đặt package `google.generativeai` và cấu hình môi trường phù hợp.

Sử dụng:
- Chạy trực tiếp file này để xuất file `data_old_to_new_format.json`.
"""

import json
import google.generativeai as genai

# ================= CẤU HÌNH API KEYS =================
# Điền TẤT CẢ các API Key bạn có vào mảng này (để trong ngoặc kép, cách nhau bởi dấu phẩy)
API_KEYS = [

]

FILE_DATA_OLD = "data_web_old.json"
FILE_DATA_NEW = "data_web.json" 
FILE_OUTPUT = "data_old_to_new_format.json"

# ================= LOGIC QUẢN LÝ TỰ ĐỘNG ĐỔI KEY =================
current_key_index = 0

def setup_gemini():
    """Cấu hình lại Gemini với Key hiện tại"""
    genai.configure(api_key=API_KEYS[current_key_index])
    return genai.GenerativeModel('gemini-2.5-flash')

# Khởi tạo model lần đầu
model = setup_gemini()

def rotate_api_key():
    """Hàm tự động nhảy sang Key tiếp theo"""
    global current_key_index, model
    current_key_index += 1
    
    if current_key_index >= len(API_KEYS):
        print("\n🚨 ĐÃ THỬ HẾT TOÀN BỘ API KEY TRONG DANH SÁCH MÀ VẪN LỖI! Dừng chương trình.")
        exit(1)
        
    print(f"\n🔄 Đang đổi sang API Key số {current_key_index + 1}...")
    model = setup_gemini()

def call_gemini_with_retry(prompt):
    """Hàm bọc (Wrapper) để gọi Gemini. Cứ lỗi Quota là tự xoay Key gọi lại."""
    while True:
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_msg = str(e)
            # Nếu bắt được lỗi 429 hoặc Quota -> Kích hoạt đổi Key
            if "429" in error_msg or "Quota" in error_msg:
                print(f"⚠️ Key số {current_key_index + 1} hết Quota (Lỗi 429).")
                rotate_api_key() # Đổi key
                # Vòng lặp while sẽ tự động quay lại try với Key mới mà không bị rớt data
            else:
                print(f"⚠️ Lỗi gọi API không xác định: {e}")
                return None

# ================= CÁC HÀM XỬ LÝ DỮ LIỆU =================
def get_max_ids(new_data):
    max_showbiz = 0
    max_education = 0
    for item in new_data:
        id_val = item.get("id_content", "")
        if id_val.startswith("showbiz_"):
            num = int(id_val.split("_")[1])
            max_showbiz = max(max_showbiz, num)
        elif id_val.startswith("education_"):
            num = int(id_val.split("_")[1])
            max_education = max(max_education, num)
    return max_showbiz, max_education

def check_duplicate_with_gemini(old_title, old_content, new_data_list, category):
    existing_events = [
        f"ID: {item['id_content']} - Tên sự kiện: {item.get('ten_su_kien', '')}" 
        for item in new_data_list 
        if (category == 'social' and 'showbiz' in item.get('id_content', '')) or 
           (category == 'education' and 'education' in item.get('id_content', ''))
    ]
    if not existing_events:
        return False
        
    prompt = f"""
    Tôi có một sự kiện cũ như sau:
    - Tiêu đề: {old_title}
    - Nội dung tóm tắt: {old_content[:500]}...

    Dưới đây là danh sách các sự kiện hiện có:
    {chr(10).join(existing_events)}

    Hãy phân tích xem sự kiện cũ có trùng khớp (> 70%) với bất kỳ sự kiện nào trong danh sách không.
    Chỉ trả về JSON: {{"is_duplicate": true/false}}
    """
    
    response_text = call_gemini_with_retry(prompt)
    if not response_text:
        return False
        
    try:
        result_text = response_text.replace('```json', '').replace('```', '').strip()
        result_json = json.loads(result_text)
        return result_json.get("is_duplicate", False)
    except Exception:
        return False

def extract_actors_with_gemini(content):
    prompt = f"""
    Đọc nội dung sự kiện giải trí sau và trích xuất danh sách nhân vật có liên quan.
    Nội dung: {content[:2000]}
    
    Chỉ trả về danh sách JSON (nếu không có thì trả về mảng rỗng []):
    [
      {{
        "name": "Tên nhân vật",
        "role": "Vai trò/Liên quan (ngắn gọn 1 câu)"
      }}
    ]
    """
    
    response_text = call_gemini_with_retry(prompt)
    if not response_text:
        return []
        
    try:
        result_text = response_text.replace('```json', '').replace('```', '').strip()
        actors = json.loads(result_text)
        return actors if isinstance(actors, list) else []
    except Exception:
        return []

def main():
    print("🚀 Bắt đầu quá trình chuẩn hóa dữ liệu với Multi-API Key...")
    with open(FILE_DATA_OLD, 'r', encoding='utf-8') as f:
        old_data = json.load(f)
        
    try:
        with open(FILE_DATA_NEW, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
    except FileNotFoundError:
        new_data = []

    max_showbiz, max_education = get_max_ids(new_data)
    print(f"📊 ID hiện tại: showbiz_{max_showbiz:03d}, education_{max_education:03d}")
    
    standardized_data = []
    skipped_count = 0

    for index, item in enumerate(old_data):
        print(f"\n⏳ Đang xử lý bài {index + 1}/{len(old_data)}: {item.get('title', '')[:50]}...")
        
        category = "social" if item.get("id") in ["social", "soical"] else item.get("id")
        if category == "lifestyle":
            continue
            
        is_dup = check_duplicate_with_gemini(item.get("title", ""), item.get("content", ""), new_data, category)
        if is_dup:
            print("   -> ❌ Bỏ qua: Sự kiện đã tồn tại (>70% khớp).")
            skipped_count += 1
            continue
            
        print("   -> ✅ Pass: Sự kiện mới. Tiến hành chuẩn hóa...")
        
        new_item = {
            "id_content": "",
            "ten_su_kien": item.get("title", ""),
            "danh_muc": "",
            "content": item.get("content", ""),
            "time_event": item.get("date", ""),
            "source_url": item.get("source_url", ""), 
            "highlights": item.get("highlights", [])  
        }
        
        if category == "social":
            max_showbiz += 1
            new_item["id_content"] = f"showbiz_{max_showbiz:03d}"
            new_item["danh_muc"] = "Giải trí"
            print("   -> 🤖 Đang nhờ Gemini bóc tách nhân vật...")
            new_item["actor_related"] = extract_actors_with_gemini(item.get("content", ""))
            print(f"   -> Đã tìm thấy {len(new_item.get('actor_related', []))} nhân vật liên quan.")
            
        elif category == "education":
            max_education += 1
            new_item["id_content"] = f"education_{max_education:03d}"
            new_item["danh_muc"] = "Giáo dục"
            
        standardized_data.append(new_item)

    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(standardized_data, f, ensure_ascii=False, indent=4)
        
    print("\n🎉 HOÀN THÀNH!")
    print(f"✅ Đã chuẩn hóa thành công: {len(standardized_data)} bài.")
    print(f"🗑️ Đã bỏ qua do trùng lặp: {skipped_count} bài.")

if __name__ == "__main__":
    main()