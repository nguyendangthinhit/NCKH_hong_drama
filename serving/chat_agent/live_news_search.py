"""Tool tra tin mới trên web qua Firecrawl: tìm tin báo (/v2/search, nguồn news, Việt Nam), rồi scrape
song song vài bài đầu để lấy nội dung. Dùng khi kho sự kiện local không có / cần cập nhật mới nhất.
Port của serving/chat_agent_worker/src/live-news-search.ts (giữ cùng hành vi).
"""
import asyncio
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from urllib.parse import urlparse

import httpx

log = logging.getLogger("chat_agent.live_news")

API = "https://api.firecrawl.dev/v2"
SEARCH_TIMEOUT_S = 10
SCRAPE_TIMEOUT_S = 12
SEARCH_LIMIT = 5
ARTICLE_CHARS = 1500
CACHE_TTL_S = 30 * 60  # cùng câu tìm trong 30 phút dùng lại kết quả (tiết kiệm credit)
CACHE_MAX = 200


@dataclass
class NewsItem:
    title: str
    url: str
    source: str  # tên miền báo
    date: str  # thời điểm tương đối do Google News trả (vd "4 days ago")
    content: str = ""  # đoạn nội dung đã làm sạch, rỗng nếu không scrape được


def _host(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def clean_article_markdown(md: str, max_chars: int = ARTICLE_CHARS) -> str:
    """Markdown bài báo -> văn bản thuần: bỏ ảnh/link/menu (dòng ngắn), giữ các đoạn văn đầu."""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)  # ảnh
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)  # link -> chữ
    out, size = [], 0
    for line in md.split("\n"):
        line = re.sub(r"[*_`|]+", "", re.sub(r"^[#>*\-\s|]+", "", line)).strip()
        if len(line) < 60 or line in out:  # dòng menu, nút, chú thích ảnh thường ngắn
            continue
        out.append(line)
        size += len(line)
        if size >= max_chars:
            break
    return "\n".join(out)[:max_chars]


def news_context_text(items: list[NewsItem], today: date | None = None) -> str:
    """Văn bản đưa vào phần DỮ LIỆU của prompt."""
    day = (today or date.today()).isoformat()
    blocks = []
    for i, it in enumerate(items, 1):
        head = f"[{i}] {it.title} | Báo: {it.source} | Thời gian: {it.date or 'không rõ'}"
        blocks.append(f"{head}\nNội dung: {it.content}" if it.content else head)
    body = "\n\n".join(blocks)
    return f"TIN MỚI TỪ WEB (tìm ngày {day}, chưa qua phân tích dư luận của hệ thống):\n{body}"


def sources_text(items: list[NewsItem], max_items: int = 3) -> str:
    """Danh sách link nguồn nối vào cuối câu trả lời."""
    if not items:
        return ""
    return "\n\nNguồn tin:\n" + "\n".join(it.url for it in items[:max_items])


class LiveNewsSearch:
    """Gọi được như hàm: `await tool(query, recent)` -> list[NewsItem]. Lỗi/thiếu khoá -> []."""

    def __init__(self, api_key: str, http: httpx.AsyncClient, scrape_top: int = 2):
        self.api_key = api_key
        self.http = http
        self.scrape_top = max(0, scrape_top)
        self._cache: dict[str, tuple[float, list[NewsItem]]] = {}

    async def _post(self, path: str, body: dict, timeout: float) -> dict:
        resp = await self.http.post(
            f"{API}/{path}", json=body, timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def _scrape(self, url: str) -> str:
        body = {"url": url, "formats": ["markdown"], "onlyMainContent": True,
                "timeout": (SCRAPE_TIMEOUT_S - 2) * 1000}
        try:
            data = await self._post("scrape", body, SCRAPE_TIMEOUT_S)
            return clean_article_markdown((data.get("data") or {}).get("markdown") or "")
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Scrape lỗi %s: %s", _host(url), type(exc).__name__)
            return ""  # vẫn dùng được tiêu đề

    async def __call__(self, query: str, recent: bool) -> list[NewsItem]:
        if not self.api_key:
            return []
        q = query.strip()[:200]
        tbs = "qdr:w" if recent else "qdr:y"
        key = f"{tbs}|{q.lower()}"
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
            return [NewsItem(**asdict(it)) for it in hit[1]]
        try:
            body = {"query": q, "limit": SEARCH_LIMIT, "sources": ["news"], "tbs": tbs, "country": "vn"}
            raw = ((await self._post("search", body, SEARCH_TIMEOUT_S)).get("data") or {}).get("news") or []
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Tìm tin web lỗi: %s", exc)
            return []
        items = [
            NewsItem(r["title"], r["url"], _host(r["url"]), r.get("date") or "")
            for r in raw if isinstance(r.get("url"), str) and isinstance(r.get("title"), str)
        ]
        top = items[: self.scrape_top]
        for it, content in zip(top, await asyncio.gather(*(self._scrape(it.url) for it in top))):
            it.content = content
        if items:
            if len(self._cache) >= CACHE_MAX:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (time.monotonic(), items)
        return items
