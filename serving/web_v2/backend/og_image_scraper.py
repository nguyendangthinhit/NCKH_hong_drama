"""Scrape og:image from event links for thumbnail display.

Usage:
    from og_image_scraper import fetch_og_image
    url = fetch_og_image("https://example.com/article")  # str | None
"""

import asyncio
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

TIMEOUT = 8.0


def _extract_image_url(html: str, base_url: str) -> str | None:
    """Parse HTML for og:image, twitter:image, or link[rel=image_src]."""
    soup = BeautifulSoup(html, "html.parser")

    selectors = [
        ("meta", {"property": "og:image"}),
        ("meta", {"name": "og:image"}),
        ("meta", {"name": "twitter:image"}),
        ("meta", {"property": "twitter:image"}),
        ("link", {"rel": "image_src"}),
    ]

    for tag_name, attrs in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if not tag:
            continue
        value = tag.get("content") or tag.get("href")
        if value and value.strip():
            url = value.strip()
            if url.startswith("//"):
                url = "https:" + url
            elif not url.startswith("http"):
                url = urljoin(base_url, url)
            return url

    return None


async def _fetch_one(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a single URL and extract og:image."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        return _extract_image_url(resp.text, str(resp.url))
    except Exception:
        return None


async def fetch_og_images_batch(urls: list[str], concurrency: int = 10) -> list[str | None]:
    """Fetch og:image for a batch of URLs concurrently.

    Returns list of same length as input; None for failed/missing.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def limited(url):
        async with semaphore:
            return await _fetch_one(client, url)

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [limited(u) for u in urls]
        return await asyncio.gather(*tasks)


def fetch_og_image(url: str) -> str | None:
    """Synchronous wrapper — fetch og:image from a single URL."""
    results = asyncio.run(fetch_og_images_batch([url]))
    return results[0]
