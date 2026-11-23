"""Luồng xử lý một tin nhắn: luật -> khớp sự kiện/insight (+ tra tin web khi cần) -> đúng 1 lần LLM.
Ghi thời gian từng bước."""
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import intent_rules as rules
from answer_prompt import SYSTEM_PROMPT, build_user_prompt
from event_store import EventStore
from insight_context import InsightStore, event_text
from live_news_search import NewsItem, news_context_text, sources_text
from llm_client import LLMClient, LLMUnavailable
from news_search_query import (build_search_query, event_search_query, is_generic_question,
                               is_subjectless_latest_request, search_keywords)
from session_memory import SessionMemory

log = logging.getLogger("chat_agent.pipeline")

# Câu hỏi top/thống kê mà vẫn khớp mạnh một sự kiện (vd. "vụ X có bao nhiêu bình luận")
# thì trả lời theo sự kiện thay vì số liệu toàn hệ thống.
STRONG_EVENT_SCORE = 20.0
LLM_DOWN_REPLY = "Hệ thống đang bận, bạn thử hỏi lại sau ít phút nhé."

# Tool tra tin web: (câu tìm, chỉ tin 1 tuần?) -> danh sách tin. Xem live_news_search.LiveNewsSearch.
NewsFn = Callable[[str, bool], Awaitable[list[NewsItem]]]


async def _no_news(_query: str, _recent: bool) -> list[NewsItem]:
    return []


@dataclass
class ChatResult:
    reply: str
    intent: str
    event_ids: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    provider: str = ""


class ChatPipeline:
    def __init__(
        self, events: EventStore, insights: InsightStore, llm: LLMClient, news: NewsFn = _no_news
    ):
        self.events = events
        self.insights = insights
        self.llm = llm
        self.news = news
        self.memory = SessionMemory()

    async def _search(self, timings: dict, query: str, recent: bool) -> list[NewsItem]:
        t = time.perf_counter()
        items = await self.news(query, recent)
        timings["web"] = round((time.perf_counter() - t) * 1000, 1)
        return items

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
        timings = {"match": round((time.perf_counter() - t) * 1000, 1)}
        category = rules.category_hint(message)
        wants_top = rules.is_top_request(message)
        wants_stats = rules.is_stats_request(message)
        subjectless_latest = is_subjectless_latest_request(message)
        wants_latest = rules.is_latest_request(message) or subjectless_latest
        weak_event = match.score < STRONG_EVENT_SCORE
        no_strong_event = not match.events or weak_event
        in_scope = rules.mentions_drama(message) or category is not None
        web_tried = False

        # Hỏi tin mới chung chung ("drama nào hot gần đây", "drama giáo dục gần đây"): kho local là
        # số liệu cũ và chỉ khớp yếu -> ưu tiên tin web; web rỗng thì đi tiếp luồng cũ.
        generic = in_scope and is_generic_question(message)
        if wants_latest and no_strong_event and (wants_top or generic):
            web_tried = True
            items = await self._search(timings, build_search_query(message), True)
            if items:
                context = news_context_text(items)
                return await self._answer(user_id, message, context, "live_news", [], timings, items)

        if (wants_top or wants_stats) and no_strong_event:
            context = (
                self.insights.top_events_text(category)
                if wants_top
                else self.insights.stats_text(category)
            )
            intent = "insights_top" if wants_top else "insights_stats"
            return await self._answer(user_id, message, context, intent, [], timings)

        events = match.events
        intent = "event"
        # Câu hỏi nối tiếp ("vụ đó", "dư luận thế nào"): ưu tiên sự kiện đang bàn trong phiên,
        # trừ khi câu hỏi khớp mạnh một sự kiện khác.
        session = self.memory.get(user_id)
        previous = [self.events.by_id[i] for i in session.last_event_ids if i in self.events.by_id]
        if subjectless_latest and not previous:
            return ChatResult(rules.CLARIFY_REPLY, "clarify", timings_ms=timings)
        refers_back = rules.is_followup(message) and (not events or weak_event)
        opinion_only = not events and rules.is_opinion_request(message)
        # "có gì mới không": hỏi tin mới mà không nêu chủ thể nào -> về sự kiện đang bàn.
        # ("giá vàng hôm nay" có từ khoá riêng nên không bị kéo về sự kiện cũ.)
        latest_followup = subjectless_latest or (
            wants_latest and not events and not in_scope and not search_keywords(message)
        )
        if previous and (refers_back or opinion_only or latest_followup):
            events, intent = previous, "event_followup"
        if events:
            with_stats = rules.is_opinion_request(message) or wants_stats
            context = "\n\n---\n\n".join(event_text(e, with_stats) for e in events)
            ids = [e.id for e in events]
            # Hỏi diễn biến mới của sự kiện đã có: ghép thêm tin web (theo chủ thể sự kiện đầu tiên).
            if wants_latest:
                direct = message if intent == "event" else None
                items = await self._search(timings, event_search_query(events[0].title, direct), True)
                if items:
                    context += "\n\n---\n\n" + news_context_text(items)
                    return await self._answer(
                        user_id, message, context, f"{intent}_live", ids, timings, items
                    )
            return await self._answer(user_id, message, context, intent, ids, timings)

        # Kho local không có: thay vì trả "chưa có", tra tin trên web nếu câu hỏi thuộc phạm vi drama.
        if in_scope:
            items = [] if web_tried else await self._search(
                timings, build_search_query(message), wants_latest
            )
            if items:
                context = news_context_text(items)
                return await self._answer(user_id, message, context, "live_news", [], timings, items)
            return ChatResult(rules.CLARIFY_REPLY, "clarify", timings_ms=timings)
        return ChatResult(rules.UNRELATED_REPLY, "unrelated", timings_ms=timings)

    async def _answer(
        self, user_id: str, question: str, context: str, intent: str,
        event_ids: list[str], timings: dict, web_items: list[NewsItem] | None = None,
    ) -> ChatResult:
        history = list(self.memory.get(user_id).turns)
        prompt = build_user_prompt(question, context, history)
        t = time.perf_counter()
        try:
            reply, provider = await self.llm.generate(SYSTEM_PROMPT, prompt)
            reply += sources_text(web_items or [])
        except LLMUnavailable as exc:
            log.error("LLM không khả dụng: %s", exc)
            reply, provider = LLM_DOWN_REPLY, ""
        llm_ms = round((time.perf_counter() - t) * 1000, 1)
        return ChatResult(reply, intent, event_ids, {**timings, "llm": llm_ms}, provider)
