import json
import os

# Đường dẫn tới file input và output
input_file = os.path.join(os.path.dirname(__file__), 'data', 'education.json')
output_file = os.path.join(os.path.dirname(__file__), 'data', 'output', 'showbiz_sukien.json')

# Đảm bảo thư mục output tồn tại
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Đọc file education.json
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Trích xuất chỉ ba trường cần thiết
extracted_data = []
for item in data:
    extracted_item = {
        'id_content': item.get('id_content', ''),
        'ten_su_kien': item.get('ten_su_kien', ''),
        'content': item.get('content', '')
    }
    extracted_data.append(extracted_item)

# Lưu vào file showbiz_sukien.json
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(extracted_data, f, ensure_ascii=False, indent=2)

print(f"✓ Đã trích xuất {len(extracted_data)} bản ghi")
print(f"✓ Lưu kết quả vào: {output_file}")
