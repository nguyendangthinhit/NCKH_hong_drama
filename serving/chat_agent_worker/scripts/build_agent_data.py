"""Dựng src/generated/agent-data.json bằng chính code Python của agent (đảm bảo chỉ mục khớp bản gốc).

Chạy: python scripts/build_agent_data.py (Python 3.11+, cần dotenv của chat_agent; dùng venv chat_agent).
Định dạng: events[] + terms{term: [idf, [chỉ số sự kiện trúng tiêu đề/nhân vật], [chỉ số chỉ trúng thân bài]]} + insights.
"""
import json
import sys
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER_DIR.parent / "chat_agent"))

from config import load_settings  # noqa: E402
from event_store import EventStore  # noqa: E402


def build() -> dict:
    s = load_settings()
    store = EventStore.load({"showbiz": s.showbiz_file, "education": s.education_file})
    terms: dict[str, list] = {}
    for term, idf in store.idf.items():
        head = [i for i, e in enumerate(store.events) if term in e.head_terms]
        # Python chấm "tiêu đề" trước, nên thân bài chỉ tính khi không trúng tiêu đề.
        body = [i for i, e in enumerate(store.events) if term in e.body_terms and term not in e.head_terms]
        terms[term] = [round(idf, 6), head, body]
    events = [
        {
            "id": e.id, "category": e.category, "title": e.title, "content": e.content,
            "actors": e.actors, "time_event": e.time_event, "analyzed": e.analyzed,
        }
        for e in store.events
    ]
    insights = json.loads(Path(s.insights_file).read_text(encoding="utf-8"))
    return {"events": events, "terms": terms, "insights": insights}


if __name__ == "__main__":
    out = WORKER_DIR / "src" / "generated" / "agent-data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(data['events'])} sự kiện, {len(data['terms'])} từ -> {out} ({out.stat().st_size // 1024} KB)")
