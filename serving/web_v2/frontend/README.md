# Frontend web_v2

Website React/Vite. Chạy [backend](../backend/README.md) tại cổng `8001` trong terminal riêng trước.

## Chạy local (PowerShell)

```powershell
cd D:\py\git\NCKH_hong_drama\serving\web_v2\frontend
$env:VITE_API_BASE = 'http://localhost:8001'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở <http://127.0.0.1:5173>. Giữ terminal mở; nhấn `Ctrl+C` để dừng.

Cần đặt `VITE_API_BASE` mỗi khi mở terminal mới. Nếu không đặt, frontend mặc định gọi API tại cổng `8000`.

## Cài đặt lần đầu

Cần Node.js và npm. Nếu chưa cài dependencies:

```powershell
cd D:\py\git\NCKH_hong_drama\serving\web_v2\frontend
npm install
```

Xem [hướng dẫn chạy cả website](../README.md).
