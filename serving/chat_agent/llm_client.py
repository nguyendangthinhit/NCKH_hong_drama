"""Gọi LLM (Groq / Gemini qua REST). Lỗi một key/provider thì tự chuyển sang cái kế tiếp."""
import itertools
import logging

import httpx

from config import Settings

log = logging.getLogger("chat_agent.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_OUTPUT_TOKENS = 700
TEMPERATURE = 0.3


class LLMUnavailable(Exception):
    """Mọi provider/key đều lỗi."""


class LLMClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient):
        self.s = settings
        self.http = http
        # Xoay vòng key để chia tải giữa các key miễn phí.
        self._key_cycles = {
            "groq": itertools.cycle(settings.groq_keys) if settings.groq_keys else None,
            "gemini": itertools.cycle(settings.gemini_keys) if settings.gemini_keys else None,
        }
        self._key_counts = {"groq": len(settings.groq_keys), "gemini": len(settings.gemini_keys)}

    async def generate(self, system: str, user: str) -> tuple[str, str]:
        """Trả (văn bản, tên provider đã dùng)."""
        errors = []
        for provider in self.s.llm_order:
            cycle = self._key_cycles.get(provider)
            if cycle is None:
                continue
            # Thử tối đa 2 key mỗi provider rồi chuyển provider để giữ độ trễ thấp.
            for _ in range(min(2, self._key_counts[provider])):
                key = next(cycle)
                try:
                    call = self._groq if provider == "groq" else self._gemini
                    text = await call(key, system, user)
                    if text.strip():
                        return text.strip(), provider
                    errors.append(f"{provider}: rỗng")
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                    status = getattr(getattr(exc, "response", None), "status_code", "")
                    errors.append(f"{provider} {status} {type(exc).__name__}")
                    log.warning("LLM %s lỗi (%s %s), thử tiếp", provider, status, type(exc).__name__)
        raise LLMUnavailable("; ".join(errors) or "chưa cấu hình khoá LLM nào")

    async def _groq(self, key: str, system: str, user: str) -> str:
        model = self.s.groq_model
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_OUTPUT_TOKENS,
        }
        # Model có chế độ suy luận: giảm/tắt suy luận để trả lời nhanh, không lẫn phần suy luận.
        if "gpt-oss" in model:
            body |= {"reasoning_effort": "low", "include_reasoning": False}
        elif "qwen" in model:
            body |= {"reasoning_effort": "none"}
        resp = await self.http.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=self.s.llm_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _gemini(self, key: str, system: str, user: str) -> str:
        resp = await self.http.post(
            GEMINI_URL.format(model=self.s.gemini_model),
            headers={"x-goog-api-key": key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": TEMPERATURE,
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                },
            },
            timeout=self.s.llm_timeout_s,
        )
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
