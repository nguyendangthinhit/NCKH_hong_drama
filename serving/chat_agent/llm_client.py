"""Gọi Groq/Gemini; fallback chỉ được phép trước khi phát văn bản đầu tiên."""
import itertools
import logging
from contextlib import aclosing

import httpx

from config import Settings
from llm_protocol import ProviderReplyError, decode_reply, make_request, parse_payload, sse_payloads

log = logging.getLogger("chat_agent.llm")

PROVIDER_ERRORS = (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError)


class LLMUnavailable(Exception):
    """Provider không trả lời được hoặc stream bị ngắt/chưa hoàn tất."""


class LLMClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient):
        self.s = settings
        self.http = http
        keys = {"groq": settings.groq_keys, "gemini": settings.gemini_keys}
        self._key_cycles = {name: itertools.cycle(values) for name, values in keys.items() if values}
        self._key_counts = {name: len(values) for name, values in keys.items()}

    def _attempts(self):
        for provider in self.s.llm_order:
            cycle = self._key_cycles.get(provider)
            if cycle is not None:
                for _ in range(min(2, self._key_counts[provider])):
                    yield provider, next(cycle)

    @staticmethod
    def _error(provider, error):
        # Không log khóa, header hay toàn bộ body của provider.
        status = getattr(getattr(error, "response", None), "status_code", "")
        description = f"{provider} {status} {type(error).__name__}"
        log.warning("LLM lỗi: %s", description)
        return description

    async def generate(self, system: str, user: str) -> tuple[str, str]:
        errors = []
        for provider, key in self._attempts():
            try:
                url, headers, body = make_request(self.s, provider, key, system, user)
                response = await self.http.post(url, headers=headers, json=body, timeout=self.s.llm_timeout_s)
                response.raise_for_status()
                text, _ = decode_reply(provider, response.json())
                if text.strip():
                    return text.strip(), provider
                raise ProviderReplyError("empty reply")
            except PROVIDER_ERRORS as error:
                errors.append(self._error(provider, error))
        raise LLMUnavailable("; ".join(errors) or "chưa cấu hình khoá LLM nào")

    async def stream_generate(self, system: str, user: str):
        errors = []
        for provider, key in self._attempts():
            emitted = False
            try:
                async with aclosing(self._stream(provider, key, system, user)) as stream:
                    async for text in stream:
                        emitted = True
                        yield text, provider
                if emitted:
                    return
                raise ProviderReplyError("empty reply")
            except PROVIDER_ERRORS as error:
                description = self._error(provider, error)
                if emitted:
                    raise LLMUnavailable(description) from None
                errors.append(description)
        raise LLMUnavailable("; ".join(errors) or "chưa cấu hình khoá LLM nào")

    async def _stream(self, provider, key, system, user):
        url, headers, body = make_request(self.s, provider, key, system, user, streaming=True)
        finished = False
        async with self.http.stream(
            "POST", url, headers=headers, json=body, timeout=self.s.llm_timeout_s,
        ) as response:
            response.raise_for_status()
            async for payload in sse_payloads(response):
                data = parse_payload(payload)
                if data is None:
                    finished = True
                    break
                text, finish = decode_reply(provider, data)
                if text:
                    yield text
                finished = finished or finish in ("STOP", "stop")
                if finished:
                    break
        if not finished:
            raise ProviderReplyError("provider stream ended without completion")
