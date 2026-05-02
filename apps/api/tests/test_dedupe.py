from app.pipeline.generator import dedupe_snippets


def test_dedupe_merges_similar_snippets():
    snippets = [
        {"id": "SN1", "text": "Stripe offers global payment processing with robust fraud protection.", "source_url": "https://stripe.com/pricing", "sections": ["positioning"]},
        {"id": "SN2", "text": "Stripe offers global payment processing with robust fraud protection", "source_url": "https://stripe.com/payments", "sections": ["positioning"]},
        {"id": "SN3", "text": "Stripe pricing is usage-based with volume discounts for enterprise customers.", "source_url": "https://stripe.com/pricing", "sections": ["pricing_posture"]},
        {"id": "SN4", "text": "Stripe pricing is usage-based, with volume discounts for enterprise customers.", "source_url": "https://merchantmaverick.com", "sections": ["pricing_posture"]},
        {"id": "SN5", "text": "Customers report good developer experience and reliable uptime.", "source_url": "https://nerdwallet.com", "sections": ["customer_sentiment"]},
    ]

    unique = dedupe_snippets(snippets, similarity_threshold=0.8)

    # Expect duplicates merged -> 3 unique items
    assert len(unique) == 3

    texts = [u["text"] for u in unique]
    assert any("robust fraud protection" in t for t in texts)
    assert any("volume discounts" in t for t in texts)
    assert any("developer experience" in t for t in texts)

    # citations merged for the duplicate groups
    for u in unique:
        if "fraud protection" in u["text"]:
            assert set(u.get("citations", [])) == {"https://stripe.com/pricing", "https://stripe.com/payments"}


def test_dedupe_respects_limit():
    many = [{"id": f"SN{i}", "text": f"Claim {i}", "source_url": f"https://s{i}.com", "sections": ["positioning"]} for i in range(200)]
    out = dedupe_snippets(many, limit=50)
    assert len(out) == 50
