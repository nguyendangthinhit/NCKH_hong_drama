# Hướng dẫn team: cào bình luận Facebook và phân tích bằng LLM

Tài liệu cho thành viên team tự chạy trên máy mình. Phần A cài đặt một lần. Phần B cào theo bảng link. Phần C phân tích. Phần D là các prompt dán thẳng cho trợ lý AI (Claude Code, Cursor...) nếu muốn nhờ AI chạy giúp.

Lệnh dưới đây chạy trong **PowerShell**, tại thư mục gốc repo. `$PY` là đường dẫn Python 3.10+ của máy bạn (ví dụ `python` hoặc `C:\...\python.exe`).

---

## A. Cài đặt (một lần)

1. Lấy code:
   ```powershell
   git clone <url repo> NCKH_hong_drama
   cd NCKH_hong_drama
   git pull
   ```
2. Cài thư viện:
   ```powershell
   $PY = "python"
   & $PY -m pip install websockets openpyxl pytest
   ```
3. **File bí mật (không có trên git, xin trưởng nhóm gửi riêng):**
   - `.env.local` ở thư mục gốc. Dòng 4 có dạng `API_key=<key1>,<key2>`, dòng 5 có dạng `Base URL=https://api.mmodiary.com/v1`.
   - `model_list.txt` ở thư mục gốc, mỗi dòng một model (ví dụ `doitac3/deepseek-v4.1-flash`).
   - Không commit hai file này. `.gitignore` đã chặn sẵn.
4. Kiểm tra cài đặt (không tốn request):
   ```powershell
   & $PY -m pytest ingestion/tests analysis_new/tests -q
   ```
5. Chống ngủ máy khi chạy lâu: `powercfg /change standby-timeout-ac 0` (chạy xong thì trả lại bằng `powercfg /change standby-timeout-ac 15`). Cắm sạc và không gập máy.

---

## B. Cào bình luận theo bảng link

### B1. Bảng link (`.xlsx`)
Mặc định là `FB_Crawl_skills/data/cao.xlsx`. Dùng file khác thì thêm `--sheet <đường dẫn>`. Script tìm cột theo **tên tiêu đề**, thứ tự cột không quan trọng:

| Cột | Bắt buộc | Ghi chú |
|---|---|---|
| `Mã sự kiện` | có | ví dụ `showbiz_064`, `education_041` (tiền tố quyết định lĩnh vực khi phân tích) |
| `Link Facebook` | có | link bài, link `share/p/`, hoặc `reel/<id>` |
| `Tên sự kiện` | nên có | đưa vào prompt phân tích |
| `Trang hoặc nhóm đăng` | không | |
| `Số bình luận (số)` | không | dùng để ước số vòng cuộn |
| `Trạng thái` | không | `pending` = chưa cào, `done` = đã cào. Thiếu cột thì script tự thêm |

### B2. Chạy
```powershell
# Xem trạng thái
& $PY -X utf8 ingestion/crawl_links_from_sheet.py --list

# Cào mọi link pending (tự mở Chrome profile riêng; lần đầu phải đăng nhập Facebook trong cửa sổ đó)
& $PY -X utf8 ingestion/crawl_links_from_sheet.py

# Thử 1 link của 1 sự kiện
& $PY -X utf8 ingestion/crawl_links_from_sheet.py --event showbiz_065 --limit 1
```
Chạy **song song 2 terminal** (mỗi terminal một Chrome và một profile riêng, không cào trùng link):
```powershell
# Terminal 1: từ dưới bảng lên (bài lớn để cuối bảng thì được cào ngay)
& $PY -X utf8 ingestion/crawl_links_from_sheet.py --reverse
# Terminal 2: từ trên xuống, Chrome thứ hai ở cổng 9223 (lần đầu đăng nhập FB, rồi bấm Enter)
& $PY -X utf8 ingestion/crawl_links_from_sheet.py --port 9223
```

### B3. Lưu ý khi cào
- Cào xong link nào thì link đó được ghi `done` vào bảng ngay. Lỗi thì giữ `pending`; chạy lại lệnh là cào tiếp.
- **Không bấm lưu file bảng trong Excel lúc đang cào** (sẽ ghi đè các `done`). Mở để xem thì được.
- **Không thu nhỏ cửa sổ Chrome**, vì tab bị ẩn thì Facebook ngừng tải comment.
- Chrome sập hoặc máy ngủ giữa chừng: chạy lại lệnh. Crawler nạp `partial-comments.json` và cào tiếp.
- Terminal bị tắt ngang (không phải Ctrl+C) thì link đó bị giữ khoá. Xoá `FB_Crawl_skills/data/posts/<thư mục bài>/.crawl.lock` rồi chạy lại.
- Số comment lấy được thường **ít hơn số Facebook hiển thị** (Facebook không tải hết comment cũ, reply và comment ẩn). Đây không phải lỗi.
- Kết quả thô của mỗi link: `FB_Crawl_skills/data/posts/<thư mục bài>/common*.jsonl`.

---

## C. Phân tích bằng LLM (`analysis_new`)

