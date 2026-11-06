# Thu thập dữ liệu

Document loại 4/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: các nhánh thu thập trong bản export n8n local và crawler Facebook tại `ingestion/code_cao_fb_chuahoanthien/`. Chỉ mô tả cài đặt hiện có; chưa chạy lại crawler, gọi API hay đối chiếu workflow đang chạy trên cloud.

Luồng xử lý sau thu thập xem [Data pipeline](./data-pipeline.md); cấu trúc các kho dữ liệu xem [Database và dữ liệu](./database-va-du-lieu.md). Kế hoạch làm lại Facebook nằm ở bảng Việc làm sau của doc-map, không được coi là cài đặt trong tài liệu này.

## 1. Hai cách thu thập hiện có

| Cách | Nguồn / công cụ | Đầu ra trong code | Mức xác minh |
|---|---|---|---|
| n8n: tìm URL và thu thập báo | Google Sheets, SerpApi, Gemini, Firecrawl | Links trên Sheets; JSON tổng hợp lên Google Drive | Đã đọc export, chưa kiểm tra cloud |
| n8n: bình luận Facebook | Google Sheets, Apify, Google Drive | JSON theo sự kiện; cập nhật trạng thái dòng URL | Đã đọc export; nhánh chưa nối trigger trong export |
| Python: bình luận Facebook | Google Sheets API, Playwright Firefox, Gemini | Một file `output/data_cao_fb.json` | Code chưa hoàn thiện, chưa kiểm thử lại |

Theo user xác nhận ngày 2026-10-29, crawler Facebook tự viết không hiệu quả nên trước đây dự án đã chuyển sang thu thập bằng Apify. Code Python còn trong repo là phần cài đặt chưa hoàn thiện, không phải bằng chứng đang dùng thay cho Apify. Thu thập Facebook vẫn cần được cải thiện; kế hoạch cụ thể thuộc bảng Việc làm sau của doc-map.

## 2. Bản export n8n và điểm bắt đầu thực tế

Nguồn: `ingestion/n8n/cào data.json`, gồm 78 node. File chứa cấu hình nhạy cảm và đang được Git ignore; tài liệu không chép khóa, token hay credential ID.

Không thể coi mọi node trong export là một luồng tự động chạy liên tục:

| Nhánh | Chuỗi kết nối trong export |
|---|---|
| Đường đi từ manual trigger | `When clicking ‘Execute workflow’` → `Get row(s) in sheet4` → `Normalize Links1` → `Update row(s) in sheet1` |
| Tìm URL | Các gốc `Get row(s) in sheet`, `Get row(s) in sheet2` → loop → SerpApi → Gemini → ghi Sheets; không có cạnh vào từ trigger |
| Thu thập nội dung báo | `Get row(s) in sheet1` → Firecrawl/Gemini → Drive → cập nhật status; không có cạnh vào từ trigger |
| Thu thập Facebook | `Get Pending Link1` → `Has Pending URL?` → `API Key Manager` → Apify → Drive → cập nhật status; không có cạnh vào từ trigger |
| Schedule | Có `Schedule Trigger1`, nhưng không có cạnh đi ra trong `connections` |

Đây là trạng thái kết nối của file local. Chưa có thông tin workflow cloud có giống bản này hay không, các nhánh rời có được chạy thủ công riêng hay không.

`Normalize Links1` tách URL dính nhau hoặc ngăn bằng dấu cách, xuống dòng, dấu phẩy/chấm phẩy; chuẩn hóa Facebook/YouTube và xóa `row_number` trước khi sinh dòng mới. Node cuối tên `Update row(s) in sheet1` nhưng **operation thực tế là `append`**. Đường đi manual này chuẩn hóa và thêm dòng Sheets, không đi tiếp tới scraper trong export.

## 3. n8n: tìm URL cho sự kiện

Các nhánh có cấu trúc tương tự: đọc sự kiện từ Sheets → lấy từ khóa → SerpApi → trích URL → dựng prompt Gemini → làm sạch kết quả → append Links lên Sheets → quay lại loop.

