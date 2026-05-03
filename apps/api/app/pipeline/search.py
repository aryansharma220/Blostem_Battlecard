import asyncio
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.utils.logging import get_logger


logger = get_logger(__name__)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Search configuration
SEARCH_TIMEOUT = 6.0
SEARCH_MAX_RETRIES = 2
SEARCH_BACKOFF_MULTIPLIER = 1.5

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


async def _search_duckduckgo_attempt(query: str, max_results: int = 8, source_type: str = "external") -> list[dict[str, str]]:
    """Internal DuckDuckGo search implementation (single attempt, no retry)."""
    endpoint = "https://duckduckgo.com/html/"
    params = {"q": query}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
    except Exception as exc:
        logger.warning(f"search_duckduckgo failed for query={query}: {exc}")
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


async def search_duckduckgo(query: str, max_results: int = 8, source_type: str = "external", retry_count: int = 0) -> list[dict[str, str]]:
    """Search DuckDuckGo with exponential backoff retry on transient errors.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        source_type: Label for result type (e.g. 'news', 'reviews')
        retry_count: Current retry attempt (0 for first attempt)
        
    Returns:
        List of search results with url, title, snippet, source_type
    """
    try:
        return await _search_duckduckgo_attempt(query, max_results, source_type)
    except (asyncio.TimeoutError, httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        # Transient error - retry with backoff
        if retry_count < SEARCH_MAX_RETRIES:
            backoff = (SEARCH_BACKOFF_MULTIPLIER ** retry_count)
            logger.warning(f"search_duckduckgo transient error query={query} error={type(exc).__name__}, retrying in {backoff:.1f}s (attempt {retry_count + 1}/{SEARCH_MAX_RETRIES})")
            await asyncio.sleep(backoff)
            return await search_duckduckgo(query, max_results, source_type, retry_count=retry_count + 1)
        else:
            logger.warning(f"search_duckduckgo failed query={query} after {SEARCH_MAX_RETRIES} retries")
            return []
    except Exception as exc:
        logger.warning(f"search_duckduckgo unexpected error query={query}: {exc}")
        return []


async def _search_bing_attempt(query: str, max_results: int = 8, source_type: str = "external") -> list[dict[str, str]]:
    """Internal Bing search implementation as fallback (single attempt, no retry).
    
    Note: Bing search via HTML scraping is fragile. This serves as a graceful fallback
    when DuckDuckGo is unavailable. For production, consider using Bing API.
    """
    endpoint = "https://www.bing.com/search"
    params = {"q": query}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
    except Exception as exc:
        logger.warning(f"search_bing failed for query={query}: {exc}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    
    # Bing uses different HTML structure than DDG
    for item in soup.select("li.b_algo"):
        try:
            a = item.select_one("h2 a")
            if not a:
                continue
            href = a.get("href", "").strip()
            if not href or not href.startswith("http"):
                continue
            title = a.get_text(" ", strip=True)
            
            # Try to find snippet
            snippet_node = item.select_one("p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            
            results.append({"url": href, "title": title, "snippet": snippet, "source_type": source_type})
            if len(results) >= max_results:
                break
        except Exception:
            continue

    return results


async def search_bing(query: str, max_results: int = 8, source_type: str = "external") -> list[dict[str, str]]:
    """Search Bing as fallback when DuckDuckGo fails.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        source_type: Label for result type
        
    Returns:
        List of search results
    """
    try:
        logger.debug(f"Attempting fallback Bing search for query={query}")
        return await _search_bing_attempt(query, max_results, source_type)
    except Exception as exc:
        logger.warning(f"search_bing fallback failed query={query}: {exc}")
        return []


async def discover_sources(competitor_name: str) -> list[dict[str, str]]:
    """Discover sources about a competitor using search queries.
    
    Uses multiple search queries across different categories (news, reviews, filings, etc.)
    with DuckDuckGo as primary and Bing as fallback. Returns deduplicated results.
    
    Args:
        competitor_name: Name of the competitor to search for
        
    Returns:
        List of source dicts with url, title, snippet, source_type (up to 30 results)
    """
    queries: list[tuple[str, str]] = []
    for source_type, templates in SOURCE_QUERY_GROUPS:
        for template in templates:
            queries.append((source_type, template.format(name=competitor_name)))

    # Keep discovery fast by capping the number of live search queries.
    queries = queries[:6]

    # Run the selected DuckDuckGo queries in parallel
    ddg_batches = await asyncio.gather(
        *[search_duckduckgo(query, max_results=6, source_type=source_type) for source_type, query in queries]
    )

    # Collect all results and dedupe
    dedup: dict[str, dict[str, str]] = {}
    for batch in ddg_batches:
        for item in batch:
            url = item["url"]
            if url.startswith("http") and url not in dedup:
                dedup[url] = item
    
    # If DuckDuckGo returned insufficient results, try Bing fallback on a subset of queries
    if len(dedup) < 15:
        logger.info(f"DuckDuckGo returned {len(dedup)} results; trying Bing fallback for {competitor_name}")
        fallback_queries = [q for _, q in queries[:3]]  # Top 3 queries
        bing_batches = await asyncio.gather(
            *[search_bing(query, max_results=4, source_type="external") for query in fallback_queries]
        )
        for batch in bing_batches:
            for item in batch:
                url = item["url"]
                if url.startswith("http") and url not in dedup and len(dedup) < 30:
                    dedup[url] = item
    
    return list(dedup.values())[:30]
