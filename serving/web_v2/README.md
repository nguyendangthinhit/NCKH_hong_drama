# Website web_v2

Website React/Vite dùng API FastAPI. Mở **hai terminal PowerShell riêng**, chạy backend trước rồi frontend.

## Terminal 1: Backend

```powershell
cd D:\py\git\NCKH_hong_drama\serving\web_v2\backend
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

API: <http://127.0.0.1:8001/api/stats>. Swagger: <http://127.0.0.1:8001/docs>.

## Terminal 2: Frontend

```powershell
cd D:\py\git\NCKH_hong_drama\serving\web_v2\frontend
$env:VITE_API_BASE = 'http://localhost:8001'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở website tại <http://127.0.0.1:5173>. Biến `VITE_API_BASE` áp dụng trong terminal hiện tại, cần đặt lại khi mở terminal mới.

Giữ cả hai terminal mở; nhấn `Ctrl+C` trong từng terminal để dừng.

## Cài đặt lần đầu

Xem [backend](./backend/README.md) để tạo `.venv` và cài Python dependencies; xem [frontend](./frontend/README.md) để cài npm dependencies. Backend cần file `backend/events.db` hiện có để phục vụ dữ liệu.
