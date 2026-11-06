# Backend / serving

Document loại 10/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **User đã duyệt ngày 2026-10-29.**

Phạm vi: code phục vụ dữ liệu website, quá trình dựng SQLite và hai giao diện React đang có. Nguồn là code, cấu hình, artifact và tài liệu hiện có; không dùng lộ trình phát triển để mô tả hệ thống đã cài đặt.

Hợp đồng HTTP/file chi tiết xem [loại 9](./hop-dong-tich-hop.md), schema dữ liệu xem [loại 3](./database-va-du-lieu.md), pipeline phân tích xem [loại 2](./data-pipeline.md). **Phần agent n8n ở loại 7 còn thiếu**, chờ user bổ sung sau; không coi mô tả serving local là xác minh backend chatbot trên cloud.

## 1. Các thành phần phục vụ dữ liệu

| Thành phần | Vai trò trong code |
|---|---|
| `serving/web_v2/backend/app.py` | API FastAPI đọc dữ liệu sự kiện từ SQLite |
| `serving/web_v2/backend/build_db.py` | ETL chạy riêng: dữ liệu web + insight + Apps Script → events.db |
| `content_extractor.py` | Trích nội dung text và tạo excerpt cho thẻ bài |
| `og_image_scraper.py` | Tìm URL ảnh đại diện từ HTML nguồn khi dựng DB |
| `serving/web_v2/frontend/` | Website React/Vite gọi FastAPI; chatbot gọi webhook n8n trực tiếp |
| `serving/dashboard/` | Dashboard React/Vite đọc JSON GitHub; có luồng Gemini trong trình duyệt |

Backend website hiện là FastAPI + SQLite. Apps Script là nguồn bổ sung links/status lúc ETL, không phải server xử lý request danh sách sự kiện từ website. Dashboard có dependency express trong package.json, nhưng các entry point/source serving đã khảo sát không cho thấy server Express riêng đang được khởi động.

## 2. Vòng đời API FastAPI

Khi import `app.py`, module xác định `DB_PATH` theo vị trí file, tạo app version `2.0`, gắn CORS và khai báo route. Không có hook startup/lifespan chạy `build_db.py`, migration, tải dữ liệu hoặc nạp mô hình ML.

Các handler dữ liệu là hàm `def` đồng bộ; phần xử lý dùng sqlite3 và SQL trực tiếp. Không có ORM, hàng đợi job, cache response hoặc pool kết nối trong file app đã đọc. Không diễn giải dùng FastAPI thành việc truy vấn SQLite đã chuyển sang driver bất đồng bộ.

Mỗi lần gọi handler dữ liệu:

1. `get_conn()` kiểm tra file DB tồn tại; thiếu thì ném HTTP 503.
2. Mở một kết nối SQLite, đặt row_factory thành sqlite3.Row.
3. Thực hiện SELECT, lấy kết quả và đóng kết nối trên đường chạy bình thường.
4. Chuyển row thành dict response; links được parse từ chuỗi JSON, is_hot được đổi thành bool.

Chi tiết sự kiện không tồn tại đóng kết nối rồi trả 404. Không có khối try/finally bao toàn bộ truy vấn để bảo đảm đóng kết nối khi mọi loại exception xảy ra. Code app không cấu hình riêng journal mode, bật foreign_keys hoặc transaction cho truy vấn đọc; không tự suy ra bảo đảm vận hành đồng thời từ việc DB có khai báo khóa ngoại.

## 3. Trách nhiệm các route

| Route GET | Xử lý chính |
|---|---|
| `/api/events` | Lọc category/từ khóa, đếm tổng, phân trang; xếp theo total_comments rồi id_content |
| `/api/hot` | Chỉ lấy is_hot=1, xếp số bình luận giảm dần, giới hạn kết quả |
| `/api/event/{id_content}` | Đọc sự kiện và actors liên quan |
| `/api/categories` | GROUP BY danh mục, đếm sự kiện và cộng bình luận |
| `/api/stats` | Tổng số sự kiện, bình luận và sự kiện hot trong DB |
| `/` | Thông tin dịch vụ và đường dẫn docs; không kiểm tra tính sẵn sàng của DB |

Chi tiết tham số, response và lỗi ở loại 9. Không có route ghi dữ liệu nghiệp vụ, endpoint chạy thu thập/ML hoặc proxy chatbot trong `app.py`. `/docs` là giao diện tài liệu do FastAPI cung cấp, không phải dashboard dữ liệu.

