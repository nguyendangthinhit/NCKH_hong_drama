# Hợp đồng tích hợp

Document loại 9/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: dữ liệu vào/ra giữa các thành phần theo code và tài liệu đang có. Đây là mô tả hành vi hiện tại, không bổ sung API hoặc quy ước từ lộ trình phát triển. Lần rà soát đọc nguồn local, sinh OpenAPI từ app và gọi trực tiếp các hàm route với kết nối SQLite chỉ đọc để kiểm tra hình dạng trả về; không mở HTTP server, gọi dịch vụ ngoài, chạy crawler hoặc dựng lại DB.

Cấu trúc kho chi tiết ở [loại 3](./database-va-du-lieu.md), thu thập ở [loại 4](./thu-thap-du-lieu.md), pipeline ở [loại 2](./data-pipeline.md). **Phần agent n8n còn thiếu và chờ user bổ sung** theo [loại 7](./llm-agent-rag.md); không coi giao tiếp chatbot phía server đã được kiểm chứng đầy đủ.

## 1. Các ranh giới tích hợp

| Bên cung cấp → bên nhận | Giao diện hiện có | Dữ liệu chính |
|---|---|---|
| FastAPI → website | HTTP GET `/api/*` | Sự kiện, top, danh mục, thống kê |
| Website → n8n | HTTP POST `/webhook/nckh` | Câu hỏi và userId; client đợi reply |
| GitHub raw → dashboard | HTTP GET JSON | Insights và lịch sử hội thoại |
| Dashboard → Gemini | GoogleGenAI trong browser | Câu hỏi lịch sử → top chủ đề |
| Apps Script → build_db | HTTP GET | Links và status theo mã sự kiện |
| Google Sheets → crawler Python | Sheets API, service account chỉ đọc | Danh mục, mã, tên sự kiện và URL |
| n8n → nhà cung cấp/Drive/Sheets | Node trong export thu thập | Tìm URL, cào nội dung, lưu JSON, cập nhật dòng |
| Script pipeline → script/serving | JSON, Parquet, CSV, SQLite | Bình luận, nhãn, summary, insight, dữ liệu web |

Không có một schema/version chung bao trùm các giao diện này. API ghi version 2.0 trong app, nhưng route không có tiền tố version; các file dữ liệu đã đọc không có cơ chế migration/compatibility được xác minh.

## 2. API website: địa chỉ và quy tắc chung

`app.py` tạo FastAPI `Drama Intelligence API`, version `2.0`, đọc `events.db` cạnh file Python. Frontend lấy base URL từ `VITE_API_BASE`, thiếu thì dùng `http://localhost:8000`. README local hiện hướng dẫn backend cổng 8001, nên cần đặt base tương ứng; không có cơ chế tự dò cổng.

- Các route nghiệp vụ hiện chỉ đọc dữ liệu bằng GET; không có route tạo/sửa/xóa sự kiện trong file này.
- Không thấy auth dependency/API-key requirement trong các route. CORS cho origins `*`, methods GET và headers `*`; không phải cơ chế phân quyền và không áp dụng cho webhook n8n độc lập.
- `/` trả `service`, `version`, `docs`; `/docs` là giao diện OpenAPI do FastAPI cung cấp.
- OpenAPI sinh từ app mô tả tham số và validation, nhưng schema response 200 hiện là `{}` vì không khai báo response model. Các hình dạng response bên dưới lấy từ code trả về, không phải schema response đã được kiểm tra tự động.

## 3. Endpoint và tham số

| GET | Tham số | Mặc định / ràng buộc | Response thành công |
|---|---|---|---|
| `/api/events` | `category`, `q` | String tùy chọn; không enum danh mục | Object phân trang |
| `/api/events` | `page`, `per_page` | Integer; page ≥1, mặc định 1; per_page 1–9999, mặc định 12 | Như trên |
| `/api/hot` | `category`, `limit` | Category tùy chọn; limit integer 1–50, mặc định 10 | `{data: Event[]}` |
| `/api/event/{id_content}` | `id_content` | Path string bắt buộc | Event trực tiếp, thêm actors |
| `/api/categories` | Không có tham số nghiệp vụ khai báo | — | `{data: [{name, count, comments}]}` |
| `/api/stats` | Không có tham số nghiệp vụ khai báo | — | `{total_events, total_comments, hot_events}` |

