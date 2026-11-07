"""Kiểm tra phần không gọi LLM: luật ý định, khớp sự kiện trên dữ liệu thật, định tuyến pipeline.

LLM để trống khoá -> pipeline đi tới bước LLM thì trả câu "hệ thống bận"; ta chỉ kiểm intent/event_ids.
"""
import asyncio
import dataclasses
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
from llm_client import LLMClient  # noqa: E402

SETTINGS = load_settings()
STORE = EventStore.load({"showbiz": SETTINGS.showbiz_file, "education": SETTINGS.education_file})


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def pipeline():
    no_llm = dataclasses.replace(SETTINGS, groq_keys=[], gemini_keys=[])
    insights = InsightStore.load(SETTINGS.insights_file)
    return ChatPipeline(STORE, insights, LLMClient(no_llm, httpx.AsyncClient()))


def test_rules_basic():
    assert rules.is_greeting_only("hello")
    assert rules.is_greeting_only("Xin chào bạn")
    assert not rules.is_greeting_only("hello, vụ Jack là gì")
    assert rules.is_info("bạn là ai vậy")
    assert rules.is_spam("đm bot")
    assert not rules.is_spam("trường lớn nhất")  # "lớn" không phải từ tục
    assert rules.is_top_request("Top những drama được quan tâm nhất")
    assert rules.category_hint("top drama giáo dục") == "education"


@pytest.mark.parametrize(
    "question, expected_id_prefix, title_word",
    [
        ("Vụ việc học sinh Hưng Yên đạo nhái thi KHKT", "education", "đạo nhái"),
        ("Công ty của Shark Thủy nợ lương giáo viên như thế nào?", "education", "Shark Thuỷ"),
        ("cô giáo 231 cái tát", "education", "231"),
        ("Mailisa", "showbiz", "Mailisa"),
        ("Tizi và Đích Lép bị đồn đoán chuyện gì về hôn nhân?", "showbiz", "Tizi"),
    ],
)
def test_match_real_questions(question, expected_id_prefix, title_word):
    m = STORE.match(question)
    assert m.events, question
    assert m.events[0].id.startswith(expected_id_prefix)
    assert title_word.lower() in m.events[0].title.lower()


def test_person_with_many_events_returns_group():
    m = STORE.match("Thông tin về drama của Viruss")
    assert len(m.events) >= 2
    assert all("viruss" in e.title.lower() for e in m.events[:2])


@pytest.mark.parametrize("question", ["sự kiện của miu lê", "giá vàng hôm nay", "Xin chào"])
def test_no_false_match(question):
    assert STORE.match(question).events == []


def test_pipeline_fixed_replies(pipeline):
    assert run(pipeline.handle("u1", "hello")).intent == "greeting"
    assert run(pipeline.handle("u1", "bạn làm được gì")).intent == "info"
    assert run(pipeline.handle("u1", "giá vàng hôm nay")).intent == "unrelated"
    assert run(pipeline.handle("u1", "drama của miu lê")).intent == "clarify"


def test_pipeline_insights_and_followup(pipeline):
    assert run(pipeline.handle("u2", "Top những drama được quan tâm nhất")).intent == "insights_top"
    assert run(pipeline.handle("u2", "có drama giáo dục nào không")).intent == "insights_top"
    first = run(pipeline.handle("u2", "Vì sao Trường Quốc tế Mỹ bị giải thể?"))
    assert first.intent == "event" and first.event_ids
    follow = run(pipeline.handle("u2", "dư luận phản ứng thế nào về vụ đó"))
    assert follow.intent == "event_followup"
    assert follow.event_ids == first.event_ids
