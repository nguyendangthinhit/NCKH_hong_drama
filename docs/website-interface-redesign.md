# Giao diện website theo mẫu Stitch

Cập nhật: 06/11/2026. Phạm vi: `serving/web_v2/frontend`.

## Yêu cầu và bố cục

Chuyển phần trình bày theo mẫu `stitch_web_b_o_h_ng_drama/code.html` và `screen.png`, giữ các luồng website cũ, bố cục footer và toàn bộ chatbot.

- Header trắng, thanh thông tin nền tối, điều hướng và màu nhấn đỏ.
- Lưới bốn sự kiện: một tiêu điểm bên trái, một thẻ trên và hai thẻ nhỏ bên phải.
- Phần thân hai cột: Trending bên trái; theo dõi cộng đồng/Facebook/điểm tin bên phải.
- Dải Sự kiện mới nhất từ mọi nguồn, cuộn ngang có nút điều khiển và liên kết danh sách chung.
- Footer vẫn gồm thương hiệu/socials, hai nhóm liên kết và thanh bản quyền; nền đổi sang `#171717`, giữ sóng trang trí và cách xếp cột cũ.
- Dữ liệu và liên kết dùng nội dung hiện có; thương hiệu header theo ảnh người dùng yêu cầu. Không đưa số online, followers, lượt xem, video hoặc Drama Score minh họa của mẫu thành số liệu sản phẩm.

### Điều chỉnh header theo ảnh tham chiếu

Cụm thương hiệu header được đổi theo yêu cầu tiếp theo: chữ **HÓNG** trắng trên nền đỏ, **BIẾN.VN** đen/đỏ, dòng phụ “SHOWBIZ • DRAMA • MẠNG XÃ HỘI” và slogan nghiêng có vạch ngăn. `Header/header-brand.jsx` và `header-brand.module.scss` quản lý riêng phần này; các state/handler/routes của Header giữ nguyên. Nhãn thanh tối đổi thành “HOT 24/7” như mẫu.

Slogan hiện từ 1024 px như file tham chiếu. Trên mobile, thương hiệu ở hàng đầu, tìm kiếm/thông báo/đăng nhập ở hàng kế; giữ chiều cao header 184 px. Bổ sung Montserrat italic 700, không thay font toàn trang hoặc chatbot.

Đã build và chạy lại 10/10 kiểm thử giao diện. Kiểm tra Edge ở 1440, 1024, 768, 390 và 320 px: header không tràn, các nút hiển thị đủ; thử menu danh mục, link logo về trang chủ và hành vi submit tìm kiếm cũ. Kiểm tra này dùng API giả lập, không thay dữ liệu thật. Ảnh và kết quả tạm: `_tmp/header-brand-*.png`, `_tmp/header-brand-browser-results.json`.

## Các thành phần

| File/thư mục | Trách nhiệm |
|---|---|
| `pages/HomePage/` | Giữ dữ liệu tiêu điểm/sidebar; tải riêng sáu sự kiện mới nhất từ mọi nguồn |
| `pages/EventsPage/` | Trang `/events`: danh sách mới đến cũ, tìm kiếm/lọc nguồn, phân trang 12 mục |
| `components/home/featured-events` | Chọn bốn ID không trùng từ dữ liệu đã tải; thẻ mở trang chi tiết |
| `components/home/home-sidebar` | Khối cộng đồng, đủ năm mục Facebook và điểm tin |
| `components/home/follow-community` | Ba ô theo dõi Facebook/TikTok/Threads theo mẫu |
| `config/social-links.js` | URL fanpage/kênh của từng nền tảng; để trống khi chưa ra mắt |
| `components/home/latest-events-rail` | Sáu sự kiện mới nhất, ngày và nhãn nguồn; Xem tất cả tới `/events` |
| `services/latest-events-api.js` | Gom mọi trang/mọi nguồn từ API, xếp ngày giảm dần trước khi giới hạn |
| `hooks/use-latest-events.js` | Dùng chung dữ liệu mới nhất, tải/lỗi/thử lại và hủy request khi rời trang |
| `hooks/use-event-filters.js` | Draft tìm kiếm độc lập, xử lý IME, đồng bộ URL và bộ lọc/phân trang |
| `utils/event-sources.js` | Nhãn nguồn có sẵn, giữ tên nguồn mới và xử lý thiếu nguồn |
| `components/TrendingSection/` | Giữ hai tab, request/cache theo lĩnh vực và thứ hạng theo vị trí; đổi sang danh sách |
| `components/PostCard/` | Giữ link chi tiết/nguồn, số bình luận, status; layout `row`, `rail`, `reference`, tùy chọn hiện ngày/ẩn HOT cho tin mới |
| `components/Header/` | Routes/danh mục, dropdown bàn phím, tìm kiếm chung mở `/events?q=...` |
| `components/Footer/` | Giữ bố cục/nội dung, thay palette và màu sóng |
| `styles/theme/_light.scss` | Nền xám, surface trắng, viền trung tính và điểm nhấn đỏ |