- Các node `Rate Limited?` / `Rate Limited?1` kiểm tra mã lỗi 429; nhánh lỗi chuyển khóa rồi chờ và gọi lại Gemini.
- Node `Append row in sheet` và `Append row in sheet1` ghi `Tên sự kiện`, `Links` và `Status: Done`. Không suy ra `Done` ở bước tìm URL có nghĩa nội dung/bình luận đã được thu thập.
- Tên node không luôn phản ánh thời gian chờ: `Wait 10s1` được cấu hình amount 30; cần đọc parameter khi vận hành.
- Có nhánh `Get row(s) in sheet3` → `Normalize Links` → update Sheets theo `row_number`, tách biệt với đường đi manual ở mục 2.

Tài liệu chưa xác nhận danh sách sự kiện do ai nhập, tiêu chí chọn nguồn cuối cùng hoặc mức đầy đủ của kết quả tìm kiếm.

## 4. n8n: thu thập và tổng hợp nội dung báo

### 4.1 Đầu vào và mã sự kiện

`Prepare All Links1` đọc `Danh mục`, `Tên sự kiện`, `Links`, `Status`, `row_number`; chuẩn hóa status bằng lowercase/trim và chỉ lấy `pending`.

Node này tự sinh `education_NNN` nếu danh mục chứa “giáo dục”, ngược lại dùng `showbiz_NNN`. Bộ đếm reset mỗi lần chạy nhánh; **không lấy `id_content` có sẵn trên dòng Sheets làm mã đầu ra**. Mã vì vậy phụ thuộc tập dòng pending và thứ tự đọc, không bảo đảm ổn định qua các lần chạy.

Mỗi URL hợp lệ trở thành một item có mã sự kiện, tên, danh mục và `row_number`. URL được tách/làm sạch và phải bắt đầu bằng `http`, dài hơn 20 ký tự.

### 4.2 Firecrawl và Gemini

1. `Loop Links1` gửi từng URL tới `Firecrawl Scrape1`, yêu cầu markdown và `onlyMainContent: true`.
2. `Save Markdown1` lấy `data.markdown` hoặc `markdown`; bỏ kết quả có lỗi hoặc dưới 200 ký tự, giữ tối đa 3.000 ký tự/nguồn trong workflow static data.
3. Chờ 3 giây rồi xử lý URL kế tiếp. Sau vòng URL, nhóm markdown theo sự kiện để đưa vào vòng Gemini.
4. `Build Gemini Prompt1` yêu cầu JSON gồm `id_content`, `ten_su_kien`, `danh_muc`, `content`, `actor_related`, `time_event`.
5. `Parse & Save Result1` bỏ hàng rào markdown, sửa một số lỗi định dạng và thử parse JSON; có xử lý `content` là chuỗi JSON lồng.
6. Nếu response lỗi hoặc không có `candidates`, tăng chỉ số khóa và trả cờ retry; kết nối chờ 3 giây rồi dựng lại request. Chưa thấy giới hạn số lần retry toàn vòng ở nhánh này.
7. Nếu parse thất bại, vẫn đẩy bản ghi có `parse_error`, nội dung thô và các giá trị dự phòng vào kết quả; bản ghi này không tương đương JSON tổng hợp đã đạt chất lượng.

### 4.3 Lưu và trạng thái

`Export JSON` xuất mảng kết quả thành `web_content_YYYY-MM-DD.json`, backup kết quả cho bước cập nhật status và reset một số static data. Sau `Upload to Google Drive`, nhánh lấy các bản ghi backup có `row_number` để ghi `Status: done`.

Hai giới hạn từ code:

- `Save Markdown1` tạo nhóm sự kiện nhưng không giữ `row_number`; các bước sau lại trông chờ trường này. Do đó chưa thể bảo đảm status được cập nhật đúng chỉ từ chuỗi code hiện tại.
- `Prepare All Links1` không reset `staticData.markdowns`, và `Export JSON` cũng không reset trường này. Có rủi ro giữ markdown từ lần chạy trước nếu static data còn tồn tại.

