from urllib.parse import urlparse


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


def score_source(url: str, domain: str | None, title: str = "") -> float:
    score = 1.0
    parsed_domain = urlparse(url).netloc.lower()
    if domain and domain.lower().replace("www.", "") in parsed_domain.replace("www.", ""):
        score += 2.0
    t = title.lower()
    if "pricing" in t or "press" in t or "news" in t or "docs" in t:
        score += 1.0
    if any(x in parsed_domain for x in ["crunchbase", "techcrunch", "forbes", "reuters", "bloomberg"]):
        score += 1.2
    return score


def rank_and_dedupe_sources(
    canonical_domain: str | None,
    discovered: list[dict[str, str]],
    crawled: list[dict[str, str | None]],
) -> list[dict[str, str | float]]:
    title_by_url = {d["url"]: d.get("title", "") for d in discovered}

    ranked = []
    seen_domains: set[str] = set()
    for page in crawled:
        url = str(page.get("url", ""))
        domain = str(page.get("domain", ""))
        if not url or not domain:
            continue
        domain_key = domain.replace("www.", "")
        if domain_key in seen_domains and canonical_domain and canonical_domain not in domain:
            continue
        seen_domains.add(domain_key)
        ranked.append(
            {
                "url": url,
                "title": str(page.get("title") or title_by_url.get(url) or url),
                "source_type": "official" if canonical_domain and canonical_domain in domain else "external",
                "score": score_source(url, canonical_domain, title_by_url.get(url, "")),
                "text": str(page.get("text") or ""),
            }
        )

    ranked.sort(key=lambda x: float(x["score"]), reverse=True)
    return ranked[:12]
