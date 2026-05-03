import asyncio
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.utils.logging import get_logger


logger = get_logger(__name__)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    chunks = []
    for node in soup.select("h1, h2, h3, p, li"):
        text = WHITESPACE_RE.sub(" ", node.get_text(" ", strip=True)).strip()
        if len(text) > 40:
            chunks.append(text)

    return "\n".join(chunks)


async def fetch_url(url: str) -> dict[str, str | None]:
    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        text = clean_text(response.text)
        title = ""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            title = (soup.title.get_text(strip=True) if soup.title else "")[:200]
        except Exception:
            pass
        return {
            "url": url,
            "domain": urlparse(str(response.url)).netloc,
            "title": title,
            "text": text[:12000],
        }
    except Exception as exc:
        logger.warning("crawl failed url=%s error=%s", url, exc)
        return {"url": url, "domain": urlparse(url).netloc, "title": "", "text": ""}


async def crawl_sources(sources: list[dict[str, str]], limit: int = 6) -> list[dict[str, str | None]]:
    selected = sources[:limit]
    tasks = [fetch_url(s["url"]) for s in selected]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r.get("text")]
