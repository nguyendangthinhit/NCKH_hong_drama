"""Bộ nhớ phiên trong RAM: sự kiện gần nhất và vài lượt hội thoại của từng người dùng."""
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

MAX_TURNS = 3  # số lượt (hỏi + đáp) giữ lại để LLM hiểu ngữ cảnh
TTL_SECONDS = 30 * 60
MAX_SESSIONS = 5000


@dataclass
class Session:
    last_event_ids: list[str] = field(default_factory=list)
    turns: deque = field(default_factory=lambda: deque(maxlen=MAX_TURNS))
    updated: float = field(default_factory=time.monotonic)


class SessionMemory:
    def __init__(self):
        self._sessions: OrderedDict[str, Session] = OrderedDict()

    def get(self, user_id: str) -> Session:
        now = time.monotonic()
        session = self._sessions.get(user_id)
        if session is None or now - session.updated > TTL_SECONDS:
            session = Session()
        self._sessions[user_id] = session
        self._sessions.move_to_end(user_id)
        while len(self._sessions) > MAX_SESSIONS:
            self._sessions.popitem(last=False)
        return session

    def record(self, user_id: str, question: str, answer: str, event_ids: list[str] | None):
        session = self.get(user_id)
        session.turns.append((question, answer))
        if event_ids:
            session.last_event_ids = event_ids
        session.updated = time.monotonic()
