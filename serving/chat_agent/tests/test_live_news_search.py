"""Tra tin web (Firecrawl) trong pipeline: tool giả để không tốn credit; kiểm định tuyến, ngữ cảnh, nguồn.
Port của serving/chat_agent_worker/tests/live-news-search.test.ts.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import intent_rules as rules  # noqa: E402
from chat_pipeline import ChatPipeline  # noqa: E402
from config import load_settings  # noqa: E402
from event_store import EventStore  # noqa: E402
from insight_context import InsightStore  # noqa: E402
from live_news_search import LiveNewsSearch, NewsItem, clean_article_markdown  # noqa: E402
from news_search_query import build_search_query, event_search_query, search_keywords  # noqa: E402

SETTINGS = load_settings()
STORE = EventStore.load({"showbiz": SETTINGS.showbiz_file, "education": SETTINGS.education_file})
INSIGHTS = InsightStore.load(SETTINGS.insights_file)
ITEM = NewsItem("Ca sĩ X bị chỉ trích vì phát ngôn", "https://kenh14.vn/bai-1", "kenh14.vn",
                "2 days ago", "Nội dung bài báo về phát ngôn của ca sĩ X gây tranh cãi trên mạng xã hội.")


class FakeNews:
    """Tool giả: ghi lại các lần gọi, trả danh sách cho trước."""

    def __init__(self, items):
        self.items, self.calls = items, []

    async def __call__(self, query, recent):
        self.calls.append((query, recent))
        return list(self.items)


class CaptureLLM:
    """LLM giả: lưu prompt để kiểm ngữ cảnh đưa vào."""

    def __init__(self):
        self.prompts = []

    async def generate(self, _system, user):
        self.prompts.append(user)
        return "trả lời", "test"


def make(items):
    news, llm = FakeNews(items), CaptureLLM()
    return ChatPipeline(STORE, INSIGHTS, llm, news), news, llm


def ask(pipeline, message, user="u1"):
    return asyncio.run(pipeline.handle(user, message))


def test_latest_rule():
    assert rules.is_latest_request("Shark Bình mới nhất ra sao")
    assert rules.is_latest_request("drama showbiz gần đây")
    assert rules.is_latest_request("giáo dục có drama gì mới không")
    assert not rules.is_latest_request("Mailisa")


def test_not_in_local_store_searches_web_with_sources():
    p, news, llm = make([ITEM])
    r = ask(p, "drama của miu lê")
    assert r.intent == "live_news"
    assert news.calls == [("miu lê", False)]
    assert "TIN MỚI TỪ WEB" in llm.prompts[0] and ITEM.content in llm.prompts[0]
    assert "Nguồn tin:\nhttps://kenh14.vn/bai-1" in r.reply
    assert r.timings_ms["web"] >= 0


def test_no_web_results_keeps_clarify_and_unrelated_skips_web():
    p, _, _ = make([])
    assert ask(p, "drama của miu lê").intent == "clarify"
    p, news, _ = make([ITEM])
    assert ask(p, "giá vàng hôm nay").intent == "unrelated"
    assert news.calls == []


def test_known_event_latest_merges_local_and_web():
    p, news, llm = make([ITEM])
    r = ask(p, "Mailisa có tin gì mới nhất")
    ev = STORE.match("Mailisa").events[0]
    assert r.intent == "event_live" and r.event_ids[0] == ev.id
    assert news.calls[0] == ("Mailisa", True)
    assert ev.title in llm.prompts[0] and "TIN MỚI TỪ WEB" in llm.prompts[0]
    p, news, _ = make([ITEM])
    assert ask(p, "Mailisa").intent == "event" and news.calls == []  # không hỏi mới nhất: không tốn credit


def test_hot_recently_prefers_web_then_falls_back_to_local_top():
    q = "drama nào đang hot gần đây"
    assert ask(make([ITEM])[0], q).intent == "live_news"
    assert ask(make([])[0], q).intent == "insights_top"


def test_followup_latest_uses_event_in_session():
    p, news, _ = make([ITEM])
    first = ask(p, "Jack J97 và Thiên An")
    r = ask(p, "có gì mới không")
    assert r.intent == "event_followup_live" and r.event_ids == first.event_ids
    assert news.calls == [("Jack J97", True)]


@pytest.mark.parametrize("question, keywords", [
    ("Shark Bình có tin gì mới nhất", "Shark Bình"),
    ("drama của Miu Lê", "Miu Lê"),
    ("Hiền Hồ dạo này thế nào rồi?", "Hiền Hồ"),
    ("cô giáo bị tố đánh học sinh gần đây", "cô giáo tố đánh học sinh"),
    ("Nhật Kim Anh có ồn ào gì không", "Nhật Kim Anh"),
])
def test_search_keywords(question, keywords):
    assert search_keywords(question) == keywords


def test_query_builders():
    assert build_search_query("drama showbiz nào đang hot gần đây") == "ồn ào showbiz Việt"
    assert build_search_query("giáo dục có drama gì mới không") == "giáo dục gây xôn xao"
    assert build_search_query("có drama gì mới nhất không") == "ồn ào showbiz Việt"
    jack = "Jack (J97) – tranh chấp với Thiên An liên quan việc công khai con chung"
    assert event_search_query(jack) == "Jack J97"
    assert event_search_query("Shark Bình từ 'cá mập' đến tội phạm lừa đảo, rửa tiền") == "Shark Bình từ cá mập đến"
    assert event_search_query("x – y", "Shark Bình có tin gì mới nhất") == "Shark Bình"
    assert event_search_query(jack, "vụ đó có gì mới không") == "Jack J97"


def test_tool_without_key_returns_empty():
    tool = LiveNewsSearch("", httpx.AsyncClient())
    assert asyncio.run(tool("abc", True)) == []


def test_clean_article_markdown():
    md = "\n".join([
        "[Bỏ qua đến nội dung chính](https://x.vn#content)",
        "- [Video](https://x.vn/video)",
        "![ảnh](https://x.vn/a.jpg)",
        "# Shark Bình lãnh 10 năm tù vì rửa tiền gần 320 tỉ đồng trong vụ án Mr Pips",
        "Trong vụ án Mr Pips, **Shark Bình** bị cáo buộc giúp [Mr Pips](https://x.vn/p) rửa tiền qua ví điện tử.",
        "Trong vụ án Mr Pips, **Shark Bình** bị cáo buộc giúp [Mr Pips](https://x.vn/p) rửa tiền qua ví điện tử.",
    ])
    assert clean_article_markdown(md).split("\n") == [
        "Shark Bình lãnh 10 năm tù vì rửa tiền gần 320 tỉ đồng trong vụ án Mr Pips",
        "Trong vụ án Mr Pips, Shark Bình bị cáo buộc giúp Mr Pips rửa tiền qua ví điện tử.",
    ]


def test_regression_unrelated_after_event_and_generic_latest():
    p, news, _ = make([ITEM])
    ask(p, "Mailisa")
    assert ask(p, "giá vàng hôm nay").intent == "unrelated" and news.calls == []
    p, news, _ = make([ITEM])
    assert ask(p, "drama giáo dục gần đây").intent == "live_news"
    assert news.calls == [("giáo dục gây xôn xao", True)]
    p, news, _ = make([])
    ask(p, "drama mới nhất")
    assert len(news.calls) == 1  # web rỗng thì không gọi lại lần hai
