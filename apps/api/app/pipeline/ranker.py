from urllib.parse import urlparse


SOURCE_TYPE_BONUS = {
    "official": 0.85,
    "news": 1.35,
    "reviews": 1.5,
    "filings": 1.3,
    "community": 1.05,
    "comparison": 1.15,
    "external": 0.9,
}


def resolve_canonical_domain(competitor_name: str, sources: list[dict[str, str]]) -> str | None:
    name_key = competitor_name.lower().replace(" ", "")
    for item in sources:
        domain = urlparse(item.get("url", "")).netloc.lower()
        if not domain:
            continue
        compact = domain.replace("www.", "").replace("-", "").replace(".", "")
        if name_key[:8] in compact:
            return domain
    return urlparse(sources[0]["url"]).netloc if sources else None


def score_source(url: str, domain: str | None, title: str = "", source_type: str = "external") -> float:
    score = 1.0
    parsed_domain = urlparse(url).netloc.lower()
    if domain and domain.lower().replace("www.", "") in parsed_domain.replace("www.", ""):
        score += 0.85
    t = title.lower()
    if "pricing" in t or "press" in t or "news" in t or "docs" in t or "review" in t or "filing" in t:
        score += 0.75
    if any(x in parsed_domain for x in ["crunchbase", "techcrunch", "forbes", "reuters", "bloomberg", "sec.gov", "g2.com", "trustpilot.com", "capterra.com", "reddit.com"]):
        score += 1.25
    score += SOURCE_TYPE_BONUS.get(source_type, SOURCE_TYPE_BONUS["external"])
    return score


def rank_and_dedupe_sources(
    canonical_domain: str | None,
    discovered: list[dict[str, str]],
    crawled: list[dict[str, str | None]],
) -> list[dict[str, str | float]]:
    title_by_url = {d["url"]: d.get("title", "") for d in discovered}
    type_by_url = {d["url"]: d.get("source_type", "external") for d in discovered}

    ranked = []
    seen_domains: dict[str, int] = {}
    for idx, page in enumerate(crawled, start=1):
        url = str(page.get("url", ""))
        domain = str(page.get("domain", ""))
        if not url or not domain:
            continue
        domain_key = domain.replace("www.", "")
        source_type = str(type_by_url.get(url) or page.get("source_type") or "external")
        domain_limit = 2 if source_type == "official" or (canonical_domain and canonical_domain in domain) else 1
        if seen_domains.get(domain_key, 0) >= domain_limit:
            continue
        seen_domains[domain_key] = seen_domains.get(domain_key, 0) + 1
        ranked.append(
            {
                "id": f"S{idx}",
                "url": url,
                "title": str(page.get("title") or title_by_url.get(url) or url),
                "source_type": "official" if canonical_domain and canonical_domain in domain else source_type,
                "score": score_source(url, canonical_domain, title_by_url.get(url, ""), source_type=source_type),
                "text": str(page.get("text") or ""),
                "published_at": page.get("published_at"),
            }
        )

    ranked.sort(key=lambda x: float(x["score"]), reverse=True)
    return ranked[:16]
