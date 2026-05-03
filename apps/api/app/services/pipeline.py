import asyncio
import time
from typing import Any

from app.db.database import add_event, get_cache, set_cache, update_run
from app.config import settings
from app.pipeline.crawler import crawl_sources
from app.pipeline.generator import (
    extract_snippets,
    dedupe_snippets,
    generate_battlecard_json,
    generate_live_call_payload,
    render_markdown,
)
from app.pipeline.intelligence import extract_competitive_signals
from app.pipeline.ranker import rank_and_dedupe_sources, resolve_canonical_domain, score_source
from app.pipeline.search import discover_sources
from app.services.cache import competitor_cache_key
from app.services.pdf_export import generate_pdf
from app.utils.logging import get_logger


logger = get_logger(__name__)


def _search_result_sources(competitor_name: str, canonical_domain: str | None, discovered: list[dict[str, str]]) -> list[dict[str, Any]]:
    sources = []
    for item in discovered[:10]:
        url = item.get("url", "")
        title = item.get("title", url)
        if not url:
            continue
        source_type = "official" if canonical_domain and canonical_domain in url else "external"
        sources.append(
            {
                "url": url,
                "title": title,
                "source_type": source_type,
                "score": score_source(url, canonical_domain, title),
                "text": f"{title}. {item.get('snippet', '')}",
            }
        )
    return sources


