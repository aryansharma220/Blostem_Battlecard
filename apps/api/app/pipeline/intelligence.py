from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from datetime import datetime, timezone
import email.utils


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
    limit: int = 20,
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
                    "citation_dicts": [],
                    "source_types": set(),
                    "raw_score": 0.0,
                },
            )
            if source_url and source_url not in bucket["citations"]:
                bucket["citations"].append(source_url)
                # Add structured citation (source_id, url, published_at, score)
                bucket["citation_dicts"].append(
                    {
                        "source_id": source.get("id"),
                        "url": source_url,
                        "published_at": source.get("published_at"),
                        "score": float(source.get("score", 0.0)),
                    }
                )
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
                "citations": bucket.get("citation_dicts", []) or citations,
                "evidence": bucket["evidence"][:3],
            }
        )

    signals.sort(key=lambda item: (float(item["score"]), int(item["support_count"])), reverse=True)
    # Compute sharpness score for each signal and detect contradictions
    for s in signals:
        s["sharpness_score"] = _compute_sharpness_score(s)
        s["has_contradiction"] = False
        s["contradiction_details"] = None

    _detect_contradictions(signals, sources)

    return signals[:limit]


async def extract_signals(
    competitor_name: str,
    snippets: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Compatibility wrapper for older callers that still await extract_signals()."""
    _ = competitor_name
    return extract_competitive_signals(snippets, sources or [], limit=limit)


def _compute_sharpness_score(signal: dict[str, Any]) -> float:
    """Heuristic sharpness: rewards numeric/metric evidence and penalizes generic phrases."""
    evidence = signal.get("evidence", [])
    text_blob = " ".join(str(e.get("text", "") or "") for e in evidence).lower()
    if not text_blob:
        return 0.0

    score = 0.0
    # presence of numbers or timeframes
    if re.search(r"\b\d+\b", text_blob):
        score += 0.4
    if re.search(r"\b(days|weeks|months|years|%|per|k|m)\b", text_blob):
        score += 0.25
    # presence of named products/metrics
    if re.search(r"(onboard|go live|implementation|setup|fee|pricing|charge|transaction|downtime|outage)", text_blob):
        score += 0.2

    # penalize generic words
    generic_terms = ["scalable", "flexible", "robust", "seamless", "enterprise-grade", "powerful"]
    generic_hits = sum(1 for t in generic_terms if t in text_blob)
    score -= 0.15 * min(generic_hits, 3)

    # clamp
    return round(max(0.0, min(1.0, score)), 2)


def _detect_contradictions(signals: list[dict[str, Any]], sources: list[dict[str, Any]]) -> None:
    """Mark contradictions when opposing angles exist for important categories.

    Rules (per founder): show contradiction ONLY if >=2 sources disagree AND both have medium+ signal strength
    and category is important (pricing, support, reliability, onboarding).
    """
    important = {"pricing_friction", "support_quality", "reliability", "onboarding_speed"}
    # map by category -> angles
    by_cat: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for s in signals:
        cat = s.get("category")
        angle = s.get("angle")
        if cat not in by_cat:
            by_cat[cat] = {}
        by_cat[cat].setdefault(angle, []).append(s)

    def signal_strength(sig: dict[str, Any]) -> float:
        # derive a medium+ threshold: support_count>=2 and agreement>=0.33 or source_quality>=2.5
        sc = float(sig.get("support_count", 0))
        agr = float(sig.get("agreement", 0))
        qual = float(sig.get("source_quality", 0))
        return 1.0 if (sc >= 2 and (agr >= 0.33 or qual >= 2.5)) else 0.0

    for cat, angles in by_cat.items():
        if cat not in important:
            continue
        # look for opposing angles (strength vs weakness) or presence of loss_risk vs strength
        if "weakness" in angles and "strength" in angles:
            # check if at least one signal in each group meets medium+ criteria
            weak_signals = angles["weakness"]
            strong_signals = angles["strength"]
            weak_ok = [s for s in weak_signals if signal_strength(s)]
            strong_ok = [s for s in strong_signals if signal_strength(s)]
            if weak_ok and strong_ok:
                # mark all involved signals with contradiction info
                for w in weak_ok:
                    w["has_contradiction"] = True
                    w["contradiction_details"] = _format_contradiction_detail(w, strong_ok, sources)
                for st in strong_ok:
                    st["has_contradiction"] = True
                    st["contradiction_details"] = _format_contradiction_detail(st, weak_ok, sources)


def _format_contradiction_detail(signal: dict[str, Any], opposing: list[dict[str, Any]], sources: list[dict[str, Any]]) -> str:
    parts = []
    parts.append(f"Conflicting signals for '{signal.get('label')}'.")
    for o in opposing:
        parts.append(f"Other view: {o.get('angle')} supported by {o.get('support_count', 0)} sources.")
    parts.append("Investigate in deep view.")
    return " ".join(parts)


def _parse_date_to_datetime(s: str) -> datetime | None:
    if not s:
        return None
    s = str(s).strip()
    try:
        # Try ISO format first
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def confidence_from_signals(signals: list[dict[str, Any]], source_count: int, sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not signals or source_count == 0:
        score = 0.0
        avg_agreement = 0.0
        avg_quality = 0.0
        avg_recency_days = None
        source_type_diversity = 0.0
        label = "No data"
    else:
        avg_agreement = sum(float(signal.get("agreement", 0)) for signal in signals[:5]) / min(len(signals), 5)
        avg_quality = sum(float(signal.get("source_quality", 0)) for signal in signals[:5]) / min(len(signals), 5)
        unique_source_types = {
            str(source.get("source_type", "external"))
            for source in (sources or [])
            if str(source.get("url", ""))
        }
        source_type_diversity = min(len(unique_source_types), 3) / 3 if unique_source_types else 0.0
        
        # Compute average recency (days) for cited sources in top signals
        recencies: list[int] = []
        source_map = {str(s.get("url")): s for s in (sources or [])}
        for sig in signals[:5]:
            for cit in sig.get("citations", [])[:3]:
                # Handle both string URLs and dict citations
                cit_url = cit if isinstance(cit, str) else cit.get("url") if isinstance(cit, dict) else None
                src = source_map.get(str(cit_url)) if cit_url else None
                if not src:
                    continue
                pub = src.get("published_at") or src.get("publish_date") or src.get("published")
                dt = _parse_date_to_datetime(pub) if pub else None
                if dt:
                    days = (datetime.now(timezone.utc) - dt).days
                    if days >= 0:
                        recencies.append(days)
        
        avg_recency_days = round(sum(recencies) / len(recencies)) if recencies else None
        
        # Score includes recency weight: fresher sources boost confidence
        recency_factor = 0.0
        if avg_recency_days is not None:
            # 0 days = 1.0, 30 days = 0.75, 90+ days = 0.3
            recency_factor = max(0.3, 1.0 - (avg_recency_days / 120))
        
        score = min(0.95, 
               (min(source_count, 6) / 6 * 0.35) +  # source count, saturates faster for small datasets
               (avg_agreement * 0.35) +             # signal agreement
               (avg_quality / 5 * 0.2) +            # source quality
             (source_type_diversity * 0.08) +      # source-type mix / evidence breadth
               (recency_factor * 0.1))              # recency boost
        
        if score >= 0.70:
            label = "High confidence"
        elif score >= 0.45:
            label = "Medium confidence"
        else:
            label = "Low confidence"

    explanation_parts = []
    if source_count > 0:
        explanation_parts.append(f"Based on {source_count} sources")
    if avg_agreement > 0:
        explanation_parts.append(f"{round(avg_agreement * 100)}% signal agreement")
    if avg_quality > 0:
        explanation_parts.append(f"{round(avg_quality, 1)}/5 avg source quality")
    if avg_recency_days is not None:
        explanation_parts.append(f"avg source age {avg_recency_days} days")
    if source_type_diversity > 0:
        explanation_parts.append(f"source-type mix {round(source_type_diversity * 100)}%")
    
    explanation = ", ".join(explanation_parts) + "." if explanation_parts else "Insufficient data."

    factors = {
        "source_count": source_count,
    }
    if avg_agreement > 0:
        factors["agreement"] = round(avg_agreement, 2)
    if avg_quality > 0:
        factors["source_quality"] = round(avg_quality, 2)
    if avg_recency_days is not None:
        factors["avg_recency_days"] = int(avg_recency_days)
    if source_type_diversity > 0:
        factors["source_type_diversity"] = round(source_type_diversity, 2)

    return {
        "confidence_score": round(score, 2),
        "confidence_label": label,
        "confidence_explanation": explanation,
        "confidence_factors": factors,
    }


def signals_by_angle(signals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        grouped[str(signal.get("angle", "unknown"))].append(signal)
    return dict(grouped)
