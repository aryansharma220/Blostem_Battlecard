from app.pipeline.generator import _fallback_json, post_process_payload


def test_postprocess_truncates_and_limits():
    fb = _fallback_json("TestCo", [
        {"id":"1","text":"Expand to new markets quickly and globally.","source_url":"https://a.com","sections":["positioning"]},
        {"id":"2","text":"Usage-based pricing with volume discounts for enterprise customers.","source_url":"https://b.com","sections":["pricing_posture"]},
        {"id":"3","text":"Customers praise developer experience and APIs.","source_url":"https://c.com","sections":["customer_sentiment"]},
    ], [{"url":"https://a.com","title":"A"},{"url":"https://b.com","title":"B"}])

    pp = post_process_payload(fb, max_bullets=1, max_words_per_bullet=4)

    # each section should have at most 1 bullet
    for sec, items in pp["sections"].items():
        assert len(items) <= 1
        for it in items:
            assert len(it.get("claim", "").split()) <= 5  # allow truncation ellipsis

    # sales talk track should be present and not empty
    st = pp["sections"].get("sales_talk_track_objection_handling", [])
    assert st and st[0].get("claim")


def test_postprocess_adds_sales_ready_payload_fields():
    signals = [
        {
            "category": "pricing_friction",
            "label": "pricing friction",
            "angle": "weakness",
            "score": 8.0,
            "support_count": 2,
            "source_quality": 2.5,
            "agreement": 0.67,
            "blostem_advantage": "transparent pricing",
            "citations": ["https://a.com", "https://b.com"],
            "evidence": [{"text": "Customers mention pricing complexity and additional fees."}],
        }
    ]
    payload = _fallback_json(
        "Stripe",
        [{"id": "1", "text": "Customers mention pricing complexity and additional fees.", "source_url": "https://a.com", "sections": ["pricing_posture"]}],
        [{"url": "https://a.com", "title": "A"}, {"url": "https://b.com", "title": "B"}],
        signals,
    )

    pp = post_process_payload(payload)

    assert pp["summary"]["confidence_label"] in {"Low confidence", "Medium confidence", "High confidence"}
    assert pp["summary"]["source_count"] == 2
    assert pp["deal_guidance"]["when_we_win"]
    assert pp["deal_guidance"]["when_we_lose"]
    assert pp["how_to_beat"]
    assert pp["talk_track"]
    assert pp["objection_handling"]
    assert pp["summary"]["confidence_explanation"]
    assert pp["talk_track"][0]["claim"].startswith('"')
    assert len(pp["how_to_beat"][0]["claim"].split()) <= 19