Danh sách lọc category bằng so sánh `danh_muc = category`; q bằng SQL LIKE trên tên và nội dung đầy đủ. Ký tự `%`/`_` trong q không được escape thành literal. Không có tham số platform, sort, date hoặc cursor trong route danh sách.

`/api/events` sắp `total_comments DESC, id_content ASC`. Response gồm `data`, `total`, `page`, `per_page`, `total_pages`; tổng trang là phép chia làm tròn lên. Không có kết quả thì total_pages bằng 0. Page vượt cuối vẫn trả danh sách rỗng và metadata page yêu cầu, không tự ép về trang cuối.

`/api/hot` chỉ lấy `is_hot = 1`, sắp số bình luận giảm dần rồi giới hạn số dòng; không khai báo khóa sắp phụ khi số bình luận bằng nhau. Endpoint danh mục đếm sự kiện và cộng số bình luận theo category; stats cộng trực tiếp từ DB. SUM có thể là null khi DB không có dòng, không được coalesce về 0 trong query.

## 4. Hình dạng Event và ánh xạ frontend

`row_to_event()` chuyển row SQLite thành object sau:

| Nhóm trường | Giá trị / nguồn |
|---|---|
| `id`, `id_content` | Cùng lấy mã `id_content` |
| `title`, `category`, `platform` | Từ tên sự kiện, danh mục, nền tảng trong DB |
| `description`, `content_full`, `time_event` | Excerpt, nội dung đầy đủ và thời gian sự kiện |
| `links`, `status`, `image_url` | Links decode JSON; trạng thái nguồn; ảnh có thể null |
| `total_comments`, `clean_comments`, `trash_comments` | Số liệu đã ghi trong DB |
| `hot_rank`, `is_hot` | Rank có thể null; is_hot được đổi sang boolean |
| `actors` | Chỉ thêm trong chi tiết: mảng object `{name, role}` |

Các `dict.get` mặc định không thay mọi giá trị null bằng chuỗi/số rỗng. API không có response model để chuẩn hóa hoặc cưỡng chế kiểu các trường lấy từ DB. Links hỏng JSON có thể gây lỗi khi ánh xạ response, không có nhánh phục hồi riêng trong mapper.

`services/api.js` đổi `id_content → id`, `total_comments → totalComments`, `is_hot → isHot`, `hot_rank → hotRank`, `image_url → imageUrl`; giữ title/category/platform/description/links/status. Mapper bỏ `content_full`, `time_event`, `clean_comments`, `trash_comments`, `actors`. Vì vậy `getPostById()` nhận response chi tiết nhưng không giữ mọi trường của nó cho caller.

| Hàm client | Hợp đồng thực tế |
|---|---|
| `getAllPosts()` | Gọi một trang per_page=9999, không lặp mọi trang nếu dữ liệu vượt giới hạn đó |
| `getPostsByPlatform()`, `searchPosts()` | Lọc platform ở client sau khi lấy dữ liệu; không phải bộ lọc server |
| `getPaginatedPosts()` | Bỏ qua platform; đổi total_pages/page thành totalPages/currentPage |
| `getLatestPostsByPlatform()` | Bỏ qua platform; chỉ đặt per_page, vẫn theo thứ tự số bình luận của API, không có sort ngày |
| `getHotEvents()`, `getCategories()` | Lấy mảng data trong response |

Hiện build_db gán platform `news` cho mọi event; không diễn giải hai trang news/Facebook là hai nguồn đã được tách đầy đủ. Số bình luận DB ngoài các top insight có thể bằng 0 do cách ETL, không chứng minh sự kiện không có bình luận.

## 5. Lỗi và độ ổn định của API

| Trường hợp | Hành vi theo code/framework |
|---|---|
| Không có events.db | HTTP 503 với detail hướng dẫn chạy build_db.py |
| Không có mã sự kiện chi tiết | HTTP 404 với detail `Không tìm thấy sự kiện` |
| Tham số integer sai kiểu/vượt bounds | Validation FastAPI, HTTP 422 |
| Lọc không có kết quả | HTTP 200, data rỗng |
| SQLite/schema/JSON lỗi khác | Không có mapping lỗi nghiệp vụ riêng; không bảo đảm luôn cùng cấu trúc detail |

Các lỗi 404/503 được raise trong code nhưng chưa khai báo riêng trong OpenAPI responses. `apiFetch()` frontend kiểm `res.ok` rồi ném Error chứa status/path; không đọc detail server vào thông điệp đó. Không có timeout, retry, backoff hoặc schema validator response trong helper này.

