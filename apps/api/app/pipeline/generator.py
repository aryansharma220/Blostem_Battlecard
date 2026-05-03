import json
from collections import defaultdict
from typing import Any
import re

from app.config import settings
from app.pipeline.intelligence import confidence_from_signals, signals_by_angle
from app.utils.logging import get_logger


logger = get_logger(__name__)

SECTIONS = [
    "competitor_overview",
    "positioning",
    "pricing_posture",
    "recent_launches_announcements",
    "strengths",
    "weaknesses_risks",
    "customer_sentiment",
    "customer_reviews",
    "sales_talk_track_objection_handling",
]


def extract_snippets(ranked_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keywords = {
        "positioning": ["platform", "solution", "digital", "bank", "payment", "fintech"],
        "pricing_posture": ["pricing", "plan", "subscription", "fee", "cost"],
        "recent_launches_announcements": ["launch", "announced", "new", "release", "partnership"],
        "strengths": ["fast", "secure", "scalable", "growth", "trusted"],
        "weaknesses_risks": ["risk", "challenge", "complaint", "issue", "regulatory"],
        "customer_sentiment": ["review", "rating", "feedback", "customer", "experience"],
        "customer_reviews": ["review", "reviews", "rating", "ratings", "testimonial", "trustpilot", "g2", "capterra", "reddit", "complaint"],
        "competitor_overview": ["company", "founded", "offers", "serves", "market"],
        "sales_talk_track_objection_handling": ["alternative", "why", "switch", "compare"],
    }
    snippets: list[dict[str, Any]] = []
    snippet_id = 1

    for source in ranked_sources:
        lines = [line.strip() for line in source["text"].split("\n") if len(line.strip()) > 60]
        top_lines = lines[:30]
        for line in top_lines:
            lower = line.lower()
            matched_sections = [
                section for section, section_keywords in keywords.items() if any(k in lower for k in section_keywords)
            ]
            if not matched_sections:
                continue
            snippets.append(
                {
                    "id": f"SN{snippet_id}",
                    "text": line[:300],
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
                    "sections": matched_sections,
                }
            )
            snippet_id += 1

    return snippets[:80]


def dedupe_snippets(snippets: list[dict[str, Any]], similarity_threshold: float = 0.82, limit: int = 60) -> list[dict[str, Any]]:
    """Remove semantic and exact duplicates from snippets while preserving sections and citations.

    This uses a simple pairwise similarity check (SequenceMatcher) and merges similar
    snippets by keeping the longer text and unioning their citation lists and sections.
    """
    def normalize(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def token_key(s: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", s.lower()) if len(token) > 3}

    def snippet_citations(sn: dict[str, Any]) -> list[Any]:
        citations = sn.get("citations") or []
        if citations:
            return list(citations)
        source_url = sn.get("source_url")
        return [source_url] if source_url else []

    unique: list[dict[str, Any]] = []
    seen_texts: dict[str, dict[str, Any]] = {}

    for sn in snippets:
        text = (sn.get("text") or "").strip()
        if not text:
            continue
        norm = normalize(text)
        if norm in seen_texts:
            merged = seen_texts[norm]
            existing_cits = merged.get("citations", []) or []
            new_cits = snippet_citations(sn)
            seen_keys = {_citation_key(c) for c in existing_cits}
            for c in new_cits:
                key = _citation_key(c)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                existing_cits.append(c)
            merged["citations"] = existing_cits
            merged["sections"] = list(set((merged.get("sections", []) or []) + (sn.get("sections", []) or [])))
            continue

        merged = None
        norm_tokens = token_key(norm)
        for existing in unique:
            existing_norm = normalize(existing["text"])
            # Avoid over-merging very short claims — require exact match for short texts
            len_min = min(len(existing_norm), len(norm))
            if len_min < 30:
                if existing_norm == norm:
                    merged = existing
                    break
                continue

            existing_tokens = existing.setdefault("_dedupe_tokens", token_key(existing_norm))
            overlap = len(existing_tokens & norm_tokens)
            union = len(existing_tokens | norm_tokens) or 1
            ratio = overlap / union
            if ratio >= similarity_threshold:
                merged = existing
                break

        if merged is None:
            # ensure citations and sections are lists
            sn.setdefault("citations", sn.get("citations") or ([sn.get("source_url")] if sn.get("source_url") else []))
            sn.setdefault("sections", sn.get("sections", []))
            sn_copy = sn.copy()
            sn_copy["_dedupe_tokens"] = norm_tokens
            unique.append(sn_copy)
            seen_texts[norm] = sn_copy
        else:
            # merge into existing: prefer longer text, combine citations and sections
            if len(text) > len(merged["text"]):
                merged["text"] = text
            # combine citations
            # dedupe citations by (source_id or url) while preserving original item shape
            existing_cits = merged.get("citations", []) or []
            new_cits = snippet_citations(sn)
            seen_keys = {_citation_key(c) for c in existing_cits}
            merged_list = list(existing_cits)
            for c in new_cits:
                key = _citation_key(c)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                merged_list.append(c)
            merged["citations"] = merged_list
            # combine sections
            merged_sections = set(merged.get("sections", []) + sn.get("sections", []))
            merged["sections"] = list(merged_sections)

    # preserve original order, limit size
    for item in unique:
        item.pop("_dedupe_tokens", None)
    return unique[:limit]


def _first_signal_text(signal: dict[str, Any]) -> str:
    evidence = signal.get("evidence") or []
    if evidence:
        return str(evidence[0].get("text", "")).strip()
    return str(signal.get("label", "competitive signal")).strip()


def _citations(signal: dict[str, Any]) -> list[str]:
    out: list[dict[str, Any]] = []
    for c in signal.get("citations", []) or []:
        if isinstance(c, dict):
            out.append(
                {
                    "source_id": c.get("source_id") or c.get("id"),
                    "url": c.get("url"),
                    "published_at": c.get("published_at"),
                    "score": c.get("score"),
                }
            )
        else:
            s = str(c)
            if s.startswith("http"):
                out.append({"url": s})
            else:
                out.append({"source_id": s})
    return out


def _citation_key(citation: Any) -> str:
    if isinstance(citation, dict):
        return str(citation.get("source_id") or citation.get("url") or citation.get("id") or "")
    return str(citation)


def _fallback_json(
    competitor_name: str,
    snippets: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    signals = signals or []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sn in snippets:
        for section in sn["sections"]:
            grouped[section].append(sn)

    def build_bullets(section: str) -> list[dict[str, Any]]:
        picks = grouped.get(section, [])[:8]
        if not picks:
            return [{"claim": "Not enough public data found.", "citations": []}]
        out = []
        for p in picks:
            cits = p.get("citations") or ([{"url": p.get("source_url")}])
            out.append({"claim": p.get("text", ""), "citations": cits})
        return out

    sections = {section: build_bullets(section) for section in SECTIONS}
    weak_signals = [s for s in signals if s.get("angle") == "weakness"]
    strength_signals = [s for s in signals if s.get("angle") == "strength"]
    if weak_signals:
        sections["weaknesses_risks"] = [
            {"claim": _weakness_claim(s), "citations": _citations(s)}
            for s in weak_signals[:4]
        ]
    if strength_signals:
        sections["strengths"] = [
            {"claim": _strength_claim(s), "citations": _citations(s)}
            for s in strength_signals[:4]
        ]

    return {
        "competitor_name": competitor_name,
        "sections": sections,
        "sources": [
            {
                "id": s.get("id") or s.get("url"),
                "url": s.get("url"),
                "title": s.get("title"),
                "score": float(s.get("score", 0.0)),
                "published_at": s.get("published_at"),
            }
            for s in sources
        ],
        "signals": signals,
        "grounding": "fallback_without_llm",
    }


def _groq_json(
    competitor_name: str,
    snippets: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    from groq import Groq

    model = settings.groq_model or "llama-3.3-70b-versatile"
    client = Groq(api_key=settings.groq_api_key)

    prompt_payload = {
        "competitor_name": competitor_name,
        "blostem_positioning": {
            "default": "SMB fintech speed",
            "advantages": ["faster onboarding", "transparent pricing", "better support", "flexibility"],
        },
        "sections": SECTIONS,
        "scored_signals": signals[:10],
        "snippets": snippets[:40],
        "sources": [{"url": s["url"], "title": s["title"], "score": s.get("score", 0)} for s in sources[:20]],
        "rules": {
            "require_citations": True,
            "no_hallucinations": True,
            "if_missing_data": "Not enough public data found.",
            "style": "sales-ready for an AE before a call",
            "talk_track": "single conversational quote per item",
            "how_to_beat": "direct, aggressive, under 18 words per bullet",
            "prioritize": ["weaknesses_risks", "deal_guidance", "how_to_beat", "talk_track"],
            "min_items_per_section": 5,
            "max_items_per_section": 8,
        },
        "output_schema": {
            "competitor_name": "string",
            "summary": {
                "key_insight": "string",
                "confidence_label": "string",
                "confidence_score": "number",
                "source_count": "number",
                "generated_in_seconds": "number | null"
            },
            "deal_guidance": {
                "when_we_win": [{"claim": "string", "citations": ["url"]}],
                "when_we_lose": [{"claim": "string", "citations": ["url"]}]
            },
            "how_to_beat": [{"claim": "string", "citations": ["url"]}],
            "talk_track": [{"claim": "string", "citations": ["url"]}],
            "objection_handling": [{"objection": "string", "response": "string", "citations": ["url"]}],
            "sections": {
                "<section_name>": [{"claim": "string", "citations": ["url"]}]
            },
            "sources": [{"url": "string", "title": "string"}],
            "signals": ["scored signal objects"],
            "grounding": "string"
        }
    }

    # Reasoning-first system prompt (decision logic, evidence-linked, no generic claims)
    sys = (
        "You are a decision-first analyst for sales enablement.\n"
        "Rules: Force comparison not description. Force trade-offs not features. Force specificity — ban generic words like 'scalable', 'flexible', 'robust', 'seamless'.\n"
        "For every claim you output, attach explicit evidence: which signals support it (ids) and which sources (urls) and their publish dates.\n"
        "Structure: For the 'Why We Win vs {competitor}' section produce items in the form:\n"
        "  Trigger → Weakness → Our Advantage → Sales Angle\n"
        "Example: 'If speed matters → competitor onboarding takes 3+ weeks → we deploy in 3 days → push quick go-live.'\n"
        "Contradictions: If 2+ medium-or-higher confidence sources disagree on an important topic (pricing, support, reliability, onboarding), output a 'CONTRADICTION' entry showing both sides and their supporting sources.\n"
        "Output: Strict JSON following the provided output_schema. Do NOT invent facts; if evidence is missing, return the explicit string: 'Not enough public data found.'"
    )
    user = json.dumps(prompt_payload)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=2500,
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content or "{}"
    return json.loads(content)


def generate_battlecard_json(
    competitor_name: str,
    snippets: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    signals = signals or []
    try:
        payload = _groq_json(competitor_name, snippets, sources, signals)
        payload["grounding"] = "groq"
        payload["signals"] = signals
        # Ensure sources include ids, score, and published_at so claims can reference them
        payload["sources"] = payload.get("sources") or [
            {
                "id": s.get("id") or s.get("url"),
                "url": s.get("url"),
                "title": s.get("title"),
                "score": float(s.get("score", 0.0)),
                "published_at": s.get("published_at"),
            }
            for s in sources
        ]
        # post-process to enforce structure and compression
        return post_process_payload(payload, max_bullets=settings.post_max_bullets, max_words_per_bullet=settings.post_max_words_per_bullet)
    except Exception as exc:
        logger.warning("groq generation failed, fallback enabled: %s", exc)
        return post_process_payload(_fallback_json(competitor_name, snippets, sources, signals), max_bullets=settings.post_max_bullets, max_words_per_bullet=settings.post_max_words_per_bullet)


def generate_live_call_payload(
    competitor_name: str,
    snippets: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _fallback_json(competitor_name, snippets, sources, signals)
    payload["grounding"] = "live_call_fast_path"
    payload["partial"] = True
    return post_process_payload(payload, max_bullets=5, max_words_per_bullet=500)


def _weakness_claim(signal: dict[str, Any]) -> str:
    label = str(signal.get("label", "execution risk"))
    evidence = _first_signal_text(signal)
    if evidence and evidence != label:
        return f"{label.title()} pain: {evidence}"
    return f"{label.title()} is a pressure point worth attacking."


def _strength_claim(signal: dict[str, Any]) -> str:
    label = str(signal.get("label", "strength"))
    evidence = _first_signal_text(signal)
    if evidence and evidence != label:
        return f"{label.title()} strength: {evidence}"
    return f"{label.title()} is a documented strength."


def _clip_sentence(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip().rstrip(".,;:") + "..."


def _sales_angle(signal: dict[str, Any]) -> str:
    category = str(signal.get("category", "complexity"))
    competitor_issue = str(signal.get("label", "friction"))
    templates = {
        "complexity": "Their complexity slows teams down; attack with simpler rollout and faster go-live.",
        "pricing_friction": "Push hard on pricing predictability; contrast their layered fees with transparent pricing.",
        "onboarding_speed": "Make speed the wedge; position faster go-live as the reason to switch.",
        "support_quality": "Attack support gaps; sell hands-on help when buyers need fast answers.",
        "customization": "Call out rigid workflows; position Blostem as the flexible fit.",
        "ecosystem_lock_in": "Pressure lock-in risk; sell freedom from one ecosystem.",
        "reliability": "Acknowledge scale, then shift to speed and flexibility for the buyer's actual stage.",
        "enterprise_fit": "Do not fight breadth; qualify out deep-enterprise platform deals early.",
    }
    return templates.get(category, f"Turn {competitor_issue} into the reason to choose Blostem now.")


def _talk_track(signal: dict[str, Any], competitor_name: str) -> str:
    category = str(signal.get("category", "complexity"))
    if category == "pricing_friction":
        return f'"If pricing predictability matters, we are cleaner than {competitor_name}\'s layered fee model."'
    if category == "onboarding_speed":
        return f'"{competitor_name} is powerful, but teams often struggle with speed to go live; we are faster."'
    if category == "support_quality":
        return f'"When support quality matters, you get a more hands-on experience with Blostem."'
    if category == "customization":
        return f'"If your workflow needs flexibility, Blostem adapts faster than a rigid platform."'
    if category == "ecosystem_lock_in":
        return f'"Blostem keeps you flexible instead of tying the whole motion to one ecosystem."'
    return f'"Most teams choose Blostem when they want speed and simplicity without unnecessary platform complexity."'


def _ensure_sales_payload(payload: dict[str, Any]) -> None:
    competitor_name = str(payload.get("competitor_name") or "the competitor")
    signals = payload.get("signals") or []
    grouped = signals_by_angle(signals)
    weaknesses = grouped.get("weakness", [])
    strengths = grouped.get("strength", [])
    loss_risks = grouped.get("loss_risk", [])
    source_count = len(payload.get("sources") or [])
    confidence = confidence_from_signals(signals, source_count, payload.get("sources") or [])

    payload["summary"] = {
        **confidence,
        "source_count": source_count,
        "generated_in_seconds": (payload.get("summary") or {}).get("generated_in_seconds"),
        "key_insight": (payload.get("summary") or {}).get("key_insight")
        or _build_key_insight(competitor_name, weaknesses, loss_risks),
    }

    objection_items = payload.get("objection_handling") or [_objection_flip(signal, competitor_name) for signal in (weaknesses + strengths + loss_risks)[:4]]
    payload["objection_handling"] = _normalize_objections(objection_items[:4])

    payload["deal_guidance"] = {
        "when_we_win": _normalize_items(
            payload.get("deal_guidance", {}).get("when_we_win")
            or [{"claim": _win_guidance(signal), "citations": _citations(signal)} for signal in weaknesses[:3]]
            or [{"claim": "SMB fintech teams that value faster onboarding, transparent pricing, support, and flexibility.", "citations": []}],
            3,
            18,
        ),
        "when_we_lose": _normalize_items(
            payload.get("deal_guidance", {}).get("when_we_lose")
            or [{"claim": _lose_guidance(signal, competitor_name), "citations": _citations(signal)} for signal in (loss_risks + strengths)[:3]]
            or [
                {"claim": f"Deeply integrated users with high switching costs around {competitor_name}.", "citations": []},
                {"claim": f"Global enterprises needing broad customization and platform depth from {competitor_name}.", "citations": []},
                {"claim": f"Teams already optimized around {competitor_name}'s tooling.", "citations": []},
            ],
            3,
            18,
        ),
    }

    payload["how_to_beat"] = _normalize_items(
        payload.get("how_to_beat")
        or [{"claim": _sales_angle(signal), "citations": _citations(signal)} for signal in weaknesses[:4]]
        or [{"claim": "Lead with faster onboarding, transparent pricing, better support, and flexibility.", "citations": []}],
        4,
        18,
    )
    payload["talk_track"] = _normalize_items(
        payload.get("talk_track")
        or [{"claim": _talk_track(signal, competitor_name), "citations": _citations(signal)} for signal in weaknesses[:3]]
        or [{"claim": _talk_track({}, competitor_name), "citations": []}],
        3,
        22,
        quote=True,
    )


def _build_key_insight(competitor_name: str, weaknesses: list[dict[str, Any]], loss_risks: list[dict[str, Any]]) -> str:
    """Extract a sharp, data-driven key insight from competitive signals."""
    # Try to extract a specific claim from evidence
    def _extract_insight_from_signals(signals: list[dict[str, Any]]) -> str | None:
        for signal in signals[:2]:
            evidence = signal.get("evidence", [])
            if not evidence:
                continue
            text = str(evidence[0].get("text", "")).strip()
            if text and len(text) > 20:
                label = str(signal.get("label", "")).lower()
                # Format as a specific insight
                return f"{competitor_name}'s {label} is a pressure point: {text[:100]}"
        return None

    # Try weaknesses first
    if weaknesses:
        insight = _extract_insight_from_signals(weaknesses)
        if insight:
            return insight
        labels = ", ".join(str(s.get("label", "friction")) for s in weaknesses[:2])
        return f"{competitor_name} has scale, but teams struggle with {labels}. We win on speed and simplicity."

    # Fall back to loss_risks
    if loss_risks:
        return f"{competitor_name} is strongest in enterprise-depth deals. Qualify hard before competing on breadth."

    # Default insight
    return f"{competitor_name} can be positioned against Blostem on speed, pricing clarity, support, and flexibility."


def _win_guidance(signal: dict[str, Any]) -> str:
    advantage = str(signal.get("blostem_advantage", "speed"))
    label = str(signal.get("label", "competitor friction"))
    return f"Teams prioritizing {advantage} over {label}."


def _lose_guidance(signal: dict[str, Any], competitor_name: str) -> str:
    if signal.get("category") == "enterprise_fit":
        return f"Global enterprises needing deep customization and platform breadth from {competitor_name}."
    if signal.get("category") == "ecosystem_lock_in":
        return f"Deeply integrated users with high switching costs around {competitor_name}."
    if signal.get("angle") == "strength":
        return f"Teams already optimized around {competitor_name}'s {signal.get('label', 'platform')}."
    return f"Buyers who value {competitor_name}'s {signal.get('label', 'incumbent breadth')} more than speed."


def _objection_flip(signal: dict[str, Any], competitor_name: str) -> dict[str, Any]:
    category = str(signal.get("category", "complexity"))
    citations = _citations(signal)
    if category == "reliability":
        return {
            "objection": f"{competitor_name} is more reliable.",
            "response": "True at massive scale; most teams need speed, flexibility, and hands-on execution more.",
            "citations": citations,
        }
    if category == "enterprise_fit":
        return {
            "objection": f"{competitor_name} is the enterprise standard.",
            "response": "That is exactly why it can feel heavy; Blostem wins when the team needs speed over breadth.",
            "citations": citations,
        }
    if category == "pricing_friction":
        return {
            "objection": f"{competitor_name} pricing is proven.",
            "response": "Proven does not mean predictable; use Blostem when pricing clarity matters.",
            "citations": citations,
        }
    if category == "ecosystem_lock_in":
        return {
            "objection": f"We are already in the {competitor_name} ecosystem.",
            "response": "That is the risk: switching gets harder later, so keep the workflow flexible now.",
            "citations": citations,
        }
    return {
        "objection": f"{competitor_name} is the safer choice.",
        "response": "Safe can become slow; Blostem is the better fit when speed and support matter now.",
        "citations": citations,
    }


def _normalize_objections(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for item in items:
        objection = str(item.get("objection", "")).strip()
        response = str(item.get("response", "")).strip()
        if not objection or not response:
            continue
        key = objection.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "objection": _clip_sentence(objection, 12),
                "response": _clip_sentence(response, 18),
                "citations": item.get("citations", []) or [],
            }
        )
    return out or [
        {
            "objection": "The competitor feels safer.",
            "response": "Safe can become slow; Blostem wins when speed, support, and flexibility matter.",
            "citations": [],
        }
    ]


def _normalize_items(
    items: list[dict[str, Any]],
    limit: int,
    max_words: int,
    quote: bool = False,
) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for item in items or []:
        claim = str(item.get("claim", "")).strip()
        if not claim:
            continue
        if quote and not claim.startswith('"'):
            claim = f'"{claim.strip(chr(34))}"'
        claim = _clip_sentence(claim, max_words)
        key = claim.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"claim": claim, "citations": item.get("citations", []) or []})
        if len(out) >= limit:
            break
    return out or [{"claim": "Not enough public data found.", "citations": []}]


def post_process_payload(payload: dict[str, Any], max_bullets: int = 5, max_words_per_bullet: int = 20) -> dict[str, Any]:
    """Deterministically enforce section limits, truncate bullets, dedupe claims, and ensure sales talk track exists.

    This runs after LLM generation (or fallback) and ensures output meets UI & demo constraints.
    It does NOT invent facts; sales talk track is synthesized from existing weaknesses/strengths when possible.
    """
    sections = payload.get("sections", {}) or {}

    def truncate_claim(claim: str) -> str:
        words = claim.split()
        if len(words) <= max_words_per_bullet:
            return claim.strip()
        return " ".join(words[:max_words_per_bullet]).rstrip().rstrip(".,;:") + "..."

    def dedupe_claims(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out = []
        for it in items:
            c = (it.get("claim") or "").strip()
            key = c.lower()
            if not c:
                continue
            if key in seen:
                # merge citations
                for existing in out:
                    if existing.get("claim", "").strip().lower() == key:
                        existing_cits = existing.get("citations", []) or []
                        new_cits = it.get("citations", []) or []
                        seen_keys = {_citation_key(citation) for citation in existing_cits}
                        merged_cits = list(existing_cits)
                        for citation in new_cits:
                            citation_key = _citation_key(citation)
                            if citation_key in seen_keys:
                                continue
                            seen_keys.add(citation_key)
                            merged_cits.append(citation)
                        existing["citations"] = merged_cits
                        break
                continue
            seen.add(key)
            it_copy = {**it}
            it_copy["claim"] = truncate_claim(it_copy.get("claim", ""))
            it_copy.setdefault("citations", [])
            out.append(it_copy)
        return out

    # Remove generic-language claims unless they have supporting evidence (citations or numeric detail)
    banned_terms = ["scalable", "flexible", "robust", "seamless", "enterprise-grade", "powerful", "scalability", "flexibility"]

    def is_generic_claim(claim: str, citations: list[str]) -> bool:
        low = (claim or "").lower()
        if not low:
            return False
        # if claim contains numbers or % or currency, consider it specific
        if re.search(r"\d+|%|\$|€|£|k\b|m\b", low):
            return False
        if citations and len(citations) > 0:
            return False
        # if any banned term appears, treat as generic
        return any(term in low for term in banned_terms)

    # Strip generic claims early
    sections_raw = payload.get("sections", {}) or {}
    for sec_key, items in list(sections_raw.items()):
        new_items = []
        for it in items or []:
            claim = str(it.get("claim", "") or "")
            cits = it.get("citations", []) or []
            if is_generic_claim(claim, cits):
                # drop generic claim
                continue
            new_items.append(it)
        sections_raw[sec_key] = new_items or items
    payload["sections"] = sections_raw

    # Normalize all sections
    for sec in SECTIONS:
        items = sections.get(sec) or []
        items = dedupe_claims(items)
        sections[sec] = items[:max_bullets] if items else [{"claim": "Not enough public data found.", "citations": []}]

    # Ensure sales talk track exists; synthesize from weaknesses and strengths if empty
    st_key = "sales_talk_track_objection_handling"
    if not sections.get(st_key) or sections.get(st_key) == [{"claim": "Not enough public data found.", "citations": []}]:
        synth: list[dict[str, Any]] = []
        # Use weaknesses to create reframed bullets
        weaknesses = sections.get("weaknesses_risks", [])
        strengths = sections.get("strengths", [])
        for w in weaknesses[:4]:
            claim = w.get("claim", "")
            if not claim:
                continue
            # Create a sales-focused counterpoint without adding facts
            synth.append({"claim": f"Emphasize {claim} as a vulnerability and offer our differentiated solution.", "citations": w.get("citations", [])})
        # If no weaknesses, use strengths to suggest leverage points
        if not synth and strengths:
            for s in strengths[:4]:
                synth.append({"claim": f"Leverage {s.get('claim','')} to highlight faster time-to-value vs competitor.", "citations": s.get("citations", [])})

        sections[st_key] = synth[:max_bullets] if synth else [{"claim": "Not enough public data found.", "citations": []}]

    payload["sections"] = sections
    # Ensure sources list exists
    payload.setdefault("sources", payload.get("sources", []))
    payload.setdefault("signals", payload.get("signals", []))
    _ensure_sales_payload(payload)
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    sources = payload.get("sources", [])
    source_index: dict[str, int] = {}
    source_index_by_id: dict[str, int] = {}
    for idx, source in enumerate(sources, start=1):
        url = source.get("url")
        sid = source.get("id")
        if url:
            source_index[url] = idx
        if sid:
            source_index_by_id[str(sid)] = idx

    lines = [f"# Battlecard: {payload.get('competitor_name', 'Unknown')}", ""]
    summary = payload.get("summary") or {}
    if summary.get("key_insight"):
        lines.extend(["## Key insight", f"- {summary.get('key_insight')}", ""])

    deal_guidance = payload.get("deal_guidance") or {}
    if deal_guidance:
        lines.extend(["## Deal guidance", "### When we win"])
        for item in deal_guidance.get("when_we_win", []):
            lines.append(f"- {item.get('claim', 'Not enough public data found.')}")
        lines.append("")
        lines.append("### When we lose")
        for item in deal_guidance.get("when_we_lose", []):
            lines.append(f"- {item.get('claim', 'Not enough public data found.')}")
        lines.append("")

    if payload.get("how_to_beat"):
        lines.append("## How to beat")
        for item in payload.get("how_to_beat", []):
            lines.append(f"- {item.get('claim', 'Not enough public data found.')}")
        lines.append("")

    if payload.get("talk_track"):
        lines.append("## Talk track")
        for item in payload.get("talk_track", []):
            lines.append(f"- {item.get('claim', 'Not enough public data found.')}")
        lines.append("")

    if payload.get("objection_handling"):
        lines.append("## Objection handling")
        for item in payload.get("objection_handling", []):
            lines.append(f"- Objection: {item.get('objection', 'Not enough public data found.')}")
            lines.append(f"  Response: {item.get('response', 'Not enough public data found.')}")
        lines.append("")

    section_titles = {
        "competitor_overview": "Competitor overview",
        "positioning": "Positioning",
        "pricing_posture": "Pricing posture",
        "recent_launches_announcements": "Recent launches / announcements",
        "strengths": "Strengths",
        "weaknesses_risks": "Weaknesses / risks",
        "customer_sentiment": "Customer sentiment",
        "customer_reviews": "Customer reviews",
        "sales_talk_track_objection_handling": "Sales talk track / objection handling",
    }

    for section_key, display in section_titles.items():
        lines.append(f"## {display}")
        claims = payload.get("sections", {}).get(section_key, [])
        if not claims:
            lines.append("- Not enough public data found.")
            lines.append("")
            continue

        for item in claims:
            claim = item.get("claim", "Not enough public data found.")
            citations = item.get("citations", [])
            labels = []
            for cit in citations:
                # citation can be a url string, id string, or dict with source_id/url
                cit_id = None
                cit_url = None
                if isinstance(cit, dict):
                    cit_id = cit.get("source_id") or cit.get("id")
                    cit_url = cit.get("url")
                else:
                    # string
                    if str(cit).startswith("http"):
                        cit_url = str(cit)
                    else:
                        cit_id = str(cit)

                index = None
                if cit_id:
                    index = source_index_by_id.get(str(cit_id))
                if index is None and cit_url:
                    index = source_index.get(cit_url)
                if index:
                    labels.append(f"[S{index}]")
            citation_suffix = f" {' '.join(labels)}" if labels else ""
            lines.append(f"- {claim}{citation_suffix}")
        lines.append("")

    lines.append("## Sources")
    if not sources:
        lines.append("- Not enough public data found.")
    else:
        for idx, source in enumerate(sources, start=1):
            title = source.get("title", source.get("url", ""))
            url = source.get("url", "")
            lines.append(f"- [S{idx}] {title} - {url}")

    return "\n".join(lines)
