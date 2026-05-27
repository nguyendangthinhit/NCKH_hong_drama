import os
import json
import glob

def merge_json_files():
    # Khởi tạo 2 mảng rỗng để chứa data
    education_data = []
    showbiz_data = []

    # Quét toàn bộ các file .json trong thư mục hiện tại
    file_list = glob.glob("*.json")

    for filename in file_list:
        # Bỏ qua chính 2 file kết quả (nếu lỡ chạy script nhiều lần)
        if filename in ["education_fb.json", "showbiz_fb.json"]:
            continue

        try:
            # Mở và đọc file với encoding utf-8 để không lỗi font tiếng Việt
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Phân loại và gộp data dựa vào tên file
                if "education" in filename:
                    # Nếu file chứa 1 list (nhiều comment), dùng extend để gộp mảng
                    if isinstance(data, list):
                        education_data.extend(data)
                    else:
                        education_data.append(data) # Nếu chỉ có 1 object, dùng append
                
                elif "showbiz" in filename:
                    if isinstance(data, list):
                        showbiz_data.extend(data)
                    else:
                        showbiz_data.append(data)
                        
        except json.JSONDecodeError:
            print(f"⚠️ Lỗi cú pháp JSON ở file: {filename}")
        except Exception as e:
            print(f"⚠️ Lỗi không xác định ở file {filename}: {e}")

    # Ghi data đã gộp ra file mới
    with open("showbiz.json", 'w', encoding='utf-8') as f:
        json.dump(showbiz_data, f, ensure_ascii=False, indent=4)
    print(f"✅ Đã tạo showbiz.json (Tổng số: {len(showbiz_data)} bản ghi)")

    # with open("showbiz_fb.json", 'w', encoding='utf-8') as f:
    #     json.dump(showbiz_data, f, ensure_ascii=False, indent=4)
    # print(f"✅ Đã tạo showbiz_fb.json (Tổng số: {len(showbiz_data)} bản ghi)")

if __name__ == "__main__":
    print("Đang tiến hành gộp dữ liệu...")
    merge_json_files()