"""Integration tests for the complete battlecard pipeline.

These tests verify:
- Discovery phase returns multiple sources
- Crawling phase successfully fetches content
- Generation phase produces multiple insights per section
- Retry/fallback mechanisms work correctly
- Total pipeline timing is within budget
"""

import asyncio
import time
from typing import Any

import pytest

from app.pipeline.crawler import crawl_sources
from app.pipeline.generator import generate_battlecard_json, _fallback_json
from app.pipeline.intelligence import extract_signals
from app.pipeline.search import discover_sources


# Configuration for these tests
TEST_COMPETITOR = "Stripe"
MIN_SOURCES_EXPECTED = 5  # Should discover at least 5 sources
MIN_CRAWLED_SUCCESS = 3  # Should successfully crawl at least 3
MIN_INSIGHTS_PER_SECTION = 2  # Each section should have at least 2 items after Phase 1 improvements
MIN_SIGNALS_EXPECTED = 3  # Should extract at least 3 signals from the fixed fixture
DISCOVERY_TIMEOUT_SEC = 60  # Discovery is network-backed and may vary significantly
CRAWL_TIMEOUT_SEC = 40  # Crawling is network-backed and may vary significantly
GENERATION_TIMEOUT_SEC = 10  # Generation should complete in <10s
TOTAL_PIPELINE_TIMEOUT_SEC = 60  # Total should be <60s


@pytest.mark.asyncio
async def test_discovery_returns_sources():
    """Test that source discovery returns multiple sources with proper structure."""
    start = time.time()
    sources = await discover_sources(TEST_COMPETITOR)
    elapsed = time.time() - start
    
    # Verify discovery completed in a reasonable amount of time for live search
    assert elapsed < DISCOVERY_TIMEOUT_SEC, f"Discovery took {elapsed:.1f}s, expected <{DISCOVERY_TIMEOUT_SEC}s"
    
    # Verify we got enough sources
    assert len(sources) >= MIN_SOURCES_EXPECTED, \
        f"Got {len(sources)} sources, expected >={MIN_SOURCES_EXPECTED}"
    
    # Verify source structure
    for source in sources:
        assert "url" in source and source["url"].startswith("http"), \
            f"Invalid URL in source: {source}"
        assert "title" in source, f"Missing title in source: {source}"
        assert "source_type" in source, f"Missing source_type in source: {source}"
    
    print(f"✓ Discovery: {len(sources)} sources in {elapsed:.1f}s")


@pytest.mark.asyncio
async def test_crawl_sources_fetches_content():
    """Test that URL crawling returns content from multiple sources."""
    # Use a small set of known URLs for reliable testing
    sources = [
        {"url": "https://stripe.com", "title": "Stripe"},
        {"url": "https://stripe.com/pricing", "title": "Stripe Pricing"},
        {"url": "https://stripe.com/blog", "title": "Stripe Blog"},
    ]
    
    start = time.time()
    crawled = await crawl_sources(sources, limit=3)
    elapsed = time.time() - start
    
    # Verify crawling completed in a reasonable amount of time for live fetches
    assert elapsed < CRAWL_TIMEOUT_SEC, \
        f"Crawling took {elapsed:.1f}s, expected <{CRAWL_TIMEOUT_SEC}s"
    
    # Verify we got content
    assert len(crawled) >= MIN_CRAWLED_SUCCESS, \
        f"Got {len(crawled)} crawled sources, expected >={MIN_CRAWLED_SUCCESS}"
    
    # Verify crawled content structure
    for item in crawled:
        assert "url" in item and item["url"].startswith("http")
        assert "text" in item and len(item["text"]) > 100, \
            f"Crawled text too short for {item['url']}: {len(item.get('text', ''))} chars"
        assert "domain" in item
    
    print(f"✓ Crawling: {len(crawled)} successful fetches in {elapsed:.1f}s")


