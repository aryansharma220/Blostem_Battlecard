import asyncio
import time
import json
import os
from pathlib import Path
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
from app.pipeline.observability import PipelineMetrics, format_pipeline_report, set_current_metrics, clear_current_metrics
from app.pipeline.ranker import rank_and_dedupe_sources, resolve_canonical_domain, score_source
from app.pipeline.search import discover_sources
from app.services.cache import competitor_cache_key
from app.services.pdf_export import generate_pdf
from app.utils.logging import get_logger


logger = get_logger(__name__)


def _search_result_sources(competitor_name: str, canonical_domain: str | None, discovered: list[dict[str, str]]) -> list[dict[str, Any]]:
    sources = []
    ranked_discovery = sorted(
        discovered,
        key=lambda item: score_source(
            str(item.get("url", "")),
            canonical_domain,
            str(item.get("title", "")),
            source_type=str(item.get("source_type", "external")),
        ),
        reverse=True,
    )
    for item in ranked_discovery[:10]:
        url = item.get("url", "")
        title = item.get("title", url)
        if not url:
            continue
        source_type = str(item.get("source_type") or ("official" if canonical_domain and canonical_domain in url else "external"))
        sources.append(
            {
                "id": f"D{len(sources)+1}",
                "url": url,
                "title": title,
                "source_type": source_type,
                "score": score_source(url, canonical_domain, title),
                "text": f"{title}. {item.get('snippet', '')}",
                "published_at": item.get('published_at'),
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
                "source_id": source.get("id"),
                "source_url": source["url"],
                "source_title": source["title"],
                "citations": [
                    {
                        "source_id": source.get("id"),
                        "url": source.get("url"),
                        "published_at": source.get("published_at"),
                        "score": float(source.get("score", 0.0)),
                    }
                ],
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


def _merge_item_lists(primary: list[dict[str, Any]] | None, fallback: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_items(items: list[dict[str, Any]] | None) -> None:
        for item in items or []:
            claim = str(item.get("claim") or item.get("objection") or "").strip().lower()
            if not claim:
                claim = json.dumps(item, sort_keys=True, default=str)
            if claim in seen:
                continue
            seen.add(claim)
            merged.append(item)

    add_items(primary)
    add_items(fallback)
    return merged


def _merge_payloads(fallback_payload: dict[str, Any], final_payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback_payload)
    merged.update(final_payload)
    # Merge sections with strict live-first ordering: include all live
    # items in original order, then append final-generated items that
    # are not duplicates by normalized claim text. This prevents the
    # final generation's placeholders or condensed claims from replacing
    # richer live draft content in the UI.
    live_sections: dict[str, list[dict[str, Any]]] = dict(fallback_payload.get("sections") or {})
    final_sections: dict[str, list[dict[str, Any]]] = dict(final_payload.get("sections") or {})
    merged_sections: dict[str, list[dict[str, Any]]] = {}
    for section_name in set(live_sections) | set(final_sections):
        merged_list: list[dict[str, Any]] = []
        seen: set[str] = set()

        # helper to get normalized key for dedupe
        def _norm(item: dict[str, Any]) -> str:
            claim = str(item.get("claim") or item.get("objection") or "").strip().lower()
            if not claim:
                return json.dumps(item, sort_keys=True, default=str)
            return claim

        # add live items first (preserve order)
        for item in (live_sections.get(section_name) or []):
            key = _norm(item)
            if key in seen:
                continue
            seen.add(key)
            merged_list.append(item)

        # then add final items that aren't duplicates
        for item in (final_sections.get(section_name) or []):
            key = _norm(item)
            if key in seen:
                continue
            seen.add(key)
            merged_list.append(item)

        if merged_list:
            merged_sections[section_name] = merged_list

    if merged_sections:
        merged["sections"] = merged_sections

    # For simple lists such as talk tracks and objection handling, prefer
    # live (fallback) items first, then final-generated items.
    for key in ("how_to_beat", "talk_track", "objection_handling"):
        merged[key] = _merge_item_lists(fallback_payload.get(key), final_payload.get(key))

    if fallback_payload.get("deal_guidance") or final_payload.get("deal_guidance"):
        fallback_guidance = fallback_payload.get("deal_guidance") or {}
        final_guidance = final_payload.get("deal_guidance") or {}
        merged["deal_guidance"] = {
            "when_we_win": _merge_item_lists(fallback_guidance.get("when_we_win"), final_guidance.get("when_we_win")),
            "when_we_lose": _merge_item_lists(fallback_guidance.get("when_we_lose"), final_guidance.get("when_we_lose")),
        }

    if fallback_payload.get("customer_reviews") or final_payload.get("customer_reviews"):
        merged["customer_reviews"] = _merge_item_lists(fallback_payload.get("customer_reviews"), final_payload.get("customer_reviews"))

    if fallback_payload.get("customer_sentiment") or final_payload.get("customer_sentiment"):
        merged["customer_sentiment"] = _merge_item_lists(fallback_payload.get("customer_sentiment"), final_payload.get("customer_sentiment"))

    if fallback_payload.get("sources") and not merged.get("sources"):
        merged["sources"] = fallback_payload["sources"]
    if fallback_payload.get("signals") and not merged.get("signals"):
        merged["signals"] = fallback_payload["signals"]

    return merged


class PipelineService:
    async def run(self, run_id: str, competitor_name: str, force_refresh: bool = False, mode: str = "live") -> None:
        started = time.monotonic()
        key = competitor_cache_key(competitor_name)
        
        # Initialize metrics tracking
        metrics = PipelineMetrics(run_id=run_id, competitor_name=competitor_name, start_time=time.time())
        set_current_metrics(metrics)

        try:
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
                metrics.complete(success=True)
                logger.info(format_pipeline_report(metrics))
                return

            # Stage 1: Discovery
            stage = metrics.stage_start("discovery")
            update_run(run_id, status="resolving_domain")
            add_event(run_id, "resolving_domain", "Finding official domain and high-signal sources.", 10)

            discovered = await discover_sources(competitor_name)
            if not discovered:
                raise RuntimeError("No sources found")
            
            metrics.sources_discovered = len(discovered)
            metrics.stage_complete("discovery")

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

            # Stage 2: Crawling
            stage = metrics.stage_start("crawling")
            update_run(run_id, status="crawling")
            # Live mode: crawl fewer pages for speed; Deep mode: comprehensive crawl
            if mode == "live":
                live_limit = min(len(discovered), 3)  # 3 pages for live (fast)
                full_limit = 0  # Skip full crawl in live mode; content freezes anyway
            else:
                live_limit = min(len(discovered), 4)  # 4 for discovery
                full_limit = min(len(discovered), 12)  # 12 for deep research
            
            live_sources = discovered[:live_limit]
            remaining_sources = discovered[live_limit:full_limit] if full_limit > 0 else []
            
            add_event(run_id, "crawling", f"Crawling {live_limit} priority pages for Live Call Mode.", 25)
            if remaining_sources and mode == "deep":
                add_event(run_id, "crawling", f"Crawling {len(remaining_sources)} more pages for Deep Research (in parallel).", 26)
            
            # Parallelize crawling of live and remaining sources
            if remaining_sources:
                live_crawled, remaining_crawled = await asyncio.gather(
                    crawl_sources(live_sources, limit=live_limit),
                    crawl_sources(remaining_sources, limit=len(remaining_sources))
                )
                crawled = live_crawled + remaining_crawled
            else:
                live_crawled = await crawl_sources(live_sources, limit=live_limit)
                crawled = live_crawled
            
            metrics.sources_crawled = len(crawled)
            metrics.stage_complete("crawling")

            # Stage 3: Extraction
            stage = metrics.stage_start("extraction")
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

            add_event(run_id, "extracting", "Extracting and ranking full research evidence.", 68)
            ranked = rank_and_dedupe_sources(canonical_domain, discovered, crawled)
            snippets = extract_snippets(ranked)
            # Deduplicate and cluster similar snippets before generation
            # Live mode: limit snippets aggressively for speed
            snippet_limit = 20 if mode == "live" else settings.dedupe_limit
            snippets = dedupe_snippets(snippets, similarity_threshold=settings.dedupe_similarity_threshold, limit=snippet_limit)
            add_event(run_id, "extracting", "Scoring competitive signals.", 70)
            signals = extract_competitive_signals(snippets, ranked, limit=10 if mode == "live" else 20)

            # Apply Live vs Deep filtering to signals before generation
            def _filter_signals_by_mode(all_signals: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
                if mode == "deep":
                    # Deep: include medium+ sharpness and at least 1 supporting source
                    return [s for s in all_signals if float(s.get("sharpness_score", 0)) >= 0.5 and int(s.get("support_count", 0)) >= 1]
                # Live mode: strict - sharp, supported
                return [s for s in all_signals if float(s.get("sharpness_score", 0)) >= 0.8 and int(s.get("support_count", 0)) >= 2]

            gen_signals = _filter_signals_by_mode(signals, mode)
            
            metrics.snippets_extracted = len(snippets)
            metrics.signals_generated = len(signals)
            metrics.stage_complete("extraction")

            # Stage 4: Generation
            stage = metrics.stage_start("generation")
            update_run(run_id, status="generating")
            add_event(run_id, "generating", "Generating full battlecard with citation-grounded claims.", 76)
            # Enforce minimum source count for confidence
            source_count = len(ranked)
            low_data = source_count < settings.min_sources
            if low_data:
                add_event(run_id, "generating", f"⚠ Low data: only {source_count} sources (recommended {settings.min_sources} for high confidence).", 74)

            # For final generation, pass mode-filtered signals to keep Live outputs sharp and concise
            payload = generate_battlecard_json(
                competitor_name,
                snippets,
                ranked,
                gen_signals,
            )
            # Surface low-data warning so UI can prompt user to try Deep Research or refresh
            if low_data:
                payload["low_data_warning"] = True
                payload["low_data_message"] = f"Limited data: only {source_count} source(s) found. Try Deep Research for more comprehensive analysis."

            # For Live mode: keep live draft as-is (freeze content, no merge).
            # For Deep mode: merge live draft with final comprehensive payload for richer content.
            if mode == "live":
                payload = live_payload
                add_event(run_id, "generating", "Live Mode: content frozen at live draft (no merge with full generation).", 77)
            else:
                # Debugging: write pre-merge and post-merge payload snapshots to help
                # diagnose where content is lost between the live draft and final output.
                try:
                    debug_dir = Path.cwd() / "tmp" / "pipeline_debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    pre = {
                        "run_id": run_id,
                        "live_sections_keys": list((live_payload.get("sections") or {}).keys()),
                        "final_sections_keys": list((payload.get("sections") or {}).keys()),
                        "live_sections_count": sum(len(v) for v in (live_payload.get("sections") or {}).values()) if live_payload.get("sections") else 0,
                        "final_sections_count": sum(len(v) for v in (payload.get("sections") or {}).values()) if payload.get("sections") else 0,
                        "gen_signals_count": len(gen_signals),
                    }
                    (debug_dir / f"{run_id}_pre_merge.json").write_text(json.dumps(pre, indent=2))
                    (debug_dir / f"{run_id}_live_payload.json").write_text(json.dumps(live_payload or {}, indent=2))
                    (debug_dir / f"{run_id}_final_payload.json").write_text(json.dumps(payload or {}, indent=2))
                    logger.info("WROTE pipeline debug pre-merge files for run_id=%s to %s", run_id, str(debug_dir))
                except Exception as _err:
                    logger.warning("Failed to write pipeline debug pre-merge files: %s", _err)

                payload = _merge_payloads(live_payload, payload)

                # After merge: record resulting sizes to help compare
                try:
                    post = {
                        "run_id": run_id,
                        "merged_sections_keys": list((payload.get("sections") or {}).keys()),
                        "merged_sections_count": sum(len(v) for v in (payload.get("sections") or {}).values()) if payload.get("sections") else 0,
                    }
                    (debug_dir / f"{run_id}_post_merge.json").write_text(json.dumps(post, indent=2))
                    (debug_dir / f"{run_id}_merged_payload.json").write_text(json.dumps(payload or {}, indent=2))
                    logger.info("WROTE pipeline debug post-merge files for run_id=%s to %s", run_id, str(debug_dir))
                except Exception as _err:
                    logger.warning("Failed to write pipeline debug post-merge files: %s", _err)

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
            metrics.stage_complete("generation")

            # Stage 5: Rendering
            stage = metrics.stage_start("rendering")
            update_run(run_id, status="rendering")
            add_event(run_id, "rendering", "Rendering markdown output.", 88)
            payload.setdefault("summary", {})
            payload["summary"]["generated_in_seconds"] = round(time.monotonic() - started, 1)
            markdown = render_markdown(payload)
            metrics.stage_complete("rendering")

            # Stage 6: Exporting (PDF)
            stage = metrics.stage_start("exporting")
            update_run(run_id, status="exporting")
            pdf_path = None
            if mode == "deep":
                # Generate PDF only for Deep mode (Live mode content is frozen, PDF can be generated on-demand)
                add_event(run_id, "exporting", "Exporting PDF.", 94)
                pdf_path = await asyncio.to_thread(generate_pdf, markdown, run_id, competitor_name)
            else:
                add_event(run_id, "exporting", "Skipping PDF export in Live mode (can be generated on-demand later).", 94)
            metrics.stage_complete("exporting")

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
                    sources=[
                        {
                            "id": s.get("id") or s.get("url"),
                            "url": s["url"],
                            "title": s["title"],
                            "source_type": s.get("source_type", "external"),
                            "score": float(s.get("score", 0.0)),
                            "published_at": s.get("published_at"),
                        }
                        for s in ranked
                    ],
                snippets=snippets,
            )
            
            # Complete metrics with success
            metrics.complete(success=True)
            logger.info(format_pipeline_report(metrics))
        except Exception as exc:
            logger.exception("pipeline failed run_id=%s", run_id)
            metrics.complete(success=False, error_message=str(exc))
            logger.info(format_pipeline_report(metrics))
            add_event(run_id, "failed", str(exc), 100)
            update_run(run_id, status="failed", error_message=str(exc))
        finally:
            clear_current_metrics()


pipeline_service = PipelineService()
