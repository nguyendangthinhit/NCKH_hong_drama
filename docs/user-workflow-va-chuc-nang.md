# User workflow và chức năng

Document loại 15/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: các thao tác và luồng dữ liệu thể hiện trong website/dashboard hiện có. Tài liệu được viết từ code và tài liệu dự án; không dùng ý tưởng phát triển làm chức năng đã cài đặt. Chưa kiểm thử bằng trình duyệt hoặc gọi dịch vụ ngoài trong lần viết này.

Hợp đồng API xem [loại 9](./hop-dong-tich-hop.md), serving xem [loại 10](./backend-serving.md), giới hạn chất lượng xem [loại 11](./thuoc-tinh-chat-luong.md). **Phần agent n8n ở loại 7 còn thiếu**, nên thao tác gửi chat trên website không chứng minh toàn bộ luồng RAG cloud đã được xác minh.

## 1. Các bề mặt tương tác

| Bề mặt | Điểm vào theo code | Người dùng thao tác được |
|---|---|---|
| Website | React Router tại `/`, `/news`, `/facebook` | Xem danh sách sự kiện, lọc/tìm trong danh sách, mở nguồn, gửi câu hỏi chatbot |
| Dashboard | App React riêng, bốn tab do state điều khiển | Xem tổng quan, phân bố nhãn, chi tiết summary, lịch sử chat và số liệu hệ thống |
| Công việc nghiên cứu | Script/CLI, bảng kiểm duyệt và artifact | Thu thập, xử lý, kiểm nhãn và đánh giá bằng công cụ ngoài hai giao diện trên |

Website và dashboard không có luồng đăng nhập/phân quyền đã cài trong các entry point được khảo sát. Không coi nhãn “quản lý” hoặc “nghiên cứu” trong tài liệu cũ là vai trò tài khoản đã được hệ thống cưỡng chế.

## 2. Điều hướng website

`App.jsx` đặt Header, Footer và Chatbot dùng chung quanh ba route. Header có logo về trang chủ, menu Trang chủ, Facebook và Tin Tức. Hai menu sau có liên kết Tất cả/Giải trí/Giáo dục; lựa chọn danh mục dùng query `?cat=...` trên route tương ứng.

| Thành phần | Hành vi đang có | Giới hạn |
|---|---|---|
| Menu danh mục | Mở dropdown khi đưa chuột vào, chọn link rồi đóng dropdown | Chưa có kiểm chứng thao tác trên thiết bị/cách nhập khác |
| Ô “Tìm kiếm drama...” ở Header | Giữ nội dung gõ trong state | Submit hiện chỉ preventDefault, còn TODO; không chạy tìm kiếm |
| Nút Thông báo | Hiển thị biểu tượng | Chưa gắn handler hoặc danh sách thông báo trong Header |
| Nút Đăng nhập | Hiển thị nút | Chưa gắn handler, form hoặc route đăng nhập |

Không có route trang chi tiết sự kiện trong `App.jsx`. API có endpoint chi tiết, nhưng việc endpoint tồn tại không tạo ra màn hình chi tiết tương ứng trên website.

## 3. Trang chủ và sự kiện Trending

Luồng trang chủ: mở `/` → tải hai nhóm thẻ qua `getLatestPostsByPlatform` → hiển thị ticker, khối Trending và các khối Facebook/Tin tức → chọn nguồn hoặc chuyển sang trang danh sách.

- Home gọi hai request song song, giới hạn 5 bản ghi cho khối Facebook và 6 cho khối Tin tức. Trong lúc chờ có skeleton; lỗi được ghi console, không có thông báo lỗi riêng cho người dùng ở nhánh catch hiện tại.
- `getLatestPostsByPlatform` bỏ qua platform và chỉ đặt per_page; API xếp theo số bình luận, không theo ngày. Vì vậy chữ “mới nhất” hoặc hai nhãn nền tảng không bảo đảm dữ liệu đã được tách theo nguồn/thời gian.
- Các nút “Xem tất cả” và CTA chuyển tới `/facebook` hoặc `/news`.
- Trending có hai tab Giải trí/Giáo dục, gọi `/api/hot` tối đa 10 bản ghi theo danh mục và cache kết quả trong component. Thẻ có hạng, ảnh nếu tải được, số nguồn và liên kết ngoài.
- Tab đã cache không tự tải lại trong component hiện tại; lỗi tải được cache thành mảng rỗng và hiển thị “Không có sự kiện trending”. Không xem trạng thái rỗng này là bằng chứng nguồn không có sự kiện.

Banner “Cập nhật liên tục”/“Live” là nội dung giao diện. Home không tự kích hoạt crawler hoặc bảo đảm dữ liệu mới theo thời gian thực.

## 4. Tìm, lọc và phân trang danh sách

Hai trang có cùng trình tự: mở route → lấy một trang API với per_page=9999 → giữ mảng trong state → áp dụng bộ lọc/tìm kiếm phía client → cắt trang để hiển thị.

