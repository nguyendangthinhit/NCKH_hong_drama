"""Đọc/ghi bảng link cần cào (mặc định FB_Crawl_skills/data/cao.xlsx) và cột trạng thái pending/done.

Cột được tìm theo TÊN tiêu đề (không phân biệt hoa thường/dấu), thứ tự cột tuỳ ý:
    Mã sự kiện | Tên sự kiện | Trang hoặc nhóm đăng | Link Facebook | Số bình luận (số) | Trạng thái
("Số bình luận hiển thị" dùng thay nếu không có cột "(số)"; thiếu cột "Trạng thái" thì script thêm vào.)
Trạng thái: pending = chưa cào, done = đã cào xong.

Hỗ trợ .xlsx (ghi thẳng vào ô, giữ định dạng file) và text tách tab .xls/.tsv/.txt (đọc/ghi latin-1).
"""

import csv
import io
import os
import unicodedata
from pathlib import Path

PENDING, DONE = "pending", "done"
_HEADERS = {  # khoá nội bộ -> các tên tiêu đề chấp nhận (đã bỏ dấu, viết thường)
    "event_id": ["ma su kien"], "event_name": ["ten su kien"], "page": ["trang hoac nhom dang"],
    "url": ["link facebook"], "n_comments": ["so binh luan (so)", "so binh luan hien thi"],
    "status": ["trang thai"],
}
_REQUIRED = ["event_id", "url"]
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"  # file .xls nhị phân thật (Excel 97-2003)


def _norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").lower().split())


def _to_int(v) -> int:
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


class CrawlSheet:
    """Bảng link + trạng thái. Dùng: s = CrawlSheet.load(p); s.rows(); s.set_status(i, DONE); s.save()."""

    def __init__(self, path: Path, header: list, data: list, kind: str, ws=None, wb=None):
        self.path, self.header, self.data, self.kind, self.ws, self.wb = path, header, data, kind, ws, wb
        normed = [_norm(h) for h in header]
        self.col = {}
        for key, names in _HEADERS.items():
            for name in names:  # ưu tiên theo thứ tự trong _HEADERS
                if name in normed:
                    self.col[key] = normed.index(name)
                    break
        missing = [k for k in _REQUIRED if k not in self.col]
        if missing:
            raise ValueError(f"{path}: thiếu cột {[_HEADERS[k][0] for k in missing]}; tiêu đề hiện có: {header}")
        self.has_status_col = "status" in self.col
        if not self.has_status_col:
            self.col["status"] = len(self.header)
            self.header.append("Trạng thái")
            if ws is not None:
                ws.cell(row=1, column=self.col["status"] + 1, value="Trạng thái")
        width = len(self.header)
        for r in self.data:
            r += [""] * (width - len(r))
            if not str(r[self.col["status"]] or "").strip():
                r[self.col["status"]] = PENDING

    @classmethod
    def load(cls, path) -> "CrawlSheet":
        path = Path(path)
        raw = path.read_bytes()
        if raw.startswith(_OLE_MAGIC):
            raise ValueError(f"{path}: là file .xls nhị phân. Hãy lưu lại dạng .xlsx rồi chạy lại.")
        if path.suffix.lower() == ".xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(path)
            ws = wb.active
            table = [["" if v is None else v for v in row] for row in ws.iter_rows(values_only=True)]
            if not table:
                raise ValueError(f"{path}: file rỗng")
            # giữ cả dòng trống để chỉ số dòng khớp với ô trong sheet
            return cls(path, list(table[0]), [list(r) for r in table[1:]], "xlsx", ws, wb)
        table = [r for r in csv.reader(io.StringIO(raw.decode("latin-1")), delimiter="\t") if any(r)]
        if not table:
            raise ValueError(f"{path}: file rỗng")
        return cls(path, list(table[0]), [list(r) for r in table[1:]], "tsv")

    def rows(self) -> list:
        """Danh sách dict cho từng dòng có link (index = vị trí trong self.data)."""
        out = []
        for i, r in enumerate(self.data):
            d = {k: str(r[j] if j < len(r) else "").strip() for k, j in self.col.items()}
            if not d["url"].startswith("http"):
                continue  # dòng trống / dòng ghi chú
            d.setdefault("event_name", "")
            d.setdefault("page", "")
            d["n_comments"] = _to_int(d.get("n_comments"))
            d["status"] = d["status"].lower()
            d["index"] = i
            out.append(d)
        return out

    def set_status(self, index: int, status: str) -> None:
        self.data[index][self.col["status"]] = status
        if self.ws is not None:
            self.ws.cell(row=index + 2, column=self.col["status"] + 1, value=status)

    @classmethod
    def mark(cls, path, url: str, status: str) -> None:
        """Đọc lại file rồi chỉ đổi trạng thái dòng có link này -> nhiều terminal cùng ghi không đè nhau."""
        sheet = cls.load(path)
        for r in sheet.rows():
            if r["url"] == url:
                sheet.set_status(r["index"], status)
        sheet.save()

    def save(self) -> None:
        """Ghi đè file (qua file tạm rồi thay thế). Excel đang mở file thì báo lỗi rõ."""
        tmp = self.path.with_name(self.path.stem + ".tmp" + self.path.suffix)
        if self.kind == "xlsx":
            for i in range(len(self.data)):  # ô trạng thái còn trống -> pending
                cell = self.ws.cell(row=i + 2, column=self.col["status"] + 1)
                if cell.value in (None, "") and str(self.data[i][self.col["status"]]).strip():
                    cell.value = self.data[i][self.col["status"]]
            self.wb.save(tmp)
        else:
            buf = io.StringIO()
            csv.writer(buf, delimiter="\t", lineterminator="\r\n").writerows([self.header] + self.data)
            tmp.write_bytes(buf.getvalue().encode("latin-1"))
        try:
            os.replace(tmp, self.path)
        except PermissionError as e:
            tmp.unlink(missing_ok=True)
            raise PermissionError(f"Không ghi được {self.path} (đang mở trong Excel?). "
                                  "Đóng file rồi chạy lại.") from e