Query dùng placeholder cho category, q và ID. Tìm kiếm q vẫn dùng SQL LIKE với wildcard, không phải full-text search. Không có response_model, auth dependency hoặc rate limiter trong app; CORS cho origin `*`, method GET, header `*`. Các điều này mô tả code hiện tại, không xác nhận cấu hình gateway/cloud bên ngoài.

## 4. Dựng dữ liệu phục vụ bằng ETL riêng

`build_db.py` có main guard; chỉ chạy ETL khi được thực thi, không tự chạy cùng server. Script tự xác định repository root và các đường dẫn input, không dựa hoàn toàn vào current working directory.

| Nguồn | Vai trò |
|---|---|
| `data/raw/data_web.json` | Mã, tên, danh mục, nội dung, thời gian và nhân vật sự kiện |
| `data/analysis-output/insights.json` | Top sự kiện theo từng lĩnh vực, rank và số bình luận |
| Apps Script | Links/status theo mã sự kiện; là enrichment có thể thất bại |

Trình tự main: đọc JSON local → dựng hot lookup → gọi Apps Script → mở SQLite → DROP/tạo bảng → insert events/actors → commit dữ liệu cơ bản → lấy ảnh từ các link → update image_url → commit giai đoạn ảnh nếu có danh sách link để thử → đóng DB.

Đây là dựng lại toàn bộ dữ liệu, không phải append lịch sử hay migration tăng dần. Script không tạo DB tạm rồi thay file nguyên tử; hai giai đoạn commit không tạo một lần công bố đồng thời toàn bộ dữ liệu và ảnh. Chưa kiểm thử ảnh hưởng của việc chạy ETL trong lúc API đang đọc DB.

Một số quy tắc ánh xạ có ảnh hưởng tới kết quả phục vụ:

- Map khóa nguồn showbiz sang danh mục Giải trí, giáo dục sang Giáo dục; mọi event được ghi platform `news`.
- Bỏ sự kiện thiếu id_content; events dùng INSERT OR REPLACE, actors chỉ nhận phần tử dict có name.
- Hot lookup chỉ lấy các event có trong top_events_by_comments; event ngoài top mặc định số bình luận 0, rank null, is_hot=0.
- Links/status lỗi hoặc không có nguồn bổ sung về giá trị rỗng. Vì bảng bị dựng lại, enrichment cũ không được bảo toàn tự động.

Schema, chỉ mục và giới hạn thống kê xem loại 3/9. ETL không tự gọi classifier PhoBERT/GNN và không tạo insight từ bình luận thô.

## 5. Nội dung text và ảnh đại diện

`extract_clean_content()` giữ text thuần; nếu bắt đầu bằng `{` thì thử parse JSON để lấy content, sau đó thử regex và cuối cùng làm sạch ký tự JSON theo heuristic. Giá trị không phải string hoặc rỗng trả chuỗi rỗng. Đây không phải kiểm chứng nội dung hay cơ chế sửa mọi JSON lỗi.

`make_excerpt()` gộp whitespace, mặc định giới hạn 220 ký tự rồi cắt tại khoảng trắng và thêm dấu ba chấm khi dài. Không dùng LLM để tạo excerpt lúc phục vụ request.

Quá trình lấy ảnh chạy trong ETL, không chạy mỗi khi gọi API:

- Với mỗi event có links, ưu tiên URL web trước Facebook; lượt đầu thử link đầu, lượt sau chỉ thử link thứ hai nếu có và lượt đầu thất bại.
- httpx theo redirect, timeout 8 giây/request, batch concurrency 10. HTTP khác 200 hoặc exception trả None.
- BeautifulSoup tìm og:image, twitter:image rồi link image_src; chuẩn hóa URL tương đối theo trang nguồn.
- Chỉ lưu URL ảnh vào SQLite, không tải/lưu binary ảnh tại backend. Không bảo đảm link ảnh còn sống về sau hoặc mọi event đều có ảnh.

## 6. Website và dashboard là hai giao diện riêng

Website mount qua `src/main.jsx` → App với BrowserRouter, có `/`, `/news`, `/facebook`; Header/Footer/Chatbot dùng chung. API base lấy từ VITE_API_BASE, thiếu thì mặc định cổng 8000. Vite config frontend chỉ gắn plugin React; chưa có cấu hình proxy API trong file này.

FastAPI không mount StaticFiles hay serve build React trong app hiện có. Hướng dẫn local chạy frontend và backend bằng hai terminal. Chưa có cấu hình server production được xác minh để kết luận cách rewrite các route BrowserRouter khi truy cập trực tiếp.