| Thao tác | Facebook | Tin tức |
|---|---|---|
| Mã route | `/facebook` | `/news` |
| Kích thước trang UI | 10 sự kiện | 12 bài |
| Chọn danh mục | Từ các category xuất hiện trong mảng tải về; ghi vào `?cat=` | Như Facebook |
| Tìm kiếm | Title, category hoặc URL trong links, không phân biệt hoa thường | Như Facebook |
| Đổi bộ lọc/từ khóa | Quay lại trang 1 | Quay lại trang 1 |
| Không có kết quả | Thông báo và gợi ý đổi từ khóa/danh mục | Như Facebook |

Ô tìm tại hai trang này hoạt động theo state local, khác ô tìm chưa hoàn thiện ở Header. Nó không gọi tìm kiếm server khi gõ và không tìm trong toàn bộ `content_full`.

Pagination có Trước/Sau và số trang; ẩn khi có không quá một trang. Từ khóa và số trang không được lưu vào URL; chỉ danh mục dùng query parameter. Reload không khôi phục toàn bộ trạng thái tìm kiếm trước đó.

`getPaginatedPosts()` bỏ qua platform; ETL hiện gán mọi event là news. Hai trang vì vậy có thể dùng cùng một tập sự kiện, dù cách trình bày và số thẻ/trang khác nhau. Nếu dữ liệu vượt 9.999 bản ghi, hai trang không có vòng lặp tải hết các trang còn lại.

## 5. Đọc thẻ và mở nguồn

PostCard hiển thị tên sự kiện, category, nhãn kiểu thẻ, các nguồn và status nếu có; số bình luận chỉ hiện khi lớn hơn 0. Ảnh chỉ được render khi caller bật showImage; lỗi ảnh chuyển sang biểu tượng/gradient.

Nhấn tiêu đề hoặc Enter khi tiêu đề có focus mở mainLink trong tab mới. “Xem nguồn” và các URL liên quan cũng là liên kết ngoài. MainLink lấy `post.link`, nếu thiếu lấy links đầu tiên, cuối cùng dùng `#`; không phải route chi tiết nội bộ.

Một số khối giới hạn số URL hiển thị và chỉ ghi “+N nguồn khác” cho phần bị ẩn; không có thao tác mở rộng danh sách gắn vào nhãn đó. Status và số bình luận là dữ liệu phục vụ đã có, không phải kết quả xác minh nguồn lúc người dùng nhấn thẻ.

## 6. Chatbot trên website

Người dùng nhấn nút chat nổi để mở/đóng hộp thoại → nhập câu hỏi → Enter hoặc Gửi → thấy tin nhắn của mình ngay → chờ phản hồi bot.

- Input trống bị bỏ qua; trong khi loading, ô nhập và nút gửi bị khóa. Client gửi message và userId từ cookie tới webhook n8n, không gửi toàn bộ messages đang hiện.
- Response JSON có thể là object hoặc array; client lấy reply để hiển thị qua ReactMarkdown. Nếu reply rỗng có thông báo không có phản hồi.
- Nhánh catch có thể trả câu mẫu từ datamock.js hoặc thông báo lỗi kết nối. Câu mẫu không phải bằng chứng truy xuất RAG thành công.
- Messages là state component; reload bắt đầu lại phần hiển thị. Cookie userId có thể còn nhưng không chứng minh server đã khôi phục đúng Memory.
- Client chưa có timeout/abort hoặc kiểm tra res.ok trong hàm gửi. Chưa có quy trình UI xem/xóa lịch sử của riêng người dùng được xác minh.

Các khả năng diễn biến, dư luận và thống kê được mô tả trong prompt/báo cáo ở [loại 7](./llm-agent-rag.md). Chưa có luồng agent n8n để xác nhận việc định tuyến, retrieval, dẫn nguồn và fallback web đang chạy đúng từ đầu đến cuối.

## 7. Điều hướng và nguồn dữ liệu dashboard

Dashboard mở mặc định tab Overview; Sidebar chuyển tab bằng state, không tạo các URL con. Có nút mở/đóng sidebar và chuyển sáng/tối; theme lưu trong localStorage. Dấu hiệu loading/refresh và thời điểm tải thành công được hiển thị tại App.

App tải insight từ GitHub raw, khởi tạo bằng constants.tsx và poll mỗi 30 giây. Tải lỗi giữ dữ liệu đang có, không tự chứng minh số liệu mới. Tại thời điểm đọc code, URL chứa `data/analysis-ouput/insights.json`, khác thư mục local `data/analysis-output/`; chưa gọi remote để xác minh. Không sửa source đang được user thay đổi trong task này.

Dashboard dùng JSON remote thay vì API FastAPI website. Việc hai giao diện cùng hiển thị số liệu không chứng minh chúng dùng cùng snapshot.

## 8. Các tab dashboard

