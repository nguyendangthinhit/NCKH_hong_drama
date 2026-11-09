# Website web_v2

Giao diện trang chủ đã chuyển theo mẫu Stitch, giữ luồng dữ liệu/điều hướng cũ và chatbot. Xem [cấu trúc giao diện và kiểm thử hồi quy](../../docs/website-interface-redesign.md).

Đã sửa bộ lọc nguồn và nhãn legacy: **48 Facebook + 37 Tin tức = 85 sự kiện**, hai tab không trùng ID. Sau khi cập nhật mã cần khởi động lại backend để nạp bộ lọc `platform`. Xem [quy tắc phân nguồn, sao lưu và kiểm thử](../../docs/website-source-filtering.md).

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

## Đọc chi tiết sự kiện

Trang chủ có khối **Sự kiện mới nhất** từ mọi nguồn API cung cấp. **Xem tất cả** mở `/events`, hiển thị mới đến cũ với tìm kiếm, lọc nguồn và phân trang. Thứ tự hiện dựa trên `time_event` (ngày sự kiện); dữ liệu chưa có ngày xuất bản hoặc thời điểm hệ thống ghi nhận. Nhãn nguồn lấy từ `platform`, hỗ trợ cả nguồn bổ sung sau này.

Ô tìm kiếm trên header cũng mở `/events` khi nhấn **Enter** hoặc **kính lúp**, kèm từ khóa trong `?q=`. Trang danh sách kế thừa font Facebook/Tin tức và giữ draft nhập riêng để hỗ trợ bộ gõ tiếng Việt.

- Bấm tiêu đề, ảnh hoặc **Xem chi tiết** trên thẻ để mở `/events/:id` trong website.
- Trang chi tiết lấy dữ liệu từ API hiện có `GET /api/event/{id_content}`, hiển thị nội dung, nhân vật, thời gian sự kiện và nguồn tham khảo khi có.
- Chọn **Xem nguồn** trong trang chi tiết để mở bài viết gốc ở tab mới. Các link nguồn ghi rõ trên thẻ vẫn có thể mở trực tiếp.
- Trang có trạng thái tải, không tìm thấy sự kiện và lỗi kết nối với nút thử lại. Mở URL chi tiết trực tiếp không cần đi qua trang chủ.
- Khi triển khai hosting tĩnh, cấu hình SPA fallback để `/events/...` trả về `index.html` khi tải lại hoặc mở URL trực tiếp.

## Phân tích bình luận theo sự kiện

Trang chi tiết có khối **Phân tích dư luận**: biểu đồ, bảng số lượng/tỷ lệ và diễn giải khi có. Dữ liệu summary được lấy từ GitHub như Dashboard; không cần chạy Dashboard riêng. Khối này có trạng thái tải, thiếu dữ liệu, lỗi và thử lại, độc lập với phần thông tin sự kiện.

Chạy `npm.cmd install` tại thư mục frontend để cài Recharts sau khi cập nhật mã. Có thể cấu hình nguồn bằng `VITE_ANALYSIS_BASE` theo `.env.example`. Xem [luồng dữ liệu, quy tắc tính tỷ lệ và hướng dẫn kiểm thử](../../docs/website-event-analysis.md).



    


