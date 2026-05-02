import requests
import json
import time

def load_keys(filepath="api.txt"):
    with open(filepath, "r") as f:
        keys = [line.strip().rstrip(",") for line in f.readlines()]
        keys = [k for k in keys if k]
    return keys

def test_key(api_key, model="gemini-2.5-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{
            "parts": [{"text": "Hi"}]
        }]
    }
    try:
        response = requests.post(url, json=body, timeout=15)
        data = response.json()

        if response.status_code == 200:
            return "✅ OK"
        elif response.status_code == 429:
            details = data.get('error', {}).get('details', [])
            retry_info = ""
            for d in details:
                if 'retryDelay' in str(d):
                    retry_info = f" | retry in: {d.get('retryDelay','?')}"
            quota_msg = data.get('error', {}).get('message', '')[:80]
            return f"⚠️  RATE LIMITED{retry_info} | {quota_msg}"
        elif response.status_code == 400:
            msg = data.get('error', {}).get('message', '')
            return f"❌ BAD REQUEST: {msg}"
        elif response.status_code == 403:
            msg = data.get('error', {}).get('message', '')
            return f"❌ FORBIDDEN: {msg}"
        elif response.status_code == 404:
            return f"❌ MODEL NOT FOUND"
        else:
            msg = data.get('error', {}).get('message', '')
            return f"❌ LỖI {response.status_code}: {msg}"
    except Exception as e:
        return f"❌ EXCEPTION: {str(e)}"

if __name__ == "__main__":
    keys = load_keys("api.txt")
    print(f"Tìm thấy {len(keys)} API keys")
    print(f"Model: gemini-2.5-flash")
    print("-" * 70)

    valid_keys = []
    rate_limited_keys = []

    for i, key in enumerate(keys):
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else key
        status = test_key(key)
        print(f"Key {i+1:2d}: {masked} → {status}")

        if "✅" in status:
            valid_keys.append(key)
        elif "RATE LIMITED" in status:
            rate_limited_keys.append(key)

        time.sleep(1)

    print("-" * 70)
    print(f"\nTổng kết:")
    print(f"  ✅ OK:           {len(valid_keys)}/{len(keys)}")
    print(f"  ⚠️  Rate Limited: {len(rate_limited_keys)}/{len(keys)}")
    print(f"  ❌ Lỗi khác:     {len(keys) - len(valid_keys) - len(rate_limited_keys)}/{len(keys)}")

    if valid_keys:
        print(f"\n✅ Keys hoạt động được ngay:")
        for k in valid_keys:
            print(f"  {k[:8]}...{k[-4:]}")

    if rate_limited_keys:
        print(f"\n⚠️  Keys bị rate limit (cần đợi reset):")
        for k in rate_limited_keys:
            print(f"  {k[:8]}...{k[-4:]}")

    # kiểm tra key trùng
key_set = set(keys)

if len(key_set) == len(keys):
    print("\n✅ Không có API trùng")
else:
    print("\n❌ Có API bị trùng")

    seen = set()
    duplicates = set()

    for k in keys:
        if k in seen:
            duplicates.add(k)
        else:
            seen.add(k)

    print("Các key trùng:")
    for k in duplicates:
        print(f"  {k[:8]}...{k[-4:]}")