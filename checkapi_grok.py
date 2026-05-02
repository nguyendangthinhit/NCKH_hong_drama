import requests

def check_grok_api(file_path):
    # Endpoint mẫu để test (thường là lấy danh sách model hoặc chat completion)
    url = "https://api.xai.re/v1/models"
    
    try:
        with open(file_path, 'r') as file:
            api_keys = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file {file_path}")
        return

    print(f"🚀 Đang kiểm tra {len(api_keys)} API keys...\n")
    print(f"{'STT':<5} | {'API Key':<20} | {'Trạng thái':<10} | {'Ghi chú'}")
    print("-" * 60)

    for i, key in enumerate(api_keys, 1):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Gửi request đơn giản để check quyền hạn
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                status = "✅ LIVE"
                note = "Hoạt động tốt"
            elif response.status_code == 401:
                status = "❌ DIE"
                note = "Sai key hoặc hết hạn"
            else:
                status = "⚠️ LỖI"
                note = f"HTTP {response.status_code}"
                
        except Exception as e:
            status = "⚠️ LỖI"
            note = str(e)

        # Hiển thị kết quả (rút gọn key để bảo mật)
        short_key = f"{key[:7]}...{key[-4:]}" if len(key) > 15 else key
        print(f"{i:<5} | {short_key:<20} | {status:<10} | {note}")

if __name__ == "__main__":
    check_grok_api("api_grok.txt")