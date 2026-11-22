# Cào bình luận Facebook từ Google Sheets

`orchestration/crawl-facebook-pending-sheet.py` đọc danh sách link và gọi
`FB_Crawl_skills/scripts/05_auto_scrape_cdp.py` tuần tự qua Chrome DevTools Protocol
(CDP). Script chạy với phiên Chrome đã mở và đọc Google Sheets ở chế độ chỉ đọc.

## Thay đổi trong crawler

- Khi mở URL Reel, crawler bấm **Bình luận** nếu khung chưa mở, đợi nội dung
  xuất hiện rồi dùng vòng lặp hiện có để tải bình luận và phản hồi.
- Crawler nhận biết sự cố renderer và timeout CDP. Script điều phối dừng ở link
  gặp lỗi kết nối hoặc mất phản hồi để có thể chạy lại link đó.
- Cứ 5 vòng, crawler lưu bản tạm `partial-comments.json` nếu đã thu được
  bình luận. Lượt chạy sau (sau khi Chrome sập / máy ngủ) nạp lại file này rồi cào
  tiếp. Khi lượt chạy xuất JSON thành công, crawler xóa bản tạm.

## Đầu vào

Truyền URL của tab, gồm `gid`, qua `--sheet-url` hoặc biến môi trường
`FB_SHEET_URL`.

Các cột bắt buộc: `id_content`, `Tên sự kiện`, `Links`, `Status`. Chỉ lấy trạng
thái `pending`, không phân biệt hoa/thường. Mỗi dòng phải có mã và tên sự kiện;
script không đoán mã hoặc lấy mã của dòng trước. Ô Links có thể chứa nhiều URL
cách nhau bằng khoảng trắng/xuống dòng. URL trùng cùng sự kiện chỉ cào một lần;
cùng URL gắn hai mã khác nhau sẽ báo lỗi trước khi cào.

Trong chế độ đọc Sheet, script tải CSV mỗi lần chạy. Sheet cần cho phép đọc qua
đường xuất CSV. Chrome dùng cho phiên đăng nhập Facebook và không tham gia đọc
Google Sheets.

## Chạy từ thư mục gốc repo, bằng PowerShell

Python 3.10+; dùng môi trường đã cài dependencies của crawler:

```powershell
$env:FB_SHEET_URL = 'https://docs.google.com/spreadsheets/d/SHEET_ID/edit?gid=TAB_ID'

# Xem trước toàn bộ pending; chưa cần Chrome, chưa cào.
.\FB_Crawl_skills\.venv\Scripts\python.exe orchestration/crawl-facebook-pending-sheet.py

# Lọc pending của một sự kiện.
.\FB_Crawl_skills\.venv\Scripts\python.exe orchestration/crawl-facebook-pending-sheet.py --event-id education_041

# Thực sự cào thử một link pending, bằng Google Chrome đã đăng nhập ở cổng 9333.
.\FB_Crawl_skills\.venv\Scripts\python.exe orchestration/crawl-facebook-pending-sheet.py --run --limit 1

# Cào các link pending chưa hoàn tất. Giới hạn 2.000 vòng và 6 giờ mỗi link.
$env:FB_CDP_TIMEOUT = '90'
.\FB_Crawl_skills\.venv\Scripts\python.exe orchestration/crawl-facebook-pending-sheet.py --run --max-rounds 2000 --timeout 21600
```

Khi cần mở Chrome riêng (sau đó đăng nhập Facebook thủ công):

```powershell
$fbProfile = Join-Path $env:LOCALAPPDATA 'FB-Crawl-Profile'
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' "--user-data-dir=$fbProfile" '--remote-debugging-port=9333' '--remote-debugging-address=127.0.0.1' 'https://www.facebook.com/'
```

Wrapper kiểm tra `/json/version` phải trả `Chrome/...`; từ chối Edge hoặc trình
duyệt khác. Cổng có thể đổi bằng `--cdp-url http://127.0.0.1:9333`.
Không dùng cùng tab để chạy crawler khác đồng thời.

## Phối hợp với crawler

Với mỗi URL hợp lệ, wrapper truyền:

```text
python 05_auto_scrape_cdp.py <url> --event-id <id_content trên Sheet>
    --target 0 --max-rounds 50 --click-pause 4 --no-relaunch --crash-retries 0
```

Các giá trị target/max-rounds/click-pause tùy chỉnh qua tham số wrapper. Mặc định
nghỉ 5 giây giữa hai link. `--timeout` mặc định 1.800 giây cho cả link.
`FB_CDP_TIMEOUT` mặc định 30 giây cho mỗi lần chờ phản hồi Chrome. Nếu trang
không còn tải thêm bình luận, crawler có thể kết thúc trước giới hạn vòng.
Trạng thái `success` xác nhận crawler đã thu và lưu được dữ liệu. Hãy đối chiếu
số bản ghi với số bình luận hiển thị nếu cần đánh giá mức bao phủ.

Sau khi crawler kết thúc, wrapper yêu cầu có đúng một `common*.jsonl` mới/cập
nhật trong thư mục bài. Kiểm tra event_id/platform/ID trước khi nhận kết quả.
Crawler trả exit code 0 nhưng không có dữ liệu mới vẫn được ghi là failed;
không lấy nhầm file cũ để báo thành công.