Dashboard không lấy insight qua FastAPI: App tải GitHub raw theo URL viết trong code, khởi tạo state từ constants.tsx và refresh 30 giây. Tải thành công thay state; lỗi giữ dữ liệu đang có, ban đầu có thể là fallback. Theme được lưu localStorage; bốn tab Overview/Sentiment/Interaction/System do state điều khiển.

Tab Interaction còn đọc history qua GitHub và gọi Gemini trong browser để tổng hợp câu hỏi. Website chatbot POST thẳng tới n8n; hai luồng này không phải API FastAPI website. Cấu hình/tool agent n8n chưa đủ để mô tả backend chatbot hoàn chỉnh, xem loại 7.

## 7. Runtime, cấu hình và cách chạy local đã được ghi trong repo

| Thành phần | Cấu hình / hướng dẫn hiện có |
|---|---|
| Python backend | README dùng Python 3.11 và `.venv` riêng tại backend |
| Dependencies backend | FastAPI 0.115.6, Uvicorn 0.34.0, httpx 0.27.2, BeautifulSoup 4.12.3 trong requirements.txt |
| API local | README hướng dẫn Uvicorn app:app, host 127.0.0.1, cổng 8001 |
| Website local | README hướng dẫn VITE_API_BASE=http://localhost:8001, Vite host 127.0.0.1, cổng 5173, strictPort |
| Dashboard local | npm dev script đặt cổng 3000; README hướng dẫn host 127.0.0.1 và strictPort |
| Build/kiểm tra frontend | Cả hai có build Vite; website lint là ESLint, dashboard lint là TypeScript tsc --noEmit |

Lệnh đầy đủ và cài dependencies được giữ tại README từng thành phần ở mục nguồn. Các lệnh khởi động/build/cài đặt không được chạy lại trong task tài liệu này; bảng không phải xác nhận ứng dụng đang chạy trên các cổng đó.

Đường dẫn DB/input và Apps Script URL nằm trong code backend, không có biến môi trường tương ứng được đọc trong các file này. Dashboard Vite có cấu hình GEMINI_API_KEY/DISABLE_HMR, nhưng tab Interaction thực tế đọc khóa từ `/api.txt`; không dùng tên biến cấu hình để suy ra mọi lời gọi LLM lấy khóa từ đó.

## 8. Hiện trạng kiểm chứng và giới hạn

Kiểm tra artifact SQLite ở chế độ chỉ đọc ngày 2026-10-29: quick_check trả ok; DB có 85 events, 189 actors, 40 event có image_url và 45 không có. Có hai bảng events/actors, chỉ mục danh mục/số bình luận cùng chỉ mục khóa chính; journal_mode hiện là delete. foreign_key_check không báo vi phạm tại thời điểm kiểm tra, không chứng minh API đã bật cưỡng chế khóa ngoại cho mọi kết nối.

Phần kiểm tra route/OpenAPI ở loại 9 xác minh hình dạng trả về bằng gọi hàm trực tiếp với DB chỉ đọc; không phải kiểm thử HTTP, tải đồng thời hoặc tích hợp cloud. Task này không dựng lại DB, lấy ảnh, gọi Apps Script/LLM hay khởi động server.

Các giới hạn còn mở: dữ liệu web/dashboard có thể khác snapshot; platform chưa tách; enrichment và thống kê ngoài top có giới hạn; chưa xác minh backup/restore, giám sát, HTTP end-to-end, serving nhiều worker hoặc triển khai production. Không tự coi các hạng mục này đã có chỉ vì có hướng dẫn local.

## 9. Nguồn đối chiếu

- [API FastAPI](../serving/web_v2/backend/app.py), [ETL SQLite](../serving/web_v2/backend/build_db.py), [trích nội dung](../serving/web_v2/backend/content_extractor.py), [ảnh đại diện](../serving/web_v2/backend/og_image_scraper.py).
- [Backend README](../serving/web_v2/backend/README.md), [requirements](../serving/web_v2/backend/requirements.txt), [hướng dẫn web](../serving/web_v2/README.md), [frontend README](../serving/web_v2/frontend/README.md).
- [Website entry](../serving/web_v2/frontend/src/main.jsx), [routing](../serving/web_v2/frontend/src/App.jsx), [client API](../serving/web_v2/frontend/src/services/api.js), [Vite website](../serving/web_v2/frontend/vite.config.js).
- [Dashboard App](../serving/dashboard/src/App.tsx), [package](../serving/dashboard/package.json), [Vite dashboard](../serving/dashboard/vite.config.ts), [dashboard README](../serving/dashboard/README.md).
