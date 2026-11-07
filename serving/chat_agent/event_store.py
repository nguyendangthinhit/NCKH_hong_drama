"""Kho sự kiện trong RAM và so khớp câu hỏi với sự kiện (điểm từ vựng có trọng số IDF)."""
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from text_normalizer import terms

# Trọng số: khớp ở tiêu đề / tên nhân vật đáng tin hơn khớp trong thân bài.
TITLE_WEIGHT = 3.0
CONTENT_WEIGHT = 1.0


@dataclass
class Event:
    id: str
    category: str  # "showbiz" | "education"
    title: str
    content: str
    actors: list[dict]
    time_event: str
    analyzed: dict
    head_terms: set[str] = field(default_factory=set, repr=False)
    body_terms: set[str] = field(default_factory=set, repr=False)


# Ngưỡng chọn sự kiện (hiệu chỉnh trên câu hỏi thật trong history.json, 2026-11-05).
MIN_SCORE = 6.0  # dưới mức này coi như không khớp
BODY_ONLY_MIN = 15.0  # không trúng tiêu đề/nhân vật thì cần điểm cao hơn
GROUP_RATIO = 0.75  # sự kiện đạt >= 75% điểm cao nhất được lấy cùng (vd. một người nhiều vụ)
MAX_EVENTS = 3


@dataclass
class MatchResult:
    events: list[Event]  # rỗng nếu không khớp; phần tử đầu là khớp nhất
    score: float
    runner_up: float


class EventStore:
    def __init__(self, events: list[Event]):
        self.events = events
        self.by_id = {e.id: e for e in events}
        df: Counter = Counter()
        for e in events:
            df.update(e.head_terms | e.body_terms)
        n = len(events)
        self.idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}

    @classmethod
    def load(cls, files: dict[str, Path]) -> "EventStore":
        """files: {category: đường dẫn JSON dạng list sự kiện}."""
        events: list[Event] = []
        for category, path in files.items():
            with open(path, encoding="utf-8") as fh:
                for raw in json.load(fh):
                    actors = raw.get("actor_related") or []
                    actor_text = " ".join(
                        f"{a.get('name', '')}" for a in actors if isinstance(a, dict)
                    )
                    title = raw.get("ten_su_kien", "")
                    content = raw.get("content", "")
                    events.append(
                        Event(
                            id=raw.get("id_content", ""),
                            category=category,
                            title=title,
                            content=content,
                            actors=actors,
                            time_event=raw.get("time_event", ""),
                            analyzed=raw.get("analyzed") or {},
                            head_terms=terms(f"{title} {actor_text}"),
                            body_terms=terms(content),
                        )
                    )
        return cls(events)

    def score(self, query_terms: set[str], event: Event) -> tuple[float, bool]:
        """Trả (điểm, có trúng tiêu đề/nhân vật không)."""
        total, head_hit = 0.0, False
        for t in query_terms:
            idf = self.idf.get(t)
            if idf is None:
                continue
            if t in event.head_terms:
                total += TITLE_WEIGHT * idf
                head_hit = True
            elif t in event.body_terms:
                total += CONTENT_WEIGHT * idf
        return total, head_hit

    def match(self, question: str) -> MatchResult:
        """Tìm sự kiện khớp câu hỏi; áp ngưỡng, gom các sự kiện điểm gần nhau."""
        q = terms(question)
        scored = sorted(
            ((*self.score(q, e), e) for e in self.events),
            key=lambda item: item[0],
            reverse=True,
        )
        if not scored:
            return MatchResult([], 0.0, 0.0)
        top, top_head_hit, _ = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if top < MIN_SCORE or (not top_head_hit and top < BODY_ONLY_MIN):
            return MatchResult([], top, runner_up)
        group = [e for s, _, e in scored[:MAX_EVENTS] if s >= GROUP_RATIO * top]
        return MatchResult(group, top, runner_up)
