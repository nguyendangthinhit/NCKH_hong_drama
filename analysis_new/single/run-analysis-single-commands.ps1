# Các lệnh chạy phân tích ĐƠN LUỒNG (analysis_new) trên Windows PowerShell.
# Chạy từng dòng tại thư mục gốc repo. Dùng Python 3.14 vì các .venv đang bị Application Control chặn.
#   cd D:\py\git\NCKH_hong_drama
#   . .\analysis_new\single\run-analysis-single-commands.ps1   # chỉ nạp biến $PY, $IN, $OUT

$PY  = "C:\Users\ADMIN\AppData\Local\Python\bin\python.exe"
$IN  = "data/sample"                 # 1 file .json hoặc thư mục chứa các file sự kiện định dạng chính thức
$OUT = "data/analysis-new-output"    # kết quả: full/, summary/, run_log.jsonl

# 0. Test offline (không tốn request)
#   & $PY -m pytest analysis_new/tests -q

# 1. Kiểm tra key/API còn sống (tốn 1 request)
#   & $PY -X utf8 -m analysis_new.mmo_client --probe

# 2. Demo từng bước trên vài comment, in ra màn hình (tốn 1 request)
#   & $PY -X utf8 -m analysis_new.single.demo_step_by_step "data/sample/showbiz_068 (1).json" --orders 9 39

# 3. Dry-run: ước tính số request + ghi prompt mẫu vào $OUT/_dry_run/ (KHÔNG gọi API)
#   & $PY -X utf8 -m analysis_new.single.run_analysis_single $IN $OUT

# 4. Chạy thật; --max-requests chặn nếu dự kiến vượt số này. Sự kiện đã có summary/ sẽ bị bỏ qua.
#   & $PY -X utf8 -m analysis_new.single.run_analysis_single $IN $OUT --yes --max-requests 50

# Ép lĩnh vực khi event_id không bắt đầu bằng showbiz_/education_:
#   & $PY -X utf8 -m analysis_new.single.run_analysis_single <file.json> $OUT --domain education --yes

# ---- Dữ liệu tự cào theo bảng FB_Crawl_skills/data/cao.xlsx (cột "Trạng thái": pending = chưa cào, done = đã cào) ----
# A. Xem trạng thái các link
#   & $PY -X utf8 ingestion/crawl_links_from_sheet.py --list
# B. Cào mọi link pending (tự mở Chrome profile crawler nếu chưa mở; cào xong link nào ghi done link đó)
#   & $PY -X utf8 ingestion/crawl_links_from_sheet.py
#   & $PY -X utf8 ingestion/crawl_links_from_sheet.py --event showbiz_065 --limit 1   # thử 1 link
#   Song song: terminal 1 lệnh trên (trên xuống); terminal 2: ... crawl_links_from_sheet.py --reverse --port 9223 (dưới lên)
# C. Gộp common.jsonl của các link done -> data/crawled-events/<event_id>.json (định dạng chính thức)
#   & $PY -X utf8 ingestion/crawled_posts_to_analysis_events.py
# D. Phân tích: dry-run rồi chạy thật (sự kiện đã có summary/ bị bỏ qua -> xoá summary/<event_id>.json để chạy lại khi cào thêm link)
#   & $PY -X utf8 -m analysis_new.single.run_analysis_single data/crawled-events data/analysis-new-output/crawled
#   & $PY -X utf8 -m analysis_new.single.run_analysis_single data/crawled-events data/analysis-new-output/crawled --yes --max-requests 50