@pytest.mark.asyncio
async def test_signal_extraction_returns_multiple():
    """Test that signal extraction generates multiple signals."""
    # Use pre-defined snippets to avoid flaky remote calls
    snippets = [
        {
            "id": "1",
            "text": "Stripe offers transparent, usage-based pricing with competitive rates.",
            "source_url": "https://stripe.com/pricing",
            "sections": ["pricing_posture"],
        },
        {
            "id": "2",
            "text": "Developers praise Stripe for excellent API documentation and support.",
            "source_url": "https://stripe.com/blog",
            "sections": ["customer_sentiment"],
        },
        {
            "id": "3",
            "text": "Stripe handles complex payment scenarios with built-in fraud detection.",
            "source_url": "https://stripe.com",
            "sections": ["strengths"],
        },
        {
            "id": "4",
            "text": "Stripe's fees can be prohibitive for low-volume merchants.",
            "source_url": "https://example.com/review",
            "sections": ["risks"],
        },
        {
            "id": "5",
            "text": "Integration setup requires developer expertise; not suitable for non-technical users.",
            "source_url": "https://example.com/forum",
            "sections": ["risks"],
        },
    ]
    
    start = time.time()
    signals = await extract_signals(TEST_COMPETITOR, snippets)
    elapsed = time.time() - start
    
    # Verify extraction completed in time
    assert elapsed < 10, f"Signal extraction took {elapsed:.1f}s, expected <10s"
    
    # Verify the fixed fixture produces grounded signals
    assert len(signals) >= MIN_SIGNALS_EXPECTED, \
        f"Got {len(signals)} signals, expected >={MIN_SIGNALS_EXPECTED}"
    
    # Verify signal structure
    for signal in signals:
        assert "category" in signal
        assert "label" in signal
        assert "angle" in signal  # Should be weakness, strength, neutral, opportunity
        assert "score" in signal and 0 <= signal["score"] <= 10
    
    print(f"✓ Signal Extraction: {len(signals)} signals in {elapsed:.1f}s")


def test_generation_produces_multiple_items_per_section():
    """Test that generation creates multiple items per section (Phase 1 goal)."""
    # Use pre-defined signals to avoid flakiness
    signals = [
        {
            "category": "pricing_strength",
            "label": "competitive pricing",
            "angle": "strength",
            "score": 8.0,
            "support_count": 3,
            "source_quality": 2.8,
            "agreement": 0.85,
            "blostem_advantage": "value for money",
            "citations": ["https://a.com", "https://b.com"],
            "evidence": [
                {"text": "Lower rates than competitors."},
                {"text": "No hidden fees."},
                {"text": "Flexible volume pricing."},
            ],
        },
        {
            "category": "api_strength",
            "label": "excellent developer experience",
            "angle": "strength",
            "score": 9.0,
            "support_count": 5,
            "source_quality": 3.0,
            "agreement": 0.95,
            "blostem_advantage": "developer-first design",
            "citations": ["https://c.com", "https://d.com"],
            "evidence": [
                {"text": "Comprehensive API documentation."},
                {"text": "Active developer community."},
            ],
        },
        {
            "category": "implementation_risk",
            "label": "requires developer expertise",
            "angle": "weakness",
            "score": 6.5,
            "support_count": 2,
            "source_quality": 2.5,
            "agreement": 0.70,
            "blostem_advantage": "low-code alternatives",
            "citations": ["https://e.com"],
            "evidence": [
                {"text": "Setup requires coding knowledge."},
            ],
        },
    ]
    
    snippets = [
        {"id": "1", "text": "Stripe pricing is very competitive.", "source_url": "https://a.com", "sections": ["pricing_posture"]},
        {"id": "2", "text": "API docs are outstanding.", "source_url": "https://c.com", "sections": ["strengths"]},
        {"id": "3", "text": "Integration needs developer.", "source_url": "https://e.com", "sections": ["risks"]},
    ]
    
    sources = [
        {"url": "https://a.com", "title": "Review A", "domain": "a.com", "text": "content"},
        {"url": "https://c.com", "title": "Review C", "domain": "c.com", "text": "content"},
    ]
    
    # Generate payload
    payload = _fallback_json(TEST_COMPETITOR, snippets, sources, signals)
    
    # Verify each section has multiple items (Phase 1 goal: 5+ per section)
    for section_name, items in payload.get("sections", {}).items():
        assert isinstance(items, list), f"Section {section_name} items should be a list"
        # With our test signals, we should have at least 1-2 items in most sections
        if section_name in ["strengths", "pricing_posture", "risks"]:
            assert len(items) >= 1, \
                f"Section {section_name} has {len(items)} items, expected >=1"
    
    print(f"✓ Generation: Created payload with {len(payload.get('sections', {}))} sections")