Không có bằng chứng rằng file xuất trên Drive tự động trở thành `data/raw/data_web.json` local; bước chuyển/ghép cần user xác nhận.

## 5. n8n: bình luận Facebook qua Apify

1. `Get Pending Link1` lọc `Status = Pending`; `Has Pending URL?` rẽ sang lấy API có `status = ok`, hoặc `Stop and Error` nếu không có item.
2. `Prepare Scrape Data` lấy **item đầu tiên** của node pending link: `id_content`, `Tên sự kiện`, `Danh mục`, `Links`, `row_number`.
3. `Run Apify Scraper` gửi một `startUrls`, `resultsLimit: 200`, `includeNestedComments: true`, `viewOption: RANKED_UNFILTERED`, dùng proxy residential của Apify.
4. Nhánh kiểm tra `statusCode < 400` rồi đọc dataset và format. Trường `maxComments: 3` ở bước chuẩn bị **không phải giới hạn request thực tế**; body request dùng 200.
5. `Format to Schema` lấy top-level từ `threadingDepth === 0`, nhóm reply theo `parentComment.id`; tạo JSON `{id_content, event_name, sort_mode, post_content, comments}` với `sort_mode: most_relevant`.
6. Tìm file Drive tên `{id_content}.json`: chưa có thì upload mới; có thì tải và nối comments cũ + mới, metadata lấy từ bản mới, rồi ghi đè file.
7. Sau ghi file, cập nhật dòng URL thành `Done`. Nhánh lỗi Apify đi qua node cập nhật URL về giá trị cấu hình `=Pending` và đánh dấu API `error`; cách n8n diễn giải giá trị này cần xác minh runtime.

Mã bình luận dạng `cmt_<id_content bỏ dấu gạch dưới>_NNNN`, reply thêm `_rNN` và `reply_to_id`. Số thứ tự bắt đầu lại mỗi lần format; bước merge **không khử trùng lặp và không đánh lại ID**, có thể tạo comment trùng hoặc trùng mã khi ghi thêm nhiều lượt vào cùng file.

Chỉ reply có quan hệ cha khớp một top-level comment mới được gắn vào cây kết quả. Không có bằng chứng mọi tầng reply của Apify đều được giữ. Chưa có kết nối loop sau `Update Status Done` để chứng minh một lần kích hoạt xử lý hết các URL pending.

## 6. Crawler Facebook Python chưa hoàn thiện

### 6.1 Thành phần và đầu vào

| File | Vai trò |
|---|---|
| `main.py` | Chọn sheet, lọc sự kiện đã lưu, chạy Firefox và điều phối từng sự kiện |
| `sheets_reader.py` | Google Sheets API bằng service account, scope chỉ đọc |
| `auth.py` | Nạp/lưu cookie, kiểm tra đăng nhập, đăng nhập và chờ xử lý checkpoint thủ công |
| `scraper.py` | Mở URL, trích bài, tải bình luận, mở reply, lọc và parse |
| `parser.py` | Trích text/likes/replies, sinh ID |
| `gemini_summarizer.py` | Tổng hợp bài cùng sự kiện; retry và fallback |
| `storage.py` | Đọc/ghi file JSON, tra mã sự kiện đã lưu |
| `config.py` | Tên biến cấu hình, cột, đường dẫn, thời gian chờ |

Sheet phải có đúng tên cột `Danh mục`, `id_content`, `Tên sự kiện`, `Links`. Parser bỏ dòng thiếu ID hoặc không có URL bắt đầu `http`; chỉ tách Links bằng whitespace, không có bộ chuẩn hóa mạnh như n8n. Không kiểm tra domain Facebook. **Không lọc Status và không cập nhật pending/done trên Sheets.**

Tên sheet lấy qua `SHEET_NAME_TEST` / `SHEET_NAME_REAL`, mặc định `Sheet_Test` / `Sheet_Real`. `main.py` hỏi chọn 1 hoặc 2 rồi lọc `id_content` đã có trong file output.

