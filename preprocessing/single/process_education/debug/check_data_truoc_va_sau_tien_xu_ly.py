import json
import os

def evaluate_cleaning_process(raw_file_path, cleaned_file_path, output_report_path=None):
    """
    So sánh file gốc và file đã qua xử lý để trích xuất các comment bị lọc bỏ.
    """
    try:
        # 1. Đọc dữ liệu từ file gốc (chưa xử lý)
        with open(raw_file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        # 2. Đọc dữ liệu từ file đã clean
        with open(cleaned_file_path, 'r', encoding='utf-8') as f:
            cleaned_data = json.load(f)
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file - {e}")
        return
        
    raw_comments = raw_data.get('comments', [])
    cleaned_comments = cleaned_data.get('comments', [])
    
    # 3. Tạo một Set chứa nội dung text của các comment ĐÃ ĐƯỢC GIỮ LẠI.
    # Dùng Set (tập hợp) để tra cứu siêu nhanh với độ phức tạp O(1)
    cleaned_texts = {cmt.get('text', '').strip() for cmt in cleaned_comments}
    
    filtered_out_comments = []
    
    # 4. Duyệt qua mảng gốc, nếu text không có trong Set trên -> Nó đã bị lọc bỏ
    for cmt in raw_comments:
        original_text = cmt.get('text', '').strip()
        if original_text not in cleaned_texts:
            filtered_out_comments.append(cmt)
            
    # 5. In báo cáo thống kê
    print(f"📊 THỐNG KÊ LỌC DỮ LIỆU:")
    print(f"- Tổng số comment ban đầu: {len(raw_comments)}")
    print(f"- Số comment giữ lại:      {len(cleaned_comments)}")
    print(f"- Số comment bị loại (noise): {len(filtered_out_comments)}\n")
    
    print("🗑️ DANH SÁCH CÁC COMMENT BỊ LOẠI:")
    for i, cmt in enumerate(filtered_out_comments, 1):
        text_preview = cmt.get('text', '').replace('\n', ' ') # Xóa dấu xuống dòng để in gọn hơn
        print(f"[{i:02d}] {text_preview}")
        
    # 6. (Tùy chọn) Export ra file JSON mới để Q.Huy, Thiện hoặc team dễ dàng review lại
    if output_report_path and filtered_out_comments:
        with open(output_report_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_out_comments, f, ensure_ascii=False, indent=2)
        print(f"\n📁 Đã lưu file danh sách comment bị loại tại: {output_report_path}")

# --- CÁCH SỬ DỤNG ---
# Định nghĩa đường dẫn tới file cần test (bạn thay đổi tên file cho khớp thực tế nhé)
RAW_FILE = os.path.join("input_data_test", "education_002.json")
CLEANED_FILE = os.path.join("cleaned_a", "education_002.json")
REPORT_FILE = "review_filtered_noise.json"

# Gọi hàm
evaluate_cleaning_process(RAW_FILE, CLEANED_FILE, REPORT_FILE)