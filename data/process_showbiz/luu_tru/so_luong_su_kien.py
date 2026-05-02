import json

def extract_content_dict(file_path):
    try:
        # 1. Mở và đọc file JSON với định dạng utf-8
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 2. Dùng Dictionary Comprehension để tách lấy id_content và ten_su_kien
        # Cấu trúc: { key: value for item in list }
        dictt = {item['id_content']: item['ten_su_kien'] for item in data}
        
        return dictt

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file tại đường dẫn {file_path}")
    except json.JSONDecodeError:
        print("Lỗi: File JSON không đúng định dạng.")
    except KeyError as e:
        print(f"Lỗi: Thiếu trường dữ liệu {e} trong file JSON.")
    except Exception as e:
        print(f"Lỗi không xác định: {e}")

# --- CHẠY THỬ ---
file_name = 'data_web.json' # Đảm bảo file này nằm cùng thư mục với script này
result = extract_content_dict(file_name)

if result:
    # In thử 2 phần tử đầu tiên để kiểm tra
    for i, (k, v) in enumerate(result.items()):
        if i < 2:
            print(f"ID: {k} \nSự kiện: {v}\n" + "-"*30)
    
    print(f"Tổng cộng đã lấy được {len(result)} sự kiện.")