Không thấy SLA, rate limit, idempotency key hoặc contract test tự động cho các endpoint trong các file đã đọc. Không suy ra các tính năng này chỉ từ việc API dùng FastAPI.

## 6. Webhook chatbot: phần quan sát được từ client

Chatbot POST trực tiếp JSON tới webhook n8n `/webhook/nckh`, không qua FastAPI ở trên. Request có hai trường: `message` lấy input và `userId` từ cookie. Thiếu cookie thì client dùng crypto.randomUUID, lưu cookie path `/` tối đa một năm. Request không gửi toàn bộ mảng messages.

Client parse JSON; nếu response là array thì lấy phần tử đầu, sau đó đọc `result.reply`. Không có reply thì dùng thông báo không có phản hồi; lỗi fetch/parse/truy cập object vào catch và có thể dùng câu mẫu `datamock.js`. Hàm chưa kiểm `res.ok`, timeout hay retry. Đây là cách client tiêu thụ response, không phải bằng chứng server luôn trả đúng object/mảng đó.

Prompt Final LLM local tham chiếu `chatInput` của node chat; chưa có workflow agent để xác minh ánh xạ từ `message`, cách giữ memory theo userId, error envelope, CORS hoặc xác thực webhook. User đã xác nhận luồng nằm trong n8n và sẽ bổ sung sau; phần hợp đồng server tiếp tục để mở theo loại 7.

## 7. Apps Script và dữ liệu ảnh khi dựng DB

`fetch_links_by_id()` gọi Apps Script bằng urlopen, timeout 20 giây; chấp nhận object có `posts` hoặc danh sách ở cấp gốc. Mỗi phần tử code đọc `id`, `links`, `status`; id đổi thành string rồi dùng để khớp `id_content` local. Links thiếu/null về `[]`, status thiếu về chuỗi rỗng. Không có validator đảm bảo links thực sự là list URL.

Nếu gọi/parse/duyệt dữ liệu lỗi, hàm catch exception và trả `{}`; build tiếp tục với links rỗng/status rỗng. Không có retry ở hàm này và không giữ lại enrichment cũ vì main xóa rồi dựng lại bảng. Không gọi endpoint khi rà soát tài liệu.

Ảnh là enrichment riêng: `og_image_scraper.py` tải HTML, theo redirect, timeout 8 giây/request; HTTP khác 200/lỗi trả None. Parser ưu tiên og:image, rồi twitter:image/link image_src, resolve URL tương đối. Batch trả list cùng thứ tự input, mặc định concurrency 10. build_db ưu tiên link web trước Facebook và có bước thử link dự phòng; không phải API media upload hay bảo đảm mọi event có ảnh.

## 8. Dashboard và các giao diện JSON/file

Dashboard `App.tsx` tải insight từ GitHub raw `main/data/insights.json`, đọc JSON và đưa thẳng vào state; state ban đầu dùng `constants.tsx`, lần tải sau lỗi thì giữ dữ liệu đang có, làm mới mỗi 30 giây. File local hiện ở `data/analysis-output/insights.json`; chưa xác minh hai nguồn cùng phiên bản.

TypeScript `InsightsData` mô tả ba phần overall/education/showbiz; các nhánh gồm số sự kiện, comment_stats, phân bố nhãn, top_events_by_comments, events_by_year. Count là số, nhiều tỷ lệ là chuỗi có `%`. Interface TypeScript không phải validator runtime cho JSON remote; không có schema version hoặc hash input để phát hiện lệch snapshot trong fetch này.

`InteractionView.tsx` đọc history qua GitHub raw, dùng question/answer/timestamp để hiển thị; các trường user_id/source_type/the_loai/su_kien tồn tại trong artifact local nhưng không phải tất cả được hiển thị. Việc ghi history từ n8n chưa có luồng kiểm chứng.

Dashboard còn tải `/api.txt` làm danh sách khóa rồi gửi các câu hỏi lịch sử tới Gemini qua GoogleGenAI trong browser. Đây là giao diện nhà cung cấp độc lập, không dùng webhook chatbot. Thông tin model, retry và giới hạn bảo mật được mô tả ở loại 7; không đưa giá trị khóa vào document.

## 9. Hợp đồng file của pipeline và thu thập