### 6.2 Đăng nhập và thu thập

- Mở Firefox qua Playwright, mặc định `HEADLESS = False`. Tái sử dụng cookie tại `session/fb_session.json`; cookie không còn hợp lệ thì đăng nhập bằng `FB_EMAIL`, `FB_PASSWORD`.
- Có điểm chờ người dùng xử lý captcha/checkpoint/2FA; đây không phải tiến trình hoàn toàn không tương tác.
- Xử lý tuần tự từng sự kiện và từng URL. Một URL có tối đa `MAX_RETRIES = 3` lần thử; giữa các lần lỗi chờ 3 giây.
- Mở bài, lấy nội dung, thử chọn chế độ bình luận, scroll và bấm tải thêm; dừng sau 8 vòng liên tiếp số phần tử comment không đổi. Mở replies tối đa 20 vòng.
- Lọc bình luận theo danh sách từ khóa spam và text trùng **trong một URL**. Không có khử trùng text toàn sự kiện giữa nhiều URL.
- Chỉ parse phần tử đã tải trong DOM; không bảo đảm đã lấy đủ mọi bình luận hoặc thứ tự chuẩn của Facebook.

`set_sort_most_recent()` là tên hàm hiện tại, nhưng log nói All Comments và `config.SORT_MODE` ghi `all_comments`. Lỗi chọn sort được bắt rồi bỏ qua, nên trường `sort_mode` lưu ra không chứng minh sort thực tế đã được áp dụng.

### 6.3 ID và tổng hợp nội dung

`process_event()` tạo `post_id = id_content.replace("_", "")[:12]`. Bình luận có mã `cmt_<post_id>_NNNN`; reply có mã `<comment_id>_rNN` và `reply_to_id` trỏ cha. `order_offset` tăng theo số bình luận đã nhận để nối thứ tự qua các URL thành công. Việc cắt mã sự kiện còn 12 ký tự có thể gây trùng tiền tố giữa các sự kiện.

Nội dung bài:

- Không bài nào có text: `post_content` rỗng.
- Một bài có text: dùng trực tiếp, không gọi Gemini.
- Nhiều bài có text: gọi model cấu hình `gemini-2.5-flash`; tối đa 5 lần thử, xoay khóa khi lỗi 429, hết danh sách thì chờ 60 giây và quay về khóa đầu.
- Gọi Gemini thất bại hết lượt: ghép các đoạn text bằng dòng trống. File output không có cờ riêng phân biệt tổng hợp LLM và fallback.

KeyManager được khởi tạo ngay khi import module tổng hợp. Thiếu cả `api.txt` và `GEMINI_API_KEY` có thể làm chương trình dừng trước khi chọn sheet, dù một sự kiện cụ thể sau đó có thể không cần gọi Gemini.

### 6.4 File được lưu thực tế

`storage.append_event()` cập nhật theo `id_content`, rồi ghi lại toàn bộ danh sách tại `output/data_cao_fb.json` sau mỗi sự kiện. Đường dẫn tương đối với thư mục chạy, không tự neo vào repository root.

`main.py` dựng metadata gồm category/source_urls và storage thêm timestamp, nhưng `_clean_event()` **xóa chính các trường này trên dict đã đặt trong danh sách trước khi ghi**. Schema thực tế của sự kiện vừa lưu gồm:

| Cấp | Trường được giữ |
|---|---|
| Sự kiện | `id_content`, `event_name`, `post_content`, `sort_mode`, `comments` |
| Bình luận | `comment_id`, `order`, `text`, `likes`, `reply_count`, `replies` |
| Reply | `comment_id`, `order`, `reply_to_id`, `text`, `likes` |

`category`, `source_urls`, `_scraped_at` và `url_source` bị bỏ; docstring storage/README có thể mô tả nhiều trường hơn file thật. Thư mục `output/raw` được tạo nhưng trong luồng đã đọc chưa có bước ghi riêng raw text theo URL. Log số URL sau clean có thể bằng 0 dù đã thu thập URL.

