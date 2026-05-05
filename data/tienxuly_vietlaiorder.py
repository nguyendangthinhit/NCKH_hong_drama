import os
import json
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# 1. Danh sách các API Key (thay bằng keys của bạn)
# Lưu ý: giữ an toàn cho các key — không commit public nếu không muốn lộ key.
API_KEYS = [

]

# 2. Lớp quản lý và xoay vòng API Key
class APIKeyManager:
    def __init__(self, keys):
        self.keys = keys
        self.current_index = 0
        self.model = self._init_model()

    def _init_model(self):
        """Thiết lập lại cấu hình `genai` với API key hiện tại và trả về model.

        Gọi lại khi xoay key để tránh lỗi rate-limit trên một key.
        """
        genai.configure(api_key=self.keys[self.current_index])
        # Trả về object model để gọi generate_content
        return genai.GenerativeModel('gemini-2.5-flash')

    def get_model(self):
        """Trả về model hiện tại đã được cấu hình với API key hiện tại."""
        return self.model

    def rotate(self):
        """Chuyển sang API Key tiếp theo trong danh sách"""
        self.current_index = (self.current_index + 1) % len(self.keys)
        print(f"🔄 [Rotate API] Đã chuyển sang API Key ở vị trí {self.current_index + 1}/{len(self.keys)}")
        # Cập nhật model sử dụng key mới
        self.model = self._init_model()
        return self.model

# Khởi tạo trình quản lý API
key_manager = APIKeyManager(API_KEYS)

def check_noise_batch(texts, batch_size=20):
    """Gửi các bình luận theo batch cho model Gemini và trả về flags boolean.

    Trả về list cùng độ dài với `texts` (True nếu là noise, False nếu hợp lệ).
    """
    is_noise_results = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        # Prompt hướng dẫn rõ ràng: chỉ trả về JSON array các boolean, KHÔNG giải thích.
        prompt = f"""
        Bạn là một chuyên gia làm sạch dữ liệu. Dưới đây là danh sách các bình luận trên Facebook.
        Nhiệm vụ: Xác định bình luận nào là "rác" (noise).
        Bình luận rác gồm:
        1) Chỉ tag tên người khác (ví dụ: "Nguyễn Văn A").
        2) Ký tự vô nghĩa hoặc quá ngắn ("hhh", "ok", ".").
        3) Chỉ chứa emoji ("😍", "👍").

        Chỉ trả về một mảng JSON các giá trị boolean tương ứng (true nếu là rác, false nếu hợp lệ).
        Ví dụ: [true, false, true]

        Danh sách bình luận:
        {json.dumps(batch, ensure_ascii=False)}
        """

        # Số lần thử lại tối đa cho mỗi batch (thử nhiều lần nếu cần để xoay key khi bị limit)
        max_retries = len(API_KEYS) * 2

        for attempt in range(max_retries):
            model = key_manager.get_model()
            try:
                response = model.generate_content(prompt)
                # Model có thể trả kèm ```json```, nên làm sạch trước khi parse
                cleaned_text = response.text.strip().strip('```json').strip('```')
                batch_results = json.loads(cleaned_text)

                if len(batch_results) == len(batch):
                    is_noise_results.extend(batch_results)
                else:
                    # Nếu API trả thiếu phần tử, an toàn nhất là giữ lại (False)
                    print(f"⚠️ [Cảnh báo] API trả về thiếu dữ liệu. Mặc định giữ lại.")
                    is_noise_results.extend([False] * len(batch))

                break

            except ResourceExhausted:
                # Khi gặp rate limit, xoay sang key tiếp theo và thử lại
                print(f"⚠️ [Rate Limit] Key bị limit (Lần thử {attempt + 1}/{max_retries}). Đang xoay key...")
                key_manager.rotate()

                # Nếu đã thử hết tất cả key thì chờ lâu hơn trước khi lặp lại
                if (attempt + 1) % len(API_KEYS) == 0:
                    print(f"⏳ [Wait] Tất cả các key đều đang nóng, đợi 10 giây...")
                    time.sleep(10)
                else:
                    time.sleep(1)

            except Exception as e:
                # Bắt mọi lỗi khác: tránh mất data bằng cách đánh dấu batch là hợp lệ (False)
                print(f"❌ [Lỗi API khác] {e}. Đánh dấu batch này là hợp lệ (False) để không mất data.")
                is_noise_results.extend([False] * len(batch))
                break

        # Nghỉ nhẹ giữa các batch để giảm khả năng bị limit
        time.sleep(1)

    return is_noise_results

def process_directory(input_dir, output_dir):
    """Duyệt các file JSON trong `input_dir`, lọc bình luận rác và lưu sang `output_dir`.

    - Bỏ qua file đầu ra nếu đã tồn tại (để không xử lý lại)
    - Nếu file không có comments, vẫn tạo bản sao trống ở thư mục đích
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".json"):
            # --- TÍNH NĂNG MỚI: BỎ QUA NẾU FILE ĐÃ TỒN TẠI ---
            output_path = os.path.join(output_dir, filename)
            if os.path.exists(output_path):
                print(f"⏩ Đã bỏ qua tệp: {filename} (Đã tồn tại trong thư mục đích)")
                continue
            # ------------------------------------------------

            file_path = os.path.join(input_dir, filename)
            print(f"\n🚀 Đang xử lý tệp: {filename}...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            all_comments = data.get('comments', [])
            if not all_comments:
                print(f"⚠️ Tệp {filename} không có bình luận nào. Đang tạo bản sao trống...")
                # Vẫn lưu file sang thư mục đích để lần sau script không đọc lại file rỗng này
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                continue

            texts_to_check = [cmt.get('text', '') for cmt in all_comments]
            noise_flags = check_noise_batch(texts_to_check)

            valid_comments = []
            current_order = 1

            for idx, cmt in enumerate(all_comments):
                is_noise = noise_flags[idx] if idx < len(noise_flags) else False 
                
                if not is_noise:
                    cmt['order'] = current_order
                    cmt['comment_id'] = f"cmt_{data.get('id_content', 'unknown')}_{current_order:04d}"
                    valid_comments.append(cmt)
                    current_order += 1

            data['comments'] = valid_comments

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"✅ -> Đã lưu tệp sạch tại: {output_path}. (Giữ lại {len(valid_comments)}/{len(all_comments)} comments)")

# --- CHẠY THỰC TẾ ---
input_folder = "input_clean_data" 
output_folder = "cleaned_data_input"

process_directory(input_folder, output_folder)
print("\n🎉 Hoàn tất quá trình dọn dẹp!")