from app.pipeline.intelligence import confidence_from_signals, extract_competitive_signals


def test_multiple_sources_increase_signal_confidence():
    snippets = [
        {"text": "Customers report pricing complexity and additional fees during implementation.", "source_url": "https://a.com", "sections": ["pricing_posture"]},
        {"text": "Reviews mention pricing complexity and hidden fees for smaller merchants.", "source_url": "https://b.com", "sections": ["pricing_posture"]},
        {"text": "Analysts note pricing complexity can make forecasting costs difficult.", "source_url": "https://c.com", "sections": ["pricing_posture"]},
    ]
    sources = [
        {"url": "https://a.com", "title": "A", "source_type": "external", "score": 2.0},
        {"url": "https://b.com", "title": "B", "source_type": "external", "score": 2.0},
        {"url": "https://c.com", "title": "C", "source_type": "external", "score": 2.0},
    ]

    signals = extract_competitive_signals(snippets, sources)
    pricing = next(signal for signal in signals if signal["category"] == "pricing_friction")

    assert pricing["angle"] == "weakness"
    assert pricing["support_count"] == 3
    assert pricing["agreement"] == 1.0
    assert confidence_from_signals(signals, 3)["confidence_label"] in {"Medium confidence", "High confidence"}


def test_official_feature_claim_does_not_become_weakness_without_friction_language():
    snippets = [
        {"text": "Stripe offers a powerful payments platform with advanced fraud protection.", "source_url": "https://stripe.com", "sections": ["strengths"]},
    ]
    sources = [{"url": "https://stripe.com", "title": "Stripe", "source_type": "official", "score": 3.0}]

    signals = extract_competitive_signals(snippets, sources)

    assert signals
    assert all(signal["angle"] != "weakness" for signal in signals)


def test_expected_signal_categories_are_detected():
    snippets = [
        {"text": "The platform has pricing complexity and custom pricing for larger customers.", "source_url": "https://a.com", "sections": ["pricing_posture"]},
        {"text": "Customers describe lengthy implementation and slow onboarding for new teams.", "source_url": "https://b.com", "sections": ["weaknesses_risks"]},
        {"text": "Some reviews mention slow support and ticket delays.", "source_url": "https://c.com", "sections": ["customer_sentiment"]},
        {"text": "Buyers with limited customization needs may find the platform rigid.", "source_url": "https://d.com", "sections": ["weaknesses_risks"]},
    ]
    sources = [{"url": f"https://{name}.com", "title": name, "source_type": "external", "score": 2.0} for name in ["a", "b", "c", "d"]]

    signals = extract_competitive_signals(snippets, sources)
    categories = {signal["category"] for signal in signals}

    assert {"pricing_friction", "onboarding_speed", "support_quality", "customization"}.issubset(categories)