| Bên tạo → bên nhận | Khóa/đầu vào cần khớp | Giới hạn hiện tại |
|---|---|---|
| JSON web + summary → merge_final_data | `id_content`; CLI `--web`, `--edu_sum`, `--output`, tùy chọn `--show_sum` mặc định rỗng | Không tự suy luận một bộ nhãn chung cho hai lĩnh vực |
| outputnew → analyze_insights | Thư mục có education/showbiz; `--input` bắt buộc, `--output` mặc định insights.json | Đọc summary, không tái đếm mọi comment full |
| data_web + insight → build_db | Nội dung sự kiện; education/showbiz.top_events_by_comments | Main DROP TABLE rồi dựng lại; SQLite không là kho lịch sử append |
| JSON bình luận → Spark preprocessing | `--inputs` nhiều thư mục, `--output`, threads mặc định 4 | Xuất Parquet phẳng; import hiện còn đường dẫn cũ |
| Parquet → Spark PMI | `--parquet`, `--output`; top10/min-count3/min-pmi1.0/threads4 | Không coi mọi bước đã phân tán; xem loại 6/8 |

Schema bình luận hai cấp, stance/emotion và metadata kho đã có ở loại 3/5; không gộp bốn stance Giáo dục với năm emotion Showbiz thành cùng tập giá trị. Mã sự kiện/comment là khóa nối quan trọng nhưng hiện có ID lặp và cách sinh mã khác nhau giữa cài đặt, nên không mặc định unique xuyên mọi nguồn.

Crawler Python đọc Sheets bằng service account scope spreadsheets.readonly, yêu cầu header đúng tên `Danh mục`, `id_content`, `Tên sự kiện`, `Links`; bỏ dòng thiếu mã/URL, tách Links bằng whitespace, không lọc/cập nhật Status. Export n8n có quy tắc Status và ghi Drive riêng, kể cả Pending/Done khác hoa thường; xem loại 4. Không có một enum trạng thái chung đã được cưỡng chế giữa Sheets, Apps Script và SQLite.

Việc tải/ghép JSON từ Drive vào data/raw local chưa có cầu nối tự động được xác minh. Crawler Python lưu danh sách sự kiện trong một file, còn nhánh Apify lưu theo sự kiện; không coi hai đầu ra thay thế trực tiếp cho nhau chỉ vì cùng có comments. API Supabase/embedding/rerank và tool binding agent chờ luồng n8n/schema bổ sung, không suy ra contract live từ tên trong báo cáo.

## 10. Thông tin còn thiếu để chốt tích hợp

1. Export agent n8n, mapping webhook/prompt/memory, response lỗi và quyền truy cập thực tế.
2. Schema/RPC Supabase và cấu hình embedding/rerank, nguồn nạp dữ liệu đang sử dụng.
3. Cầu nối Drive → local, phiên bản schema và snapshot dùng đồng thời cho web/dashboard/RAG.
4. Hành vi remote Apps Script, Sheets, webhook và GitHub thực tế chưa được kiểm thử trong lần viết tài liệu; chỉ có hợp đồng mà code local đọc/ghi.

## 11. Nguồn đối chiếu

- [FastAPI](../serving/web_v2/backend/app.py), [client API](../serving/web_v2/frontend/src/services/api.js), [hướng dẫn web](../serving/web_v2/README.md).
- [Dựng DB và Apps Script](../serving/web_v2/backend/build_db.py), [ảnh từ trang nguồn](../serving/web_v2/backend/og_image_scraper.py).
- [Chatbot client](../serving/web_v2/frontend/src/components/Chatbot/Chatbot.jsx), [câu mẫu](../serving/web_v2/frontend/src/components/Chatbot/datamock.js).
- [Dashboard App](../serving/dashboard/src/App.tsx), [types](../serving/dashboard/src/types.ts), [Interaction](../serving/dashboard/src/components/views/InteractionView.tsx).
- [Đọc Sheets](../ingestion/code_cao_fb_chuahoanthien/sheets_reader.py), [lưu crawler](../ingestion/code_cao_fb_chuahoanthien/storage.py).
- [Gộp pipeline](../analysis/single/merge_final_data.py), [insight](../analysis/single/analyze_insights.py), [Spark preprocessing](../preprocessing/spark/pyspark_preprocessing.py), [Spark PMI](../analysis/spark/pyspark_pmi_keywords.py).
