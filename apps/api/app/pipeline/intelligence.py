from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


BLOSTEM_ADVANTAGES = {
    "onboarding_speed": "faster onboarding",
    "pricing_friction": "transparent pricing",
    "support_quality": "better support",
    "customization": "flexibility",
    "complexity": "simpler implementation",
    "ecosystem_lock_in": "less lock-in",
    "enterprise_fit": "SMB fit",
}


SIGNAL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "complexity": {
        "label": "complexity",
        "negative": ["complex", "complicated", "steep learning", "hard to use", "difficult", "developer-heavy", "technical"],
        "positive": ["advanced", "robust", "comprehensive", "powerful", "enterprise-grade"],
    },
    "pricing_friction": {
        "label": "pricing friction",
        "negative": ["expensive", "costly", "hidden fee", "additional fee", "pricing complexity", "interchange", "volume discount", "custom pricing"],
        "positive": ["pricing", "fee", "cost", "subscription", "usage-based", "plan"],
    },
    "onboarding_speed": {
        "label": "onboarding speed",
        "negative": ["slow onboarding", "lengthy implementation", "setup time", "integration effort", "go live", "implementation"],
        "positive": ["quick start", "fast onboarding", "easy setup", "self-serve", "instant"],
    },
    "support_quality": {
        "label": "support quality",
        "negative": ["slow support", "poor support", "support gap", "ticket", "unresponsive", "customer service complaint"],
        "positive": ["support", "customer service", "help center", "success manager"],
    },
    "customization": {
        "label": "customization",
        "negative": ["rigid", "limited customization", "not customizable", "inflexible", "custom work", "configuration"],
        "positive": ["customizable", "flexible", "configuration", "custom"],
    },
    "ecosystem_lock_in": {
        "label": "ecosystem lock-in",
        "negative": ["locked into", "ecosystem", "migration", "switching cost", "proprietary", "platform dependency"],
        "positive": ["ecosystem", "marketplace", "suite", "platform"],
    },
    "reliability": {
        "label": "reliability",
        "negative": ["outage", "downtime", "reliability issue", "incident", "failed payment", "risk"],
        "positive": ["reliable", "uptime", "secure", "fraud protection", "risk management"],
    },
    "enterprise_fit": {
        "label": "enterprise fit",
        "negative": ["enterprise", "large business", "global scale", "deep customization", "complex requirements"],
        "positive": ["enterprise", "global", "scale", "large business", "multinational"],
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _source_lookup(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(source.get("url", "")): source for source in sources if source.get("url")}


def _signal_angle(category: str, text: str, source_type: str) -> str | None:
    definition = SIGNAL_DEFINITIONS[category]
    has_negative = _has_any(text, definition["negative"])
    has_positive = _has_any(text, definition["positive"])

    if category == "enterprise_fit" and has_positive:
        return "loss_risk"
    if has_negative:
        return "weakness"
    if has_positive:
        return "strength"
    return None


def extract_competitive_signals(
    snippets: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Classify and score reusable competitive signals from grounded snippets."""
    source_by_url = _source_lookup(sources)
    grouped: dict[str, dict[str, Any]] = {}

    for snippet in snippets:
        text = _normalize(str(snippet.get("text", "")))
        if not text:
            continue
        source_url = str(snippet.get("source_url") or (snippet.get("citations") or [""])[0])
        source = source_by_url.get(source_url, {})
        source_type = str(source.get("source_type", "external"))

        for category in SIGNAL_DEFINITIONS:
            angle = _signal_angle(category, text, source_type)
            if angle is None:
                continue

            key = f"{category}:{angle}"
            bucket = grouped.setdefault(
                key,
                {
                    "category": category,
                    "label": SIGNAL_DEFINITIONS[category]["label"],
                    "angle": angle,
                    "evidence": [],
                    "citations": [],
                    "source_types": set(),
                    "raw_score": 0.0,
                },
            )
            if source_url and source_url not in bucket["citations"]:
                bucket["citations"].append(source_url)
            bucket["source_types"].add(source_type)
            bucket["evidence"].append(
                {
                    "text": snippet.get("text", ""),
                    "source_url": source_url,
                    "source_title": snippet.get("source_title") or source.get("title", ""),
                }
            )
            bucket["raw_score"] += float(source.get("score", 1.0) or 1.0)

    signals: list[dict[str, Any]] = []
    for bucket in grouped.values():
        citations = bucket["citations"]
        support_count = len(citations)
        source_quality = min(bucket["raw_score"] / max(support_count, 1), 5.0)
        agreement = min(1.0, support_count / 3)
        category = bucket["category"]
        blostem_relevance = 1.0 if category in BLOSTEM_ADVANTAGES else 0.55
        if bucket["angle"] == "weakness":
            blostem_relevance += 0.35
        score = round((support_count * 1.4) + source_quality + (agreement * 1.2) + blostem_relevance, 2)
        signals.append(
            {
                "category": category,
                "label": bucket["label"],
                "angle": bucket["angle"],
                "score": score,
                "support_count": support_count,
                "source_quality": round(source_quality, 2),
                "agreement": round(agreement, 2),
                "blostem_advantage": BLOSTEM_ADVANTAGES.get(category, "focused execution"),
                "citations": citations,
                "evidence": bucket["evidence"][:3],
            }
        )

    signals.sort(key=lambda item: (float(item["score"]), int(item["support_count"])), reverse=True)
    return signals[:limit]


def confidence_from_signals(signals: list[dict[str, Any]], source_count: int) -> dict[str, Any]:
    if not signals or source_count == 0:
        score = 0.0
    else:
        avg_agreement = sum(float(signal.get("agreement", 0)) for signal in signals[:5]) / min(len(signals), 5)
        avg_quality = sum(float(signal.get("source_quality", 0)) for signal in signals[:5]) / min(len(signals), 5)
        score = min(0.95, (source_count / 12 * 0.35) + (avg_agreement * 0.35) + (avg_quality / 5 * 0.3))

    if score >= 0.68:
        label = "High confidence"
    elif score >= 0.38:
        label = "Medium confidence"
    else:
        label = "Low confidence"

    return {"confidence_score": round(score, 2), "confidence_label": label}


def signals_by_angle(signals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        grouped[str(signal.get("angle", "unknown"))].append(signal)
    return dict(grouped)
