"""Luồng xử lý một tin nhắn: luật -> khớp sự kiện/insight -> đúng 1 lần LLM. Ghi thời gian từng bước."""
import logging
import time
from dataclasses import dataclass, field

import intent_rules as rules
from answer_prompt import SYSTEM_PROMPT, build_user_prompt
from event_store import EventStore
from insight_context import InsightStore, event_text
from llm_client import LLMClient, LLMUnavailable
from session_memory import SessionMemory

log = logging.getLogger("chat_agent.pipeline")

# Câu hỏi top/thống kê mà vẫn khớp mạnh một sự kiện (vd. "vụ X có bao nhiêu bình luận")
# thì trả lời theo sự kiện thay vì số liệu toàn hệ thống.
STRONG_EVENT_SCORE = 20.0
LLM_DOWN_REPLY = "Hệ thống đang bận, bạn thử hỏi lại sau ít phút nhé."


@dataclass
class ChatResult:
    reply: str
    intent: str
    event_ids: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    provider: str = ""


class ChatPipeline:
    def __init__(self, events: EventStore, insights: InsightStore, llm: LLMClient):
        self.events = events
        self.insights = insights
        self.llm = llm
        self.memory = SessionMemory()

    async def handle(self, user_id: str, message: str) -> ChatResult:
        t0 = time.perf_counter()
        result = await self._route(user_id, message.strip())
        result.timings_ms["total"] = round((time.perf_counter() - t0) * 1000, 1)
        self.memory.record(user_id, message, result.reply, result.event_ids)
        log.info(
            "user=%s intent=%s events=%s provider=%s timings=%s",
            user_id, result.intent, result.event_ids, result.provider, result.timings_ms,
        )
        return result

    async def _route(self, user_id: str, message: str) -> ChatResult:
        if rules.is_spam(message):
            return ChatResult(rules.SPAM_REPLY, "spam")
        if rules.is_greeting_only(message):
            return ChatResult(rules.GREETING_REPLY, "greeting")
        if rules.is_info(message):
            return ChatResult(rules.INFO_REPLY, "info")

        t = time.perf_counter()
        match = self.events.match(message)
        match_ms = round((time.perf_counter() - t) * 1000, 1)
        category = rules.category_hint(message)
        wants_top = rules.is_top_request(message)
        wants_stats = rules.is_stats_request(message)
        weak_event = match.score < STRONG_EVENT_SCORE

        if (wants_top or wants_stats) and (not match.events or weak_event):
            context = (
                self.insights.top_events_text(category)
                if wants_top
                else self.insights.stats_text(category)
            )
            intent = "insights_top" if wants_top else "insights_stats"
            return await self._answer(user_id, message, context, intent, [], match_ms)

        events = match.events
        intent = "event"
        # Câu hỏi nối tiếp ("vụ đó", "dư luận thế nào"): ưu tiên sự kiện đang bàn trong phiên,
        # trừ khi câu hỏi khớp mạnh một sự kiện khác.
        session = self.memory.get(user_id)
        previous = [self.events.by_id[i] for i in session.last_event_ids if i in self.events.by_id]
        refers_back = rules.is_followup(message) and (not events or weak_event)
        opinion_only = not events and rules.is_opinion_request(message)
        if previous and (refers_back or opinion_only):
            events, intent = previous, "event_followup"
        if events:
            with_stats = rules.is_opinion_request(message) or wants_stats
            context = "\n\n---\n\n".join(event_text(e, with_stats) for e in events)
            ids = [e.id for e in events]
            return await self._answer(user_id, message, context, intent, ids, match_ms)

        if rules.mentions_drama(message):
            return ChatResult(rules.CLARIFY_REPLY, "clarify", timings_ms={"match": match_ms})
        return ChatResult(rules.UNRELATED_REPLY, "unrelated", timings_ms={"match": match_ms})

    async def _answer(
        self, user_id: str, question: str, context: str, intent: str,
        event_ids: list[str], match_ms: float,
    ) -> ChatResult:
        history = list(self.memory.get(user_id).turns)
        prompt = build_user_prompt(question, context, history)
        t = time.perf_counter()
        try:
            reply, provider = await self.llm.generate(SYSTEM_PROMPT, prompt)
        except LLMUnavailable as exc:
            log.error("LLM không khả dụng: %s", exc)
            reply, provider = LLM_DOWN_REPLY, ""
        llm_ms = round((time.perf_counter() - t) * 1000, 1)
        return ChatResult(
            reply, intent, event_ids, {"match": match_ms, "llm": llm_ms}, provider
        )
