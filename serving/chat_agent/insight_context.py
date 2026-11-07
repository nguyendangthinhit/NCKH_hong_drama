"""Cắt lát dữ liệu thống kê (insights.json, analyzed của sự kiện) làm ngữ cảnh cho LLM."""
import json
from pathlib import Path

from event_store import Event

CATEGORY_LABEL = {"education": "Giáo dục", "showbiz": "Showbiz"}


class InsightStore:
    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def load(cls, path: Path) -> "InsightStore":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def top_events_text(self, category: str | None, limit: int = 5) -> str:
        """Danh sách sự kiện nhiều bình luận nhất của một hoặc cả hai lĩnh vực."""
        cats = [category] if category else ["education", "showbiz"]
        lines = []
        for cat in cats:
            items = self.data.get(cat, {}).get("top_events_by_comments", [])[:limit]
            lines.append(f"Top sự kiện {CATEGORY_LABEL[cat]} theo số bình luận:")
            for i, ev in enumerate(items, 1):
                lines.append(
                    f"{i}. {ev.get('ten_su_kien', '')} (tổng {ev.get('total', 0)} bình luận, "
                    f"{ev.get('clean', 0)} hợp lệ, {ev.get('trash', 0)} rác)"
                )
        return "\n".join(lines)

    def stats_text(self, category: str | None) -> str:
        """Số liệu tổng quan toàn hệ thống hoặc của một lĩnh vực."""
        overall = self.data.get("overall", {})
        parts = [f"Tổng quan hệ thống: {json.dumps(overall, ensure_ascii=False)}"]
        cats = [category] if category else ["education", "showbiz"]
        for cat in cats:
            block = {
                k: v
                for k, v in self.data.get(cat, {}).items()
                if k not in ("top_events_by_comments", "category")
            }
            parts.append(f"{CATEGORY_LABEL[cat]}: {json.dumps(block, ensure_ascii=False)}")
        return "\n".join(parts)


def event_text(event: Event, with_stats: bool) -> str:
    """Nội dung một sự kiện; kèm thống kê bình luận nếu câu hỏi về dư luận."""
    actors = ", ".join(
        f"{a.get('name', '')} ({a.get('role', '')})" for a in event.actors if isinstance(a, dict)
    )
    lines = [
        f"[{CATEGORY_LABEL.get(event.category, event.category)}] {event.title}",
        f"Thời điểm: {event.time_event or 'không rõ'}",
    ]
    if actors:
        lines.append(f"Nhân vật: {actors}")
    lines.append(f"Nội dung: {event.content}")
    if with_stats and event.analyzed:
        lines.append(
            "Thống kê bình luận dư luận: " + json.dumps(event.analyzed, ensure_ascii=False)
        )
    return "\n".join(lines)
