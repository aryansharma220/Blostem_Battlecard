import asyncio
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.utils.logging import get_logger


logger = get_logger(__name__)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SOURCE_QUERY_GROUPS: list[tuple[str, list[str]]] = [
    (
        "news",
        [
            "{name} news",
            "{name} press release",
            "{name} announcement funding",
        ],
    ),
    (
        "reviews",
        [
            "{name} reviews",
            "{name} complaints",
            "{name} trustpilot g2 capterra reddit",
        ],
    ),
    (
        "filings",
        [
            "site:sec.gov {name}",
            "{name} annual report investor relations",
            '"{name}" 10-k filing',
        ],
    ),
    (
        "community",
        [
            "{name} reddit discussion",
            "{name} forum discussion",
            "{name} user feedback",
        ],
    ),
    (
        "comparison",
        [
            "{name} alternative compare",
            "{name} vs competitors",
            "{name} pricing compare",
        ],
    ),
    (
        "official",
        [
            "{name} official site",
            "{name} pricing docs",
            "{name} product docs",
        ],
    ),
]


def _unwrap_ddg_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [url])[0]
        return unquote(uddg)
    return url


async def search_duckduckgo(query: str, max_results: int = 8, source_type: str = "external") -> list[dict[str, str]]:
    endpoint = "https://duckduckgo.com/html/"
    params = {"q": query}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            response = await client.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
    except Exception as exc:
        logger.warning("search failed for query=%s: %s", query, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    for node in soup.select(".result"):
        a = node.select_one("a.result__a")
        if not a:
            continue
        href = (a.get("href") or "").strip()
        if not href:
            continue
        clean_url = _unwrap_ddg_url(href)
        title = a.get_text(" ", strip=True)
        snippet_node = node.select_one(".result__snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        results.append({"url": clean_url, "title": title, "snippet": snippet, "source_type": source_type})
        if len(results) >= max_results:
            break

    return results


async def discover_sources(competitor_name: str) -> list[dict[str, str]]:
    queries: list[tuple[str, str]] = []
    for source_type, templates in SOURCE_QUERY_GROUPS:
        for template in templates:
            queries.append((source_type, template.format(name=competitor_name)))

    batches = await asyncio.gather(*[search_duckduckgo(query, max_results=6, source_type=source_type) for source_type, query in queries])

    dedup: dict[str, dict[str, str]] = {}
    for batch in batches:
        for item in batch:
            url = item["url"]
            if url.startswith("http") and url not in dedup:
                dedup[url] = item
    return list(dedup.values())[:30]
