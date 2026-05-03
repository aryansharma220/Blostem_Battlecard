import asyncio
import re
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.utils.logging import get_logger


logger = get_logger(__name__)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
WHITESPACE_RE = re.compile(r"\s+")

# Crawl configuration
CRAWL_TIMEOUT = 5.0
CRAWL_MAX_RETRIES = 2
CRAWL_BACKOFF_MULTIPLIER = 1.5


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


def extract_publish_date(html: str, headers: dict[str, str] | None) -> str | None:
    """Try to extract a publish date from common meta tags or headers.

    Returns the raw date string if found, otherwise None.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Common meta properties
        selectors = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'name': 'pubdate'}),
            ('meta', {'name': 'publication_date'}),
            ('meta', {'name': 'date'}),
            ('meta', {'itemprop': 'datePublished'}),
            ('meta', {'property': 'og:published_time'}),
        ]
        for tag_name, attrs in selectors:
            tag = soup.find(tag_name, attrs=attrs)
            if tag:
                content = tag.get('content') or tag.get('value') or tag.get('datetime')
                if content:
                    return content.strip()

        # time tag with datetime
        time_tag = soup.find('time')
        if time_tag:
            dt = time_tag.get('datetime') or time_tag.get_text()
            if dt:
                return dt.strip()

        # fallback to Last-Modified header
        if headers:
            lm = headers.get('last-modified') or headers.get('Last-Modified')
            if lm:
                return lm.strip()
    except Exception:
        pass
    return None


async def fetch_url(url: str, retry_count: int = 0) -> dict[str, str | None]:
    """Fetch a URL with exponential backoff retry on transient errors.
    
    Args:
        url: The URL to fetch
        retry_count: Current retry attempt (0 for first attempt)
        
    Returns:
        Dict with url, domain, title, and text (text may be empty on failure)
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=CRAWL_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        text = clean_text(response.text)
        title = ""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            title = (soup.title.get_text(strip=True) if soup.title else "")[:200]
        except Exception:
            pass
        published = extract_publish_date(response.text, dict(response.headers))
        return {
            "url": url,
            "domain": urlparse(str(response.url)).netloc,
            "title": title,
            "text": text[:12000],
            "published_at": published,
        }
    except (asyncio.TimeoutError, httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        # Transient error - retry with backoff
        if retry_count < CRAWL_MAX_RETRIES:
            backoff = (CRAWL_BACKOFF_MULTIPLIER ** retry_count)
            logger.warning(f"crawl transient error url={url} error={type(exc).__name__}, retrying in {backoff:.1f}s (attempt {retry_count + 1}/{CRAWL_MAX_RETRIES})")
            await asyncio.sleep(backoff)
            return await fetch_url(url, retry_count=retry_count + 1)
        else:
            logger.warning(f"crawl failed url={url} error={exc} after {CRAWL_MAX_RETRIES} retries")
            return {"url": url, "domain": urlparse(url).netloc, "title": "", "text": ""}
    except httpx.HTTPStatusError as exc:
        # 4xx/5xx error - don't retry for 4xx (client error), retry for 5xx (server error)
        if 500 <= exc.response.status_code < 600 and retry_count < CRAWL_MAX_RETRIES:
            backoff = (CRAWL_BACKOFF_MULTIPLIER ** retry_count)
            logger.warning(f"crawl server error url={url} status={exc.response.status_code}, retrying in {backoff:.1f}s (attempt {retry_count + 1}/{CRAWL_MAX_RETRIES})")
            await asyncio.sleep(backoff)
            return await fetch_url(url, retry_count=retry_count + 1)
        else:
            logger.warning(f"crawl failed url={url} status={exc.response.status_code}")
            return {"url": url, "domain": urlparse(url).netloc, "title": "", "text": ""}
    except Exception as exc:
        logger.warning(f"crawl failed url={url} error={exc}")
        return {"url": url, "domain": urlparse(url).netloc, "title": "", "text": ""}


async def crawl_sources(sources: list[dict[str, str]], limit: int = 6) -> list[dict[str, str | None]]:
    """Crawl multiple sources in parallel.
    
    Args:
        sources: List of source dicts with 'url' key
        limit: Maximum number of sources to crawl
        
    Returns:
        List of successfully crawled sources (with non-empty text)
    """
    selected = sources[:limit]
    tasks = [fetch_url(s["url"]) for s in selected]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r.get("text")]
