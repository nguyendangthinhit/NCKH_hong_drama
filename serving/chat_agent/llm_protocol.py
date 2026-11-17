"""Payload và giải mã phản hồi provider, dùng chung cho JSON và streaming."""
import json


class ProviderReplyError(ValueError):
    """Phản hồi bị chặn, thiếu dữ liệu hoặc chưa hoàn tất."""


def make_request(settings, provider, key, system, user, streaming=False):
    if provider == "groq":
        body = {
            "model": settings.groq_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.3, "max_tokens": 700,
        }
        if "gpt-oss" in settings.groq_model:
            body.update(reasoning_effort="low", include_reasoning=False)
        elif "qwen" in settings.groq_model:
            body["reasoning_effort"] = "none"
        if streaming:
            body["stream"] = True
        return "https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {key}"}, body
    method = "streamGenerateContent?alt=sse" if streaming else "generateContent"
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:{method}",
        {"x-goog-api-key": key},
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
        },
    )


def decode_reply(provider, data):
    """Chỉ lấy văn bản người dùng được xem; không phát thought/signature."""
    if not isinstance(data, dict) or data.get("error"):
        raise ProviderReplyError("invalid provider response")
    if provider == "groq":
        choices = data.get("choices") or []
        if not choices:
            return "", None
        candidate = choices[0]
        if not isinstance(candidate, dict):
            raise ProviderReplyError("invalid candidate")
        finish = candidate.get("finish_reason")
        message = candidate.get("delta", candidate.get("message")) or {}
        if not isinstance(message, dict):
            raise ProviderReplyError("invalid message")
        content = message.get("content") or ""
    else:
        if (data.get("promptFeedback") or {}).get("blockReason"):
            raise ProviderReplyError("blocked prompt")
        candidates = data.get("candidates") or []
        if not candidates:
            return "", None
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ProviderReplyError("invalid candidate")
        finish = candidate.get("finishReason")
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            raise ProviderReplyError("invalid content")
        content = "".join(
            part["text"] for part in (content.get("parts") or [])
            if isinstance(part, dict) and not part.get("thought") and isinstance(part.get("text"), str)
        )
    if finish and finish not in ("STOP", "stop"):
        raise ProviderReplyError(f"unfinished response: {finish}")
    if not isinstance(content, str):
        raise ProviderReplyError("non-text response")
    return content, finish


async def sse_payloads(response):
    """HTTPX giữ ranh giới UTF-8/dòng; ghép data nhiều dòng trước khi parse."""
    lines, size = [], 0
    async for line in response.aiter_lines():
        if not line:
            if lines:
                yield "\n".join(lines)
            lines, size = [], 0
        elif line.startswith("data:"):
            value = line[5:].removeprefix(" ")
            size += len(value)
            if size > 1_048_576:
                raise ProviderReplyError("provider event too large")
            lines.append(value)
    if lines:
        raise ProviderReplyError("incomplete provider event")


def parse_payload(payload):
    return None if payload == "[DONE]" else json.loads(payload)
