"""Resolve an event's primary platform from metadata or its first valid source."""

from urllib.parse import urlsplit

ALIASES = {"fb": "facebook", "web": "news", "website": "news"}
SOCIAL_DOMAINS = {
    "facebook.com": "facebook", "fb.watch": "facebook",
    "youtube.com": "youtube", "youtu.be": "youtube",
    "tiktok.com": "tiktok", "threads.net": "threads", "threads.com": "threads",
    "instagram.com": "instagram",
}


def normalize_platform(value) -> str:
    value = value.strip().lower() if isinstance(value, str) else ""
    return ALIASES.get(value, value)


def preferred_platform(*values):
    for value in values:
        normalized = normalize_platform(value)
        if normalized and normalized != "unknown":
            return normalized
    return None


def resolve_platform(links=None, source_url=None, platform=None) -> str:
    explicit = normalize_platform(platform)
    if explicit and explicit != "unknown":
        return explicit
    sources = [links] if isinstance(links, str) else list(links or [])
    sources.append(source_url)
    for source in sources:
        if not isinstance(source, str):
            continue
        try:
            parsed = urlsplit(source.strip())
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError:
            continue
        # A legacy reference uses "hhttps"; its host still identifies the source.
        # This classification does not modify the stored reference URL.
        if parsed.scheme.lower() not in {"http", "https", "hhttps"} or not host:
            continue
        for domain, name in SOCIAL_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                return name
        return "news"
    return "unknown"
