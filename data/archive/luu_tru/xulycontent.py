" file này là file dùng để xử lý cái dữ liệu bị nhiễu trong file content để đưa vào n8n fix"
"file này sẽ đọc file showbiz.json, kiểm tra xem trường content có phải là chuỗi JSON lỗi không, nếu có thì sẽ cố gắng parse lại để lấy ra nội dung thực sự của sự kiện và danh sách nhân vật liên quan. Sau đó xuất ra file mới showbiz1.json đã được làm sạch."
"còn chạy cho showbiz nữa"
import json
import re

def clean_event_data(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = []

    for entry in data:
        # 1. Kiểm tra xem content có phải là chuỗi JSON lỗi không
        raw_content = entry.get("content", "")
        
        # Dấu hiệu của chuỗi JSON lỗi là bắt đầu bằng { và chứa nhiều dấu \"
        if isinstance(raw_content, str) and raw_content.strip().startswith('{'):
            try:
                # Thử parse chuỗi JSON lồng bên trong
                nested_data = json.loads(raw_content)
                
                # Cập nhật lại các trường chính từ dữ liệu lồng
                # Chỉ lấy đoạn văn bản mô tả sự kiện thực sự
                entry["content"] = nested_data.get("content", entry["content"])
                
                # Nếu actor_related chính đang rỗng hoặc lỗi, lấy từ dữ liệu lồng
                if not entry.get("actor_related") or len(entry["actor_related"]) == 0:
                    entry["actor_related"] = nested_data.get("actor_related", [])
                
                # Đồng bộ thêm các trường khác nếu thiếu
                if not entry.get("time_event"):
                    entry["time_event"] = nested_data.get("time_event", "")
                if not entry.get("ten_su_kien"):
                    entry["ten_su_kien"] = nested_data.get("ten_su_kien", "")

            except json.JSONDecodeError:
                # Nếu lỗi format quá nặng (thiếu ngoặc, dư ký tự lạ), dùng Regex để cứu
                print(f"Cảnh báo: ID {entry.get('id_content')} lỗi JSON nặng, đang cứu bằng Regex...")
                
                # Tìm đoạn text nằm giữa "content": " và ", "actor_related"
                content_match = re.search(r'\"content\":\s*\"(.*?)\",\s*\"actor_related\"', raw_content)
                if content_match:
                    entry["content"] = content_match.group(1).replace('\\"', '"')
                
                # Tìm mảng actor_related bằng regex nếu cần (phức tạp hơn)
                # Tạm thời giữ nguyên hoặc log lại để xử lý tay ca này

        # 2. Chuẩn hóa lại mảng actor_related (loại bỏ nếu rác)
        if isinstance(entry.get("actor_related"), str):
             try:
                 entry["actor_related"] = json.loads(entry["actor_related"])
             except:
                 entry["actor_related"] = []

        cleaned_data.append(entry)

    # Xuất ra file mới sạch sẽ
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=4)
    
    print(f"Xong! Đã xử lý {len(cleaned_data)} sự kiện. File sạch: {output_file}")

# Chạy script
if __name__ == "__main__":
    # Thay 'raw_database.json' bằng file của bạn
    clean_event_data('showbiz.json', 'showbiz1.json')