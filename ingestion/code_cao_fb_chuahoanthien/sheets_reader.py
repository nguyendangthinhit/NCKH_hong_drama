"""
sheets_reader.py
Đọc dữ liệu từ Google Sheets và trả về danh sách task scrape.

Cấu trúc sheet:
| Danh mục | id_content             | Tên sự kiện | links                        |
|----------|------------------------|-------------|------------------------------|
| showbiz  | showbiz_001_20250601   | Vụ XYZ      | https://fb.com/... https://  |
| educate  | educate_001_20250601   | Vụ ABC      | (trống = không có FB post)   |

Output trả về:
[
    {
        "id_content": "showbiz_001_20250601",
        "category": "showbiz",
        "event_name": "Vụ XYZ",
        "urls": ["https://fb.com/...", "https://fb.com/..."]
    },
    ...
]
Những sự kiện không có links sẽ bị bỏ qua hoàn toàn.
"""

import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _get_service():
    """Khởi tạo Google Sheets API service từ credentials file."""
    creds = Credentials.from_service_account_file(
        config.GOOGLE_CREDENTIALS_FILE,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def _parse_links(raw: str) -> list[str]:
    """
    Parse chuỗi links từ 1 ô — các URL cách nhau bằng space.
    Lọc bỏ chuỗi rỗng và khoảng trắng thừa.
    """
    if not raw or not raw.strip():
        return []
    parts = raw.strip().split()
    return [p.strip() for p in parts if p.strip().startswith("http")]


def read_tasks(sheet_name: str) -> list[dict]:
    """
    Đọc sheet theo tên, trả về danh sách task cần scrape.
    Bỏ qua các row không có links.

    Args:
        sheet_name: Tên sheet trong file (SHEET_NAME_TEST hoặc SHEET_NAME_REAL)

    Returns:
        list of dict: [{ id_content, category, event_name, urls }]
    """
    logger.info(f"Đọc Google Sheets: sheet='{sheet_name}'")

    service = _get_service()
    sheet   = service.spreadsheets()

    # Đọc toàn bộ dữ liệu từ sheet
    result = sheet.values().get(
        spreadsheetId=config.GOOGLE_SHEETS_ID,
        range=sheet_name,
    ).execute()

    rows = result.get("values", [])
    if not rows:
        logger.warning("Sheet trống hoặc không có dữ liệu.")
        return []

    # Dòng đầu tiên = header
    headers = [h.strip() for h in rows[0]]
    logger.info(f"Headers: {headers}")

    # Map tên cột → index
    try:
        idx_category   = headers.index(config.COL_CATEGORY)
        idx_id_content = headers.index(config.COL_ID_CONTENT)
        idx_event_name = headers.index(config.COL_EVENT_NAME)
        idx_links      = headers.index(config.COL_LINKS)
    except ValueError as e:
        raise ValueError(
            f"Không tìm thấy cột trong sheet: {e}. "
            f"Kiểm tra lại tên cột trong config.py"
        )

    tasks = []
    skipped = 0

    for i, row in enumerate(rows[1:], start=2):  # Bỏ qua header
        # Đảm bảo row đủ cột (có thể row cuối bị thiếu)
        def get_cell(idx):
            return row[idx].strip() if idx < len(row) else ""

        category   = get_cell(idx_category)
        id_content = get_cell(idx_id_content)
        event_name = get_cell(idx_event_name)
        links_raw  = get_cell(idx_links)

        # Bỏ qua row không có id_content
        if not id_content:
            continue

        urls = _parse_links(links_raw)

        # Bỏ qua sự kiện không có links FB
        if not urls:
            logger.debug(f"  Row {i} [{id_content}]: không có links, bỏ qua.")
            skipped += 1
            continue

        tasks.append({
            "id_content": id_content,
            "category":   category,
            "event_name": event_name,
            "urls":       urls,
        })

        logger.info(f"  Row {i} [{id_content}]: {len(urls)} links")

    logger.info(
        f"Tổng: {len(tasks)} sự kiện có links, "
        f"{skipped} sự kiện không có links (bỏ qua)."
    )
    return tasks
