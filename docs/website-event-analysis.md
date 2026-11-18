# Phân tích bình luận trên trang sự kiện

Cập nhật: 06/11/2026. Phạm vi: frontend `serving/web_v2/frontend`.

## Luồng dữ liệu

Trang `/events/:id` tải thông tin sự kiện từ FastAPI như trước. Khối phân tích tải độc lập từ summary JSON trên GitHub, theo cùng nguồn mà Dashboard dùng. Không chạy lại mô hình khi mở trang và không cần chạy ứng dụng Dashboard riêng.

1. `pages/Event_detail/event-detail-content.jsx` đặt khối “Phân tích dư luận” sau nội dung/nhân vật. Component được tải qua `React.lazy` để không đưa thư viện biểu đồ vào phần giao diện chính ngay từ đầu.
2. `services/event-analysis-api.js` chọn thư mục theo tiền tố mã sự kiện và tải JSON. Kiểm tra mã trong JSON khớp sự kiện trước khi hiển thị.
3. `utils/normalize-event-analysis.js` chuyển hai schema về cấu trúc dùng chung cho giao diện.
4. `components/Event_analysis/` hiển thị biểu đồ, bảng số liệu và diễn giải nếu có. Mục bình luận minh họa đã được bỏ khỏi giao diện theo yêu cầu.

## Cấu hình nguồn

Mặc định `VITE_ANALYSIS_BASE` là:

```text
https://raw.githubusercontent.com/nguyendangthinhit/NCKH_hong_drama/main/data
```

Các đường dẫn nối tiếp:

```text
processed/process_education/analyzed_dataa/summary/{eventId}.json
processed/process_showbiz/analyzed_data/summary/{eventId}.json
```

Biến này là URL công khai, không phải secret. Có thể đổi trong môi trường frontend; khởi động lại dev server hoặc build lại khi đổi cấu hình. Nếu sau này chuyển sang API, thay service mà không phải viết lại component biểu đồ.

Giao diện không hiển thị dòng “Kết quả phân tích đã lưu” hoặc liên kết JSON nguồn. Tuy nhiên, trình duyệt vẫn tải JSON trực tiếp từ GitHub và URL có thể được xem trong Network. Việc bỏ liên kết chưa hạn chế quyền truy cập dữ liệu. Nếu chỉ cho người dùng xem phần tổng hợp, cần chuyển việc đọc dữ liệu sang backend, chỉ trả các trường được phép và hạn chế truy cập tại kho dữ liệu gốc; không đặt token riêng tư trong frontend.

Đã xác minh hai URL `education_001` và `showbiz_001` trả HTTP 200, mã sự kiện khớp và header CORS cho phép truy cập tại thời điểm triển khai. Điều này không bảo đảm mọi file đều tồn tại hoặc dịch vụ luôn sẵn sàng.

## Ý nghĩa số liệu

- Giáo dục: đọc `comment_counts`, loại `rác` khỏi mẫu số, hiển thị phân bố lập trường. Diễn giải lấy từ `analysis` theo từng nhãn.
- Showbiz: đọc `emotion_stats`, hiển thị phân bố cảm xúc. `total_comments` là tổng bình luận hợp lệ theo pipeline hiện tại.
- Nếu tổng hợp lệ lớn hơn tổng các nhãn, phần chênh lệch là “Chưa phân loại”, được đưa vào cả biểu đồ và bảng. Không gọi phần này là rác.
- Tỷ lệ được tính lại từ số đếm, cùng mẫu số trên biểu đồ và bảng; sai số tổng tỷ lệ có thể xuất hiện khi làm tròn một chữ số thập phân.
- Không có diễn giải không làm mất số đếm. Kết luận rỗng được ẩn.
- Summary nguồn có thể chứa bình luận được chọn; website không hiển thị phần trích dẫn bình luận.
- Không lấy dữ liệu tổng của lĩnh vực thay cho dữ liệu sự kiện. Không tạo nhận định hoặc thời điểm cập nhật giả khi nguồn thiếu thông tin.

## Trạng thái và lỗi

- Chờ dữ liệu: thông báo tải riêng trong khối phân tích.
- HTTP 404 hoặc loại mã chưa hỗ trợ: thông báo chưa có phân tích trên nguồn hiện tại; cho kiểm tra lại.
- Mất mạng, HTTP lỗi khác, JSON sai, mã sai hoặc thống kê không hợp lệ: thông báo lỗi và nút thử lại.
- Quá 15 giây: hủy yêu cầu và cho thử lại.
- Đổi sự kiện hoặc rời trang: hủy yêu cầu cũ, không giữ biểu đồ của sự kiện trước.
- Thông tin sự kiện và nguồn tham khảo vẫn hiển thị khi khối phân tích thiếu/lỗi.

404 cũng có thể do đường dẫn/repository cấu hình sai hoặc không truy cập được; cần kiểm tra `VITE_ANALYSIS_BASE` trước khi kết luận pipeline chưa tạo kết quả.

Tại lần khảo sát local: có 20 summary Giáo dục và 29 summary Showbiz khớp mã sự kiện trong DB; 36/85 sự kiện chưa có summary local. Không dùng số liệu dự phòng để lấp các trường hợp này.

## Kiểm tra

Tại `serving/web_v2/frontend`:

```powershell
npm.cmd install
node --test tests/event-analysis.test.mjs
npm.cmd run build
```

Test bao phủ schema Giáo dục/Showbiz, mẫu số không gồm rác, phần chưa phân loại, nhãn mới/Unicode, ví dụ thiếu diễn giải, ID sai, toàn bộ summary local, HTTP 404/lỗi/JSON sai, hủy/timeout và render bảng/diễn giải mà không hiển thị bình luận minh họa.

Kết quả lần triển khai: 10/10 test đạt; production build thành công. Kiểm tra hồi quy API/render của trang chi tiết cũng đạt. Chưa kiểm thử tương tác hoặc bố cục biểu đồ bằng trình duyệt thật.

Khi kiểm thử bằng trình duyệt, mở `/events/education_001`, `/events/showbiz_004` và một sự kiện chưa có summary. Kiểm tra biểu đồ/bảng, phần chưa phân loại, không hiển thị liên kết JSON nguồn, đổi sự kiện, thử lại và màn hình nhỏ. Render phía server không thay thế kiểm thử tương tác hoặc kích thước biểu đồ trên trình duyệt.