Giữ các endpoint API hiện có. Header/Footer ở ngoài `Routes` như trước; các URL `/`, `/facebook`, `/news`, `/events/:id` giữ nguyên, thêm `/events` cho danh sách chung. Không thêm backend, tài khoản hoặc database.

### Gắn link cộng đồng

Theo yêu cầu tiếp theo, khối “Khám phá cùng Hóng” được thay bằng “Theo dõi hội hóng biến”: Facebook màu xanh, TikTok nền tối và Threads gradient cam như mẫu. Không hiển thị số người theo dõi minh họa.

Ô Facebook đã gắn fanpage `https://www.facebook.com/profile.php?id=61579650250828`, hiển thị “Theo dõi” và mở tab mới. TikTok/Threads vẫn để trống, hiển thị “Sắp ra mắt”.

Khi tạo xong fanpage/kênh, sửa trường `href` tương ứng trong `serving/web_v2/frontend/src/config/social-links.js`, ví dụ `href: 'https://www.facebook.com/ten-trang-cua-ban'`. Dùng địa chỉ công khai đầy đủ bắt đầu bằng `https://`. Có URL thì ô trở thành liên kết mở tab mới (`noopener noreferrer`); chưa có URL thì hiển thị “Sắp ra mắt” và không điều hướng. Cập nhật xong cần build/deploy lại frontend như các thay đổi cấu hình mã nguồn khác.

Thay đổi này chỉ thay khối shortcut trên trang chủ. Các lối vào danh sách và danh mục trong header, dữ liệu sự kiện, khối Tin hot Facebook và chatbot giữ nguyên. Đã build thành công và chạy lại 10/10 kiểm thử giao diện.

### Sự kiện mới nhất từ mọi nguồn

Khối cuối trang chủ là **Sự kiện mới nhất**, lấy mọi nền tảng API trả về: Facebook, tin tức và các nguồn bổ sung sau này. Service gom hết các trang API (200 mục/request), gộp ID không trùng, xếp toàn bộ theo `time_event` giảm dần rồi lấy sáu mục. Không lọc riêng `news`, không giới hạn cứng 9.999 sự kiện và không xếp theo số bình luận. Dải này có ngày/nhãn nguồn, không có HOT. Tiêu điểm, Trending, Facebook và Điểm tin nổi bật giữ nguồn/cách xếp trước đó.

Dữ liệu hiện có chưa có thời điểm xuất bản hay cập nhật bài viết, nên “mới nhất” căn cứ **ngày sự kiện**. Hỗ trợ ngày ISO có/không có số 0 đầu, tháng `YYYY-MM` và tháng chưa rõ ngày `YYYY-MM-xx`; tháng chưa rõ ngày đứng sau các ngày xác định trong cùng tháng. Ngày trống/không hợp lệ đứng cuối, trùng ngày dùng ID để giữ thứ tự ổn định. Không gán ngày hiện tại cho dữ liệu thiếu ngày.

**Xem tất cả** mở `/events`, không chuyển sang trang Tin tức. Danh sách chung giữ thứ tự mới → cũ, có tìm kiếm, lọc nguồn động và 12 sự kiện/trang. `q`, `source`, `page` nằm trong URL để mở trực tiếp hoặc quay lại từ chi tiết vẫn giữ bộ lọc/trang. Đổi bộ lọc reset trang 1; URL trang vượt giới hạn được chỉnh về trang hợp lệ. Có trạng thái tải/rỗng/lỗi và thử lại. Nhãn nguồn mới dùng tên `platform` từ API; thiếu nguồn hiện “Chưa rõ nguồn”, không bị gắn nhãn Tin tức.

