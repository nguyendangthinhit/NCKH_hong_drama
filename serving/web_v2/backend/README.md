# Backend web_v2

API FastAPI đọc dữ liệu từ `events.db` trong thư mục này. Giữ file dữ liệu hiện có khi chạy local.

## Chạy local (PowerShell)

```powershell
cd D:\py\git\NCKH_hong_drama\serving\web_v2\backend
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

Kiểm tra dữ liệu tại <http://127.0.0.1:8001/api/stats>; xem Swagger tại <http://127.0.0.1:8001/docs>.

Giữ terminal mở; nhấn `Ctrl+C` để dừng. Chạy [frontend](../frontend/README.md) trong terminal khác.

## Cài đặt lần đầu

Cần Python (dự án dùng Python 3.11). Nếu chưa có `.venv` và dependencies:

```powershell
cd D:\py\git\NCKH_hong_drama\serving\web_v2\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Sau đó chạy lệnh khởi động ở trên. Nếu thiếu `events.db`, API dữ liệu trả lỗi `503`; cần chuẩn bị cơ sở dữ liệu trước khi dùng website.

Xem [hướng dẫn chạy cả website](../README.md).
