"""FastAPI service cho chatbot. Chạy: uvicorn app:app --port 8010 (trong thư mục này)."""
import logging
import secrets
import json
from contextlib import aclosing, asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AliasChoices, BaseModel, Field
from fastapi.responses import StreamingResponse

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


def check_agent_key(request: Request, x_agent_key: str | None):
    # Trình duyệt không giữ được khoá bí mật -> chỉ bắt khoá với request từ ngoài (qua tunnel).
    needs_key = settings.agent_api_key and not _is_direct_local(request)
    if needs_key and not secrets.compare_digest(x_agent_key or "", settings.agent_api_key):
        raise HTTPException(status_code=401, detail="Sai hoặc thiếu X-Agent-Key")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest, request: Request, x_agent_key: str | None = Header(default=None)
):
    check_agent_key(request, x_agent_key)
    result = await state["pipeline"].handle(f"{req.source}:{req.user_id}", req.message)
    return ChatResponse(
        reply=result.reply,
        intent=result.intent,
        event_ids=result.event_ids,
        timings_ms=result.timings_ms,
    )


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest, request: Request, x_agent_key: str | None = Header(default=None)
):
    check_agent_key(request, x_agent_key)

    async def events():
        try:
            # StreamingResponse hủy generator khi client ngắt; aclosing đóng upstream.
            async with aclosing(state["pipeline"].handle_stream(f"{req.source}:{req.user_id}", req.message)) as stream:
                async for item in stream:
                    yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
        except Exception as error:
            logging.getLogger("chat_agent").error("Stream lỗi: %s", type(error).__name__)
            data = json.dumps({"code": "internal_error", "message": "Chatbot đang gặp sự cố. Bạn thử lại nhé."}, ensure_ascii=False)
            yield f"event: error\ndata: {data}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