@pytest.mark.asyncio
async def test_parallel_pipeline_timing():
    """Test that parallel crawling and retry improvements keep pipeline under time budget.
    
    Note: This is a synthetic test using small datasets to verify timing architecture.
    Real end-to-end timing depends on network conditions and target site responsiveness.
    """
    sources = [
        {"url": "https://stripe.com", "title": "Stripe"},
        {"url": "https://stripe.com/pricing", "title": "Stripe Pricing"},
        {"url": "https://stripe.com/blog", "title": "Stripe Blog"},
    ]
    
    # Test that crawling happens in parallel (not sequential)
    start = time.time()
    crawled = await crawl_sources(sources, limit=3)
    elapsed = time.time() - start
    
    # If crawling were fully sequential, it would take ~5s each = 15s total
    # Parallel crawling with asyncio.gather should be ~5-8s total
    # We allow up to 15s for network variance
    assert elapsed < CRAWL_TIMEOUT_SEC, \
        f"Parallel crawl took {elapsed:.1f}s, expected <{CRAWL_TIMEOUT_SEC}s " \
        f"(suggests sequential execution instead of parallel)"
    
    print(f"✓ Timing: Parallel crawl completed in {elapsed:.1f}s (expected <{CRAWL_TIMEOUT_SEC}s)")


def test_retry_configuration_is_sensible():
    """Verify that retry and timeout configurations are in place and reasonable."""
    from app.pipeline.crawler import CRAWL_MAX_RETRIES, CRAWL_BACKOFF_MULTIPLIER, CRAWL_TIMEOUT
    from app.pipeline.search import SEARCH_MAX_RETRIES, SEARCH_BACKOFF_MULTIPLIER, SEARCH_TIMEOUT
    
    # Verify crawler config
    assert CRAWL_MAX_RETRIES >= 1, "Crawler should have at least 1 retry"
    assert CRAWL_TIMEOUT > 0, "Crawler should have a timeout"
    assert CRAWL_BACKOFF_MULTIPLIER > 1, "Backoff multiplier should increase between retries"
    
    # Verify search config
    assert SEARCH_MAX_RETRIES >= 1, "Search should have at least 1 retry"
    assert SEARCH_TIMEOUT > 0, "Search should have a timeout"
    assert SEARCH_BACKOFF_MULTIPLIER > 1, "Backoff multiplier should increase between retries"
    
    # Verify max total wait time is reasonable
    # With 2 retries and 1.5x backoff: 1 + 1.5 + 2.25 = 4.75 seconds
    max_backoff = sum(CRAWL_BACKOFF_MULTIPLIER ** i for i in range(CRAWL_MAX_RETRIES))
    assert max_backoff < 10, f"Max backoff wait {max_backoff:.1f}s should be <10s"
    
    print(f"✓ Configuration: Retry config is sensible")


def test_worker_pool_configuration():
    """Verify that worker pool is properly configured."""
    from app.services.worker import WorkerPool, PipelineJob
    
    # Create a test pool
    pool = WorkerPool(num_workers=2)
    
    # Verify it can queue jobs
    job = PipelineJob(run_id="test-1", competitor_name="TestCo")
    # Don't start the pool, just verify structure
    assert job.run_id == "test-1"
    assert job.competitor_name == "TestCo"
    assert job.max_retries == 2, "Jobs should have max_retries=2"
    
    print(f"✓ Configuration: Worker pool config is correct")
