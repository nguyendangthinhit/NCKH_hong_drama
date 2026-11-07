"""FastAPI service cho chatbot. Chạy: uvicorn app:app --port 8010 (trong thư mục này)."""
import logging
import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AliasChoices, BaseModel, Field

from chat_pipeline import ChatPipeline
from config import load_settings
from event_store import EventStore
from insight_context import InsightStore
from llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = load_settings()
state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    events = EventStore.load(
        {"showbiz": settings.showbiz_file, "education": settings.education_file}
    )
    insights = InsightStore.load(settings.insights_file)
    http = httpx.AsyncClient()
    state["pipeline"] = ChatPipeline(events, insights, LLMClient(settings, http))
    logging.getLogger("chat_agent").info("Đã nạp %d sự kiện", len(events.events))
    yield
    await http.aclose()


app = FastAPI(title="Drama chat agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-Agent-Key"],
)


class ChatRequest(BaseModel):
    # Web gửi "userId", n8n/Messenger có thể gửi "user_id": nhận cả hai.
    user_id: str = Field(
        default="anonymous", max_length=128, validation_alias=AliasChoices("user_id", "userId")
    )
    message: str = Field(max_length=2000)
    source: str = Field(default="web", max_length=32)


class ChatResponse(BaseModel):
    reply: str
    intent: str
    event_ids: list[str]
    timings_ms: dict[str, float]


@app.get("/health")
async def health():
    return {"status": "ok", "events": len(state["pipeline"].events.events)}


def _is_direct_local(request: Request) -> bool:
    """Request gọi thẳng từ máy này (web local). Đi qua tunnel (ngrok) luôn có X-Forwarded-For."""
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1") and "x-forwarded-for" not in request.headers


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest, request: Request, x_agent_key: str | None = Header(default=None)
):
    # Trình duyệt không giữ được khoá bí mật -> chỉ bắt khoá với request từ ngoài (qua tunnel).
    needs_key = settings.agent_api_key and not _is_direct_local(request)
    if needs_key and not secrets.compare_digest(x_agent_key or "", settings.agent_api_key):
        raise HTTPException(status_code=401, detail="Sai hoặc thiếu X-Agent-Key")
    result = await state["pipeline"].handle(f"{req.source}:{req.user_id}", req.message)
    return ChatResponse(
        reply=result.reply,
        intent=result.intent,
        event_ids=result.event_ids,
        timings_ms=result.timings_ms,
    )