### C1. Đầu vào: file sự kiện định dạng chính thức
Mỗi sự kiện một file `.json`:
```json
{"id_content": "showbiz_064", "event_name": "...", "sort_mode": "...", "post_content": "...",
 "comments": [{"comment_id": "...", "order": 1, "text": "...", "likes": 0, "reply_count": 1,
               "replies": [{"comment_id": "...", "reply_to_id": "...", "text": "...", "replies": []}]}]}
```
- **Dữ liệu tự cào (phần B):** gộp các link `done` theo mã sự kiện:
  ```powershell
  & $PY -X utf8 ingestion/crawled_posts_to_analysis_events.py
  ```
  Kết quả ghi vào `data/crawled-events/<mã sự kiện>.json`.
- **Dữ liệu đã có sẵn đúng định dạng trên** (ví dụ `data/Data fb cào/`): dùng thẳng thư mục đó.

### C2. Chạy
```powershell
# 1. Kiểm tra key/API còn sống (tốn 1 request)
& $PY -X utf8 -m analysis_new.mmo_client --probe

# 2. Ước tính số request + ghi prompt mẫu (KHÔNG tốn request)
& $PY -X utf8 -m analysis_new.single.run_analysis_single data/crawled-events data/analysis-new-output/crawled

# 3. Chạy thật (--max-requests: từ chối chạy nếu dự kiến vượt số này)
& $PY -X utf8 -m analysis_new.single.run_analysis_single data/crawled-events data/analysis-new-output/crawled --yes --max-requests 150
```
- Tốc độ đo được: **khoảng 3 phút mỗi request**. 100 request mất khoảng 5 giờ, nên chạy qua đêm.
- Bị dừng giữa chừng thì chạy lại đúng lệnh bước 3. Sự kiện đã có `summary/` được bỏ qua; sự kiện đang làm dở phải chạy lại từ đầu.
- Cào thêm link cho một sự kiện đã phân tích: xoá `summary/<mã sự kiện>.json` trong thư mục kết quả rồi chạy lại.
- **Mỗi nguồn dữ liệu một thư mục kết quả riêng.** Hai nguồn có cùng mã sự kiện mà ghi chung thư mục thì nguồn sau bị bỏ qua.

### C3. Kết quả
Trong `<thư mục kết quả>/`:
- `summary/<mã sự kiện>.json`: thống kê cảm xúc, độc hại, top comment.
- `full/<mã sự kiện>.json`: nhãn của từng comment, theo cụm.
- `run_log.jsonl`: nhật ký mỗi lần chạy (số request, sự kiện xong, sự kiện lỗi).

---

## D. Prompt dán cho trợ lý AI

Mở trợ lý AI trong thư mục repo, dán từng prompt khi cần. Thay phần trong `<...>`.

**D1. Kiểm tra cài đặt**
```text
Repo này là NCKH_hong_drama. Đọc docs/huong-dan-team-cao-va-phan-tich.md mục A.
Kiểm tra máy tôi đã đủ: Python 3.10+, thư viện websockets + openpyxl + pytest, file .env.local (chỉ kiểm có dòng 4 "API_key=" và dòng 5, KHÔNG in key ra) và model_list.txt.
Chạy pytest cho ingestion/tests và analysis_new/tests. Báo cái gì thiếu và lệnh để cài. Không sửa code.
```

**D2. Cào bình luận theo bảng**
```text
Đọc docs/huong-dan-team-cao-va-phan-tich.md mục B.
Bảng link của tôi ở <đường dẫn file .xlsx>. Kiểm tra bảng có đủ cột "Mã sự kiện" và "Link Facebook", in trạng thái bằng lệnh --list (thêm --sheet nếu không phải file mặc định).
Sau đó đưa tôi lệnh cào để tôi tự chạy trong terminal (nếu nhiều link thì đưa lệnh 2 terminal: một --reverse, một --port 9223).
Không tự chạy lệnh cào, không sửa code.
```

**D3. Kiểm tra tiến độ hoặc sự cố khi đang cào**
```text
Tôi đang cào bằng ingestion/crawl_links_from_sheet.py (bảng <đường dẫn>). Kiểm tra giúp:
in --list; liệt kê các file .crawl.lock trong FB_Crawl_skills/data/posts và tiến trình python nào đang chạy crawler;
đọc checkpoint.json / manifest.json của link đang cào để xem có đứng yên hay lỗi không.
Nếu có khoá mà tiến trình đã chết thì báo tôi trước khi xoá. Không sửa code.
```

**D4. Phân tích dữ liệu**
```text
Đọc docs/huong-dan-team-cao-va-phan-tich.md mục C.
Dữ liệu cần phân tích: <data/crawled-events hoặc thư mục chứa file sự kiện .json>. Thư mục kết quả: <data/analysis-new-output/ten-rieng>.
1) Nếu là dữ liệu tự cào thì chạy ingestion/crawled_posts_to_analysis_events.py trước.
2) Chạy dry-run (không --yes), báo số sự kiện, số comment, số request dự kiến và thời gian ước tính (~3 phút/request).
3) Đưa tôi lệnh chạy thật có --max-requests phù hợp để tôi tự chạy trong terminal. Không tự gọi API.
```

**D5. Đọc kết quả**
```text
Đọc các file summary/*.json trong <thư mục kết quả>. Lập bảng mỗi sự kiện: tổng comment, số comment rác,
phân bố cảm xúc (%), số comment độc hại, và 3 comment nổi bật nhất. Ghi chú sự kiện nào có quá ít comment (< 50) để không kết luận vội.
Không sửa file.
```