def _search_result_snippets(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snippets = []
    for idx, source in enumerate(sources, start=1):
        text = str(source.get("text", "")).strip()
        if len(text) < 40:
            continue
        snippets.append(
            {
                "id": f"SR{idx}",
                "text": text[:300],
                "source_url": source["url"],
                "source_title": source["title"],
                "sections": [
                    "competitor_overview",
                    "pricing_posture",
                    "weaknesses_risks",
                    "customer_sentiment",
                    "sales_talk_track_objection_handling",
                ],
            }
        )
    return snippets


class PipelineService:
    async def run(self, run_id: str, competitor_name: str, force_refresh: bool = False) -> None:
        started = time.monotonic()
        key = competitor_cache_key(competitor_name)

        cached = None if force_refresh else get_cache(key)
        if cached:
            add_event(run_id, "cache", "Cache hit. Returning previous run data.", 100)
            update_run(
                run_id,
                status="completed",
                canonical_domain=cached.get("canonical_domain"),
                markdown=cached.get("markdown"),
                json_output=__import__("json").dumps(cached.get("json_output", {})),
                pdf_path=cached.get("pdf_path"),
                sources_json=__import__("json").dumps(cached.get("sources_json", [])),
                snippets_json=__import__("json").dumps(cached.get("snippets_json", [])),
            )
            return

        try:
            update_run(run_id, status="resolving_domain")
            add_event(run_id, "resolving_domain", "Finding official domain and high-signal sources.", 10)

            discovered = await discover_sources(competitor_name)
            if not discovered:
                raise RuntimeError("No sources found")

            canonical_domain = resolve_canonical_domain(competitor_name, discovered)
            update_run(run_id, canonical_domain=canonical_domain)

            discovery_sources = _search_result_sources(competitor_name, canonical_domain, discovered)
            discovery_snippets = _search_result_snippets(discovery_sources)
            discovery_signals = extract_competitive_signals(discovery_snippets, discovery_sources)
            if discovery_sources:
                discovery_payload = generate_live_call_payload(competitor_name, discovery_snippets, discovery_sources, discovery_signals)
                discovery_payload.setdefault("summary", {})
                discovery_payload["summary"]["generated_in_seconds"] = round(time.monotonic() - started, 1)
                update_run(
                    run_id,
                    json_output=__import__("json").dumps(discovery_payload),
                    sources_json=__import__("json").dumps(discovery_sources),
                    snippets_json=__import__("json").dumps(discovery_snippets),
                )
                add_event(run_id, "resolving_domain", "Live Call draft is ready from search signals.", 18)

            update_run(run_id, status="crawling")
            live_limit = min(len(discovered), 4)
            full_limit = live_limit
            add_event(run_id, "crawling", f"Crawling {live_limit} priority pages for Live Call Mode.", 25)
            live_crawled = await crawl_sources(discovered, limit=live_limit)
            if not live_crawled:
                raise RuntimeError("Unable to crawl sources")

            update_run(run_id, status="extracting")
            add_event(run_id, "extracting", "Extracting priority signals for Live Call Mode.", 42)
            live_ranked = rank_and_dedupe_sources(canonical_domain, discovered, live_crawled)
            live_snippets = extract_snippets(live_ranked)
            live_snippets = dedupe_snippets(live_snippets, similarity_threshold=settings.dedupe_similarity_threshold, limit=min(settings.dedupe_limit, 30))
            live_signals = extract_competitive_signals(live_snippets, live_ranked)
            live_payload = generate_live_call_payload(competitor_name, live_snippets, live_ranked, live_signals)
            live_payload.setdefault("summary", {})
            live_payload["summary"]["generated_in_seconds"] = round(time.monotonic() - started, 1)
            update_run(
                run_id,
                json_output=__import__("json").dumps(live_payload),
                sources_json=__import__("json").dumps(live_ranked),
                snippets_json=__import__("json").dumps(live_snippets),
            )
            add_event(run_id, "extracting", "Live Call Mode is ready; continuing deep research.", 55)

            remaining = discovered[live_limit:full_limit]
            add_event(run_id, "crawling", f"Crawling {len(remaining)} more pages for Deep Research.", 62)
            remaining_crawled = await crawl_sources(remaining, limit=len(remaining)) if remaining else []
            crawled = live_crawled + remaining_crawled

            add_event(run_id, "extracting", "Extracting and ranking full research evidence.", 68)
            ranked = rank_and_dedupe_sources(canonical_domain, discovered, crawled)
            snippets = extract_snippets(ranked)
            # Deduplicate and cluster similar snippets before generation
            snippets = dedupe_snippets(snippets, similarity_threshold=settings.dedupe_similarity_threshold, limit=settings.dedupe_limit)
            add_event(run_id, "extracting", "Scoring competitive signals.", 70)
            signals = extract_competitive_signals(snippets, ranked)

            update_run(run_id, status="generating")
            add_event(run_id, "generating", "Generating full battlecard with citation-grounded claims.", 76)
            payload = generate_battlecard_json(
                competitor_name,
                snippets,
                ranked,
                signals,
            )

            # Guarantee claim-level fallback safety.
            sections = payload.get("sections", {})
            for section_name, items in sections.items():
                safe_items = items or []
                if not safe_items:
                    sections[section_name] = [{"claim": "Not enough public data found.", "citations": []}]
                    continue
                for item in safe_items:
                    if not item.get("claim"):
                        item["claim"] = "Not enough public data found."
                    if "citations" not in item:
                        item["citations"] = []

            payload["sections"] = sections

            update_run(run_id, status="rendering")
            add_event(run_id, "rendering", "Rendering markdown output.", 88)
            payload.setdefault("summary", {})
            payload["summary"]["generated_in_seconds"] = round(time.monotonic() - started, 1)
            markdown = render_markdown(payload)

            update_run(run_id, status="exporting")
            add_event(run_id, "exporting", "Exporting PDF.", 94)
            pdf_path = await asyncio.to_thread(generate_pdf, markdown, run_id, competitor_name)

            elapsed = time.monotonic() - started
            add_event(run_id, "completed", f"Completed in {elapsed:.1f}s", 100)
            update_run(
                run_id,
                status="completed",
                markdown=markdown,
                json_output=__import__("json").dumps(payload),
                pdf_path=pdf_path,
                sources_json=__import__("json").dumps(ranked),
                snippets_json=__import__("json").dumps(snippets),
            )

            set_cache(
                competitor_key=key,
                run_id=run_id,
                canonical_domain=canonical_domain,
                markdown=markdown,
                json_output=payload,
                pdf_path=pdf_path,
                sources=[{"url": s["url"], "title": s["title"], "source_type": s.get("source_type", "external"), "score": float(s.get("score", 0.0))} for s in ranked],
                snippets=snippets,
            )
        except Exception as exc:
            logger.exception("pipeline failed run_id=%s", run_id)
            add_event(run_id, "failed", str(exc), 100)
            update_run(run_id, status="failed", error_message=str(exc))


pipeline_service = PipelineService()