### 6.5 Tiếp tục sau lỗi và giới hạn

- Nếu mọi URL của sự kiện đều thất bại: không lưu sự kiện; lần chạy sau vẫn có thể thử lại.
- Nếu chỉ một phần URL thành công: vẫn tổng hợp và lưu sự kiện; lần sau lọc theo `id_content` sẽ bỏ qua cả sự kiện, gồm URL từng thất bại. Không có checkpoint riêng cho từng URL.
- Ghi file bằng mở mode `w` và dump cả danh sách; không có cơ chế ghi atomic được xác minh. Crash lúc ghi có thể làm hỏng file; JSON hỏng ở `load_all()` không được phục hồi tự động.
- Reply count lấy từ giao diện hoặc số reply parse được, không chứng minh đã tải đủ phản hồi.
- Chưa có bằng chứng kiểm thử chứng minh crawler mới chạy tốt; trạng thái vẫn là bản chưa hoàn thiện.

## 7. Phụ thuộc và cấu hình

`requirements.txt` của crawler khai báo Playwright 1.44.0, python-dotenv 1.0.1, colorlog 6.8.2, google-auth 2.29.0, google-auth-oauthlib 1.2.0, google-api-python-client 2.128.0, google-genai >=0.8.0.

Tên cấu hình cần xem trong `config.py`: `FB_EMAIL`, `FB_PASSWORD`, `GEMINI_API_KEY`, `GOOGLE_SHEETS_ID`, `GOOGLE_CREDENTIALS_FILE`, `SHEET_NAME_TEST`, `SHEET_NAME_REAL`. Module tổng hợp ưu tiên danh sách khóa từ `api.txt`, fallback sang cấu hình Gemini. Không đưa giá trị bí mật vào document.

README crawler hướng dẫn cài Chromium nhưng `main.py` hiện dùng Firefox. Tài liệu này không đưa chuỗi lệnh chạy như đã được kiểm chứng; cần đối chiếu browser binary và thư mục chạy trước khi vận hành.

## 8. Câu hỏi mở

1. Workflow n8n đang dùng trên cloud có đúng export local không? Các nhánh hiện rời trigger được chạy bằng cách nào?
2. Nguồn sự kiện/URL chính thức nằm trên sheet nào, và quy ước Status giữa bước tìm link và bước cào là gì?
3. File JSON trên Drive được tải/ghép vào `data/raw/` local qua bước nào?
4. User xác nhận đã chuyển từ crawler tự viết sang Apify do crawler không hiệu quả. Chưa có thông tin truy vết từng file dữ liệu hiện có về lần chạy/công cụ cụ thể; không gán toàn bộ dữ liệu cho crawler Python còn trong repo.
5. Các URL/sự kiện chỉ thành công một phần đã được rà soát và chạy bù chưa? Chưa có thông tin kiểm chứng độ bao phủ.

## 9. Nguồn đối chiếu

- [Bản export n8n local](../ingestion/n8n/cào%20data.json) — file bị Git ignore, có thể không tồn tại trên máy khác.
- [Điều phối crawler](../ingestion/code_cao_fb_chuahoanthien/main.py), [đọc Sheets](../ingestion/code_cao_fb_chuahoanthien/sheets_reader.py), [cấu hình](../ingestion/code_cao_fb_chuahoanthien/config.py).
- [Đăng nhập](../ingestion/code_cao_fb_chuahoanthien/auth.py), [scraper](../ingestion/code_cao_fb_chuahoanthien/scraper.py), [parser](../ingestion/code_cao_fb_chuahoanthien/parser.py).
- [Tổng hợp Gemini](../ingestion/code_cao_fb_chuahoanthien/gemini_summarizer.py), [lưu dữ liệu](../ingestion/code_cao_fb_chuahoanthien/storage.py), [dependencies](../ingestion/code_cao_fb_chuahoanthien/requirements.txt).