| Tab | Chức năng có trong code | Cách hiểu giới hạn |
|---|---|---|
| Overview | Số bình luận thô/sạch/rác, sự kiện, link web/Facebook, độ bao phủ hai lĩnh vực và tiến độ có/chưa phân tích | Sparkline được sinh theo công thức cố định để trang trí, không phải chuỗi thời gian đo được |
| Sentiment | Chọn Giáo dục/Showbiz; xem phân bố nhãn, từ khóa; chọn chỉ số xếp hạng và nhấn sự kiện để tải summary | Không phải suy luận ML tức thời hay phân loại lại dữ liệu khi nhấn |
| Interaction | Đọc lịch sử question/answer/timestamp, làm mới 30 giây; Gemini tổng hợp top 5 chủ đề từ câu hỏi | Không có thuật toán phát hiện bot được xác minh chỉ từ nhãn “Tương tác & bot” |
| System | Trash rate, số sự kiện đã phân tích, biểu đồ raw/clean/trash | “Live Web Research 14%” là giá trị viết cứng, không phải telemetry từ agent |

Nhãn giao diện về “realtime”, “System health” hoặc “performance” không thay cho dữ liệu giám sát uptime/latency hay trạng thái job thực tế.

## 9. Đi sâu sự kiện trong Sentiment

Luồng: chọn lĩnh vực → xem phân bố tổng hợp → chọn Trending/Volume/Engagement/Quality → nhấn thanh/bubble/thẻ sự kiện trong top → tải summary JSON theo ID → xem chi tiết → Quay lại hoặc đổi lĩnh vực.

Ranking UI tính lại trên mảng top_events_by_comments đã có: Volume là total, Engagement là clean, Quality là clean/total; Trending kết hợp clean, tỷ lệ sạch và hệ số giảm theo ngày. Đây là heuristic hiện có trong component, không phải chức năng Drama Score đã được nghiệm thu hay bảng xếp hạng trên mọi sự kiện ngoài mảng đầu vào.

Sentiment tải từ khóa riêng từ `data/analysis-output/keyword_analysis_v4.json`. Chi tiết sự kiện lấy summary ở nhánh Giáo dục `analyzed_dataa` hoặc Showbiz `analyzed_data`, hiển thị phân bố, diễn giải Giáo dục, bình luận tiêu biểu và thread tranh cãi Showbiz khi dữ liệu có. Bình luận tiêu biểu bị cắt tối đa 15 mục trong UI.

Lỗi tải chi tiết có thông báo và nút Thử lại. Nút Quay lại bỏ selectedEventId; đổi lĩnh vực cũng bỏ lựa chọn sự kiện. Summary và nhãn là artifact phân tích sẵn, không chứng minh nhận định của người viết hoặc tính đúng của nội dung bình luận.

## 10. Lịch sử, dữ liệu mẫu và phần chưa có luồng hoàn chỉnh

Interaction lọc record có question, đảo thứ tự để hiển thị lịch sử và có thể gửi tập câu hỏi tới Gemini trong browser để tổng hợp chủ đề. Đây không phải top sự kiện theo số bình luận ở website/insight. UI có ghi chú Zalo/Telegram nhưng code đang đọc GitHub history, chưa có webhook Zalo/Telegram được nối trong component này.

Các entry point đã đọc không có luồng quản trị CRUD sự kiện, chạy crawler/training từ UI, đăng ký/tài khoản, đánh dấu quan tâm hoặc sửa nhãn trực tiếp. Công việc thu thập/xử lý/kiểm duyệt hiện nằm ở script và file dữ liệu; hướng dẫn chạy xem loại 2/4/5/10, không suy ra có trang quản trị vì đã có backend.

Các thao tác trong tài liệu là hành vi đọc được từ source. Chưa có kiểm thử trình duyệt, mobile/accessibility hoặc kết nối cloud mới trong lần viết này; không coi tên nút, mock, số cố định và prompt là chức năng đã được xác minh vận hành.

## 11. Nguồn đối chiếu

- [Website routing](../serving/web_v2/frontend/src/App.jsx), [Header](../serving/web_v2/frontend/src/components/Header/Header.jsx), [Home](../serving/web_v2/frontend/src/pages/HomePage/HomePage.jsx).
- [News](../serving/web_v2/frontend/src/pages/NewsPage/NewsPage.jsx), [Facebook](../serving/web_v2/frontend/src/pages/FacebookPage/FacebookPage.jsx), [Pagination](../serving/web_v2/frontend/src/components/Pagination/Pagination.jsx).
- [PostCard](../serving/web_v2/frontend/src/components/PostCard/PostCard.jsx), [link helpers](../serving/web_v2/frontend/src/utils/postHelpers.js), [Trending website](../serving/web_v2/frontend/src/components/TrendingSection/TrendingSection.jsx), [API client](../serving/web_v2/frontend/src/services/api.js).
- [Chatbot](../serving/web_v2/frontend/src/components/Chatbot/Chatbot.jsx), [câu mẫu](../serving/web_v2/frontend/src/components/Chatbot/datamock.js).
- [Dashboard App](../serving/dashboard/src/App.tsx), [Sidebar](../serving/dashboard/src/components/Sidebar.tsx), [Overview](../serving/dashboard/src/components/views/OverviewView.tsx), [System](../serving/dashboard/src/components/views/SystemView.tsx).
- [Sentiment](../serving/dashboard/src/components/views/SentimentView.tsx), [Trending dashboard](../serving/dashboard/src/components/views/trending-events-section.tsx), [Interaction](../serving/dashboard/src/components/views/InteractionView.tsx).
