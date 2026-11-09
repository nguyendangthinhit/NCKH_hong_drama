# Lọc sự kiện theo nguồn

Cập nhật 06/11/2026. Sửa lỗi hai tab Facebook/Tin tức cùng hiện 85 sự kiện.

## Hành vi

- `getPaginatedPosts(platform, ...)` và `getLatestPostsByPlatform(platform, ...)` gửi tham số `platform` xuống `/api/events`.
- Backend áp dụng bộ lọc nguồn cùng danh mục/từ khóa **trước COUNT, LIMIT và OFFSET**, nên tổng số và số trang thuộc đúng nguồn.
- Nguồn không phân biệt hoa/thường, bỏ khoảng trắng; alias `fb` được chuẩn hóa thành `facebook`.
- Không truyền nguồn (`null` ở client) thì giữ mọi sự kiện, phục vụ `/events` và dải Sự kiện mới nhất.
- Chỉ thêm `platform` vào API danh sách; URL chi tiết và dữ liệu phân tích không đổi.

## Sửa nhãn dữ liệu cũ

Builder cũ đặt `platform='news'` cho toàn bộ 85 dòng. Đã cập nhật `build_db.py` dùng `platforms.py`:

1. Ưu tiên metadata nền tảng rõ ràng từ dữ liệu gốc/API, bỏ giá trị rỗng hoặc `unknown` khi tìm metadata thay thế.
2. Nếu chưa có metadata, nhận diện nền tảng từ host của liên kết nguồn hợp lệ đầu tiên.
3. Nếu không có link, dùng `source_url` trong `data/raw/data_web.json`.
4. Nhận diện Facebook/YouTube/TikTok/Threads/Instagram; website còn lại thuộc `news`. Không đủ căn cứ thì `unknown`.

Đây là **nguồn chính** của sự kiện, không phải phân loại lại mọi liên kết tham khảo. Với dữ liệu hiện có, các nguồn đã đối chiếu cho kết quả:

| Nhóm | Số sự kiện | Phân trang hiện tại |
|---|---:|---|
| Facebook | 48 | 5 trang × tối đa 10 mục |
| Tin tức | 37 | 4 trang × tối đa 12 mục |
| Tất cả | 85 | Giữ mọi nguồn |

Hai tập Facebook/Tin tức không trùng ID, hợp lại đúng 85 ID. Hai sự kiện không có link trong SQLite được nhận diện qua URL báo ở dữ liệu gốc. Một URL Tiền Phong có lỗi scheme `hhttps`; classifier chỉ dùng host để nhận diện nguồn, không sửa URL lưu trữ. Số lượng trên là kết quả phân loại theo các liên kết hiện có, không phải khẳng định đã phục hồi đúng mọi nhãn lịch sử của bản web cũ.

Đã chạy `repair-platforms.py --apply`, chỉ thay **48 ô `platform`: news → facebook**. Toàn bộ trường còn lại của sự kiện và bảng nhân vật khớp bản sao lưu; SQLite integrity check đạt.

Bản sao lưu trước sửa: `_tmp/events-before-platform-fix-20261106T152823046491Z.db`.

Có thể xem trước sửa nhãn legacy bằng lệnh sau tại backend; mặc định chỉ đọc:

```powershell
.\.venv\Scripts\python.exe repair-platforms.py
```

`--apply` tạo bản sao lưu SQLite trước khi cập nhật, không dựng lại DB hoặc tải lại ảnh. Lần này không chạy `build_db.py` để dựng lại dữ liệu.

## Chạy và kiểm tra

Khởi động lại backend đang chạy để nạp tham số `platform` mới, rồi tải lại frontend. Ví dụ kiểm tra `GET /api/events?platform=facebook&per_page=10` trả `total=48`, `total_pages=5`; `platform=news&per_page=12` trả `total=37`, `total_pages=4`.

Tại backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tại frontend:

```powershell
node --test tests/platform-filter.test.mjs tests/latest-events.test.mjs tests/redesign.test.mjs tests/event-analysis.test.mjs
npm.cmd run build
```

Kiểm tra gồm lọc trước phân trang/tính tổng, nguồn không trùng, mọi nguồn/null, nguồn mới, bộ lọc kết hợp, request hủy, nhận diện nguồn và metadata ưu tiên. Nhãn/icon nguồn không dùng thuộc tính kế thừa JavaScript (`constructor`, `__proto__`).

Kết quả: **34/34 kiểm thử frontend, 9/9 kiểm thử backend**, build production đạt. Chạy lại chế độ xem trước sửa nhãn sau cập nhật cho `changed=0`.

Kiểm tra Edge headless với API/SQLite thật đạt 7 nhóm: API tổng/tách nguồn; mọi trang Facebook; mọi trang Tin tức; hợp ID trên giao diện; preview trang chủ/danh sách chung; tìm kiếm header xóa trắng; mobile. Kết quả và ảnh tạm ở `_tmp/platform-filter-browser-results.json`, `_tmp/platform-facebook.png`, `_tmp/platform-news.png`.