## Đầu ra và chạy tiếp

Mặc định lưu vào `data/facebook-sheet-output/` (đổi bằng `--output`):

```text
pending-plan.json           # danh sách đã chọn ở lần đọc Sheet này
state.json                  # tiến độ từng event_id + URL, success/failed
logs/<job-key>.log          # log riêng từng link
posts/<job-key>.jsonl       # bản chụp common.jsonl của từng link
events/education_041.json   # kết quả gộp theo mã sự kiện
```

File sự kiện gồm `id_content`, `event_name`, `platform`, danh sách `posts`,
`comments_count`, `comments`. Comments là **danh sách phẳng theo schema chung**,
giữ `reply_to_id`; không phải định dạng cây replies của n8n. Gộp loại trùng theo
`post_id + comment_id`. Không gán nhãn sentiment và không lọc rác tự động;
raw/common gốc của crawler vẫn được giữ nguyên trong `FB_Crawl_skills/data/posts/`.

Chạy lại sẽ đọc Sheet mới nhất, bỏ qua link đã thành công ở state cục bộ, và thử
lại link thất bại. `--limit` tính sau bước bỏ qua link đã xong. `--force` cào lại
các link vẫn pending dù đã xong ở máy; nếu cào lại thất bại thì giữ bản tốt cũ.
Đổi trạng thái một dòng sang Done trên Sheet sẽ loại dòng đó khỏi lượt chọn mới,
không tự xóa dữ liệu đã thu. Không ghi Done lên Sheet vì đây là luồng đọc-only.

`--run` tạo khóa `.running.lock` trong thư mục đầu ra. Nếu máy bị tắt đột ngột,
kiểm tra không còn runner hoạt động trước khi chuyển khóa cũ ra khỏi thư mục đầu ra.

Mã ID/timestamp/quan hệ phản hồi giữ nguyên giới hạn của crawler: có thể là hash
fallback, thời gian ước lượng và parent suy luận. Wrapper không tự bổ sung dữ
liệu còn thiếu. Sheet xuất CSV chỉ cung cấp giá trị hiển thị; nếu dùng nhãn
HYPERLINK thay URL thật trong ô Links thì cần đổi lại URL hoặc cơ chế đọc API.

## Cào lại theo danh sách riêng

Tạo một file JSON cục bộ có danh sách `jobs`. Mỗi mục dùng mã sự kiện, tên, URL
Facebook và số dòng gốc trong Sheet.

```json
{
  "jobs": [
    {
      "event_id": "showbiz_001",
      "event_name": "Sự kiện mẫu",
      "url": "https://www.facebook.com/reel/123456789",
      "sheet_rows": [2]
    }
  ]
}
```

```powershell
.\FB_Crawl_skills\.venv\Scripts\python.exe orchestration/crawl-facebook-pending-sheet.py --retry-plan '<đường dẫn JSON>' --run --max-rounds 2000 --timeout 21600
```

Bỏ `--run` để xem trước danh sách. Chế độ này đọc danh sách JSON trực tiếp.
Khi cào lại thành công, script ghép dữ liệu cũ và mới theo cặp `post_id` và
`comment_id`, ghi bản mới dưới tên riêng và giữ file kết quả trước đó. Khi
chạy lại cùng file danh sách, script bỏ qua những mục đã có kết quả của lượt
này. Link bị gián đoạn do Chrome chưa được tính là đã xử lý.

## Tiếp tục khi Chrome gặp lỗi

`orchestration/resume-facebook-crawl.py` lưu hàng đợi và tiến độ vào file cục bộ,
thử lại một lần khi Chrome mất kết nối và chuyển sang link tiếp theo nếu đã thử
lại hoặc renderer hết bộ nhớ. Nếu crawler đã lưu được bản tạm, script giữ các
bình luận đó trong file JSONL riêng với trạng thái `partial`. Kết quả sự kiện
chỉ gộp link có trạng thái `success`.

```powershell
$fbProfile = Join-Path $env:LOCALAPPDATA 'FB-Crawl-Profile'
$crawlProgress = Join-Path $env:LOCALAPPDATA 'facebook-crawl-progress.json'
.\FB_Crawl_skills\.venv\Scripts\python.exe orchestration/resume-facebook-crawl.py --chrome 'C:\Program Files\Google\Chrome\Application\chrome.exe' --profile $fbProfile --progress $crawlProgress
```

Khi tạo file tiến độ lần đầu, script lấy link `Pending` từ Sheet và bổ sung
các link lỗi hoặc còn bản tạm trong `state.json`. Dùng lại cùng file tiến độ
để tiếp tục danh sách đó. Cấu hình của script là 2.000 vòng và tối đa 6 giờ
mỗi link. Giữ file tiến độ, log, dữ liệu cào và hồ sơ Chrome trên máy chạy.

## Kiểm thử offline

```powershell
.\FB_Crawl_skills\.venv\Scripts\python.exe -m unittest discover -s orchestration/tests -v
```