`getPaginatedPosts` chuyển `AbortSignal` và tham số `platform` tới backend; `null` vẫn lấy mọi nguồn. Đã sửa backend lọc trước phân trang và sửa nhãn legacy bằng liên kết đối chiếu: 48 Facebook, 37 Tin tức, tổng 85. Khối mới nhất có state riêng. Xem [chi tiết sửa bộ lọc nguồn và sao lưu DB](website-source-filtering.md).

### Font và nhập tìm kiếm

Trang `/events` kế thừa font giống hai trang Facebook/Tin tức: tiêu đề dùng font body Spline Sans/Noto Sans, cỡ 28 px/weight 900; ô tìm kiếm dùng Inter 14,4 px. Font trong PostCard vẫn giống thẻ ở các trang cũ.

Ô tìm kiếm danh sách giữ draft cục bộ thay vì lấy trực tiếp giá trị URL ở mỗi phím. URL cập nhật sau 250 ms hoặc khi rời ô; trong lúc IME đang ghép dấu thì giữ kết quả/URL ổn định đến khi kết thúc composition. Cập nhật URL của chính ô nhập không ghi đè draft/con trỏ. Nút Xóa bộ lọc luôn giữ chỗ trong toolbar để ô nhập không bị co khi bắt đầu gõ. Vòng focus nằm ở khung tìm kiếm, không có hai đường viền chồng lên nhau.

Tìm kiếm chung trên header: Enter hoặc nút kính lúp mở `/events?q=<từ khóa đã mã hóa>`, không giữ bộ lọc nguồn/trang trước đó. Sau khi gửi, ô header xóa trắng; từ khóa vẫn giữ trong URL và ô tìm kiếm của trang kết quả. Chuỗi trống mở toàn bộ `/events`. Chặn submit khi Enter đang dùng để hoàn tất IME; ô header giữ draft riêng để điều hướng URL không ghi đè chữ đang gõ. Trang danh sách tìm trong tiêu đề/chủ đề/nhãn nguồn.

Hai trang Facebook/Tin tức, lọc `?cat=`, phân trang 10/12 mục và reset trang giữ nguyên mã xử lý. Đăng nhập/thông báo vẫn giữ trạng thái giao diện như trước.

## CSS và chatbot

Header cố định có chiều cao 150 px desktop, 184 px ở màn hình tối đa 767 px. Biến `--site-header-height` được dùng để chừa khoảng trống tương ứng ở các trang, tránh nội dung bị che.

Montserrat/Merriweather dùng trong header/thẻ và các khối trang chủ. Trang danh sách chung kế thừa font các trang danh sách cũ như mô tả trên. Không sửa `main.jsx`, `global.scss` hoặc biến font dùng chung để tránh đổi chatbot. Không đặt transform/filter/overflow trên gốc ứng dụng.

Các file `Chatbot.jsx`, `Chatbot.module.scss`, `datamock.js`, service phân tích, mã xử lý hai trang danh sách cũ, main và global style được đối chiếu SHA-256 với baseline và giữ nguyên. App thêm route `/events`; API danh sách bổ sung tùy chọn hủy request và lọc nền tảng. Kết nối n8n, cookie định danh, mở/đóng và gửi/nhận của chatbot giữ nguyên.

## Dữ liệu ảnh và trạng thái

Dùng `imageUrl` hiện có của từng sự kiện; ảnh thiếu hoặc tải lỗi dùng nền/icon dự phòng. Không dùng ảnh tin giả trong mẫu thay thế cho sự kiện thật. Các vấn đề chất lượng nguồn/ảnh đã có trong dữ liệu không được sửa trong đợt trình bày này.

Giữ trạng thái tải/rỗng và các nguồn tham khảo trực tiếp. Trang chi tiết tiếp tục có phân tích độc lập; không hiển thị lại bình luận minh họa hoặc liên kết JSON nguồn đã bỏ trước đó.

## Kiểm tra

Tại thư mục frontend:

```powershell
node --test tests/redesign.test.mjs
node --test tests/latest-events.test.mjs
node --test tests/platform-filter.test.mjs
node --test tests/event-analysis.test.mjs
npm.cmd run build
```

