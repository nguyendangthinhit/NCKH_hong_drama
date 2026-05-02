"""Đoạn code này dùng để map ID_content từ file data_web.json đến các sheet cho file google sheet"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- PHẦN 1: ĐỌC DỮ LIỆU TỪ FILE JSON (RESULT) ---
def load_json_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Tạo dictionary với Key là 'ten_su_kien' và Value là 'id_content'
        # để tra cứu ngược từ tên sự kiện ra ID.
        return {item['ten_su_kien']: item['id_content'] for item in data}
    except Exception as e:
        print(f"Lỗi khi đọc file JSON: {e}")
        return {}

# --- PHẦN 2: CẤU HÌNH GOOGLE SHEETS API ---
# 1. Cấu hình đường dẫn file JSON của bạn
PATH_TO_JSON = 'D:/py/git/NCKH_hong_drama/credential_get_link_sheet.json' # Điền tên file thật

# 2. Thiết lập quyền truy cập
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(PATH_TO_JSON, scope)
client = gspread.authorize(creds)

# --- PHẦN 3: XỬ LÝ MAPPING VÀ CẬP NHẬT DỮ LIỆU ---
def map_ids_to_sheet(sheet_name, json_mapping):
    if not json_mapping:
        print("Không có dữ liệu JSON để map.")
        return

    try:
        # 3. Mở file Google Sheet bằng Tên File (hoặc ID)
        spreadsheet = client.open("Drama 2025-Đầu 2026") # ĐIỀN TÊN FILE THẬT
        
        # 4. CHỖ CHỌN SHEET: Truy cập vào sheet cụ thể theo tên bạn truyền vào
        sheet = spreadsheet.worksheet(sheet_name)
        
        # 5. Lấy toàn bộ dữ liệu (tránh get nhiều lần làm chậm code)
        all_rows = sheet.get_all_values()
        
        # Giả sử cấu trúc cột là: A: Danh mục, B: id_content, C: Tên sự kiện
        # Ta cần lấy data bắt đầu từ hàng 2 (hàng 1 là tiêu đề)
        # Cột 'id_content' là cột thứ 2 (Index 1)
        # Cột 'Tên sự kiện' là cột thứ 3 (Index 2)
        
        updates = [] # Danh sách các ô cần cập nhật để update hàng loạt
        
        print("Đang kiểm tra và mapping dữ liệu...")
        
        # Duyệt qua các hàng từ hàng thứ 2 (Index 1)
        for i, row in enumerate(all_rows[1:], start=2):
            # Kiểm tra nếu số lượng cột không đủ (tránh lỗi index out of range)
            if len(row) < 3:
                continue
                
            id_content_on_sheet = row[1].strip() # Cột B
            event_name_on_sheet = row[2].strip() # Cột C
            
            # Nếu id_content trên sheet đang rỗng
            if not id_content_on_sheet:
                # Tra cứu tên sự kiện trong dictionary JSON
                matched_id = json_mapping.get(event_name_on_sheet)
                
                if matched_id:
                    print(f"-> Tìm thấy ID '{matched_id}' cho sự kiện: '{event_name_on_sheet[:50]}...'")
                    # Thêm vào danh sách cập nhật (Ô cần update là cột B, hàng i)
                    updates.append({
                        'range': f'B{i}', # Ví dụ: 'B2', 'B5'
                        'values': [[matched_id]]
                    })
        
        # 6. THỰC HIỆN CẬP NHẬT HÀNG LOẠT (TỐI ƯU TỐC ĐỘ)
        if updates:
            sheet.batch_update(updates)
            print(f"--- Đã cập nhật xong {len(updates)} mã id_content thành công! ---")
        else:
            print("--- Không tìm thấy sự kiện nào cần cập nhật mã ID. ---")
            
    except Exception as e:
        print(f"Có lỗi xảy ra khi làm việc với Google Sheet: {e}")

# --- PHẦN 4: CHẠY DỰ ÁN ---
# 1. Load dữ liệu mapping từ file JSON trước
file_json_data = 'data_web.json' # Điền tên file thật
mapping_data = load_json_data(file_json_data)

# 2. Chạy hàm mapping lên Google Sheet
# Thay 'Sheet1' bằng tên tab cụ thể bạn muốn truy cập
map_ids_to_sheet('Facebook', mapping_data)