`redesign.test.mjs` kiểm tra Header/Footer, link chi tiết và nguồn trong bốn layout PostCard, nhãn nguồn động, lưới bốn tin, đủ mục Facebook, dải sự kiện, tải/rỗng/lỗi và phân trang. `latest-events.test.mjs` kiểm tra gom nhiều trang/nhiều nền tảng, ngày thiếu/lỗi, giới hạn sau sắp xếp, lỗi trang sau, hủy request và ID trùng. Kiểm thử phân tích hiện có tiếp tục kiểm tra số đếm, mẫu số, lỗi và trạng thái dữ liệu.

Kiểm tra trình duyệt cần bao gồm desktop/mobile, dropdown danh mục, đổi tab Trending, tìm kiếm/lọc/phân trang, mở và tải lại chi tiết, nút dải cuộn, nguồn tham khảo và chatbot. Thử gửi chatbot bằng phản hồi giả lập để không ghi thêm hội thoại kiểm thử lên workflow thật.

### Kết quả thực hiện

- Build Vite production: đạt.
- Bốn bộ kiểm thử frontend: **34/34 đạt**, backend lọc nguồn **9/9 đạt**. Cache Vite của mỗi bộ được tách khỏi server phát triển; không mở WebSocket trong kiểm thử SSR.
- Edge headless kiểm tra bản build với API giả lập nhiều nguồn: **11 nhóm kiểm tra đạt**, không có ngoại lệ JavaScript. Dữ liệu kiểm thử không ghi vào database hoặc workflow thật.
- Desktop 1440 × 1000 và mobile 390/320 × 844: danh sách mới không tràn ngang, nội dung không bị header cố định che.
- Đã thử dải sáu sự kiện nhiều nguồn, Xem tất cả `/events`, thứ tự ngày trên từng trang, mở/tải lại URL trang 2, chi tiết/quay lại, lọc TikTok/nguồn mới/thiếu nguồn, tìm kiếm rỗng, xóa bộ lọc, trang URL vượt giới hạn và lỗi/thử lại.
- Đã mô phỏng IME ghép “bình”, chèn chữ ở giữa từ và chờ đồng bộ URL: nội dung/con trỏ/độ rộng ô giữ đúng. So sánh computed font tiêu đề/input giữa `/events`, `/facebook`, `/news`: khớp. Đã thử header Enter/kính lúp, nhiều truy vấn liên tiếp, ký tự `& / # ?` và chuỗi trắng.
- Đã thử đổi tab Trending, nút cuộn Tin tức, mở/tải lại URL chi tiết và quay về danh sách; kiểm tra nguồn và vùng phân tích.
- Đã thử tìm kiếm có/không có kết quả, xóa tìm kiếm, trang 2 và reset về trang 1 tại Facebook (10 mục/trang) và Tin tức (12 mục/trang); lọc danh mục và menu mobile.
- Chatbot mở/gửi/nhận/đóng đạt với phản hồi chặn tại trình duyệt; giữ gradient xanh, nút 65 px, font Inter và payload `message`/`userId`. Kết quả này xác nhận giao diện và luồng client; không kiểm chứng trạng thái workflow n8n thật.
- Đối chiếu SHA-256: 8/10 file baseline giữ nguyên, gồm toàn bộ chatbot. Hai file thay đổi có chủ đích là App (route mới) và API (tùy chọn hủy request).

Ảnh/báo cáo danh sách chung nằm trong `_tmp/latest-events-*.png` và `_tmp/latest-events-browser-results.json`; kết quả các luồng cũ nằm trong `_tmp/redesign-*`. Preview dùng cổng riêng để không ảnh hưởng server người dùng. Không thay cấu hình API mặc định; đợt sửa dữ liệu nguồn được ghi bên dưới.

Riêng đợt sửa nguồn đã cập nhật 48 ô `platform` có bản sao lưu, không đổi các trường sự kiện khác; kiểm tra trình duyệt với DB/API thật đạt 7 nhóm, gồm mọi trang Facebook/Tin tức và hợp 85 ID không trùng. Xem `website-source-filtering.md` và `_tmp/platform-filter-browser-results.json`.
