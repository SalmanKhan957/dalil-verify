from __future__ import annotations

from typing import Any

from domains.ask.heuristics import (
    detect_action_type,
    detect_tafsir_intent,
    looks_like_arabic_quran_quote,
    looks_like_explicit_quran_reference,
    normalize_query_text,
)
from domains.ask.route_types import AskActionType, AskRouteType
from domains.ask.topical_query import detect_topical_query_intent
from domains.query_intelligence.concept_linker import link_query_to_concepts
from domains.query_intelligence.clarify_mode import build_clarify_instruction, serialize_clarify_instruction
from domains.hadith.citations.parser import parse_hadith_citation




def _resolve_named_quran_anchor(text: str) -> dict[str, Any] | None:
    concept_matches = link_query_to_concepts(text, domain='quran_anchor', max_results=1)
    if not concept_matches:
        return None
    match = concept_matches[0]
    canonical_ref = match.canonical_ref
    if not canonical_ref or not canonical_ref.startswith('quran:'):
        return None
    parts = canonical_ref.split(':')
    if len(parts) != 3:
        return None
    try:
        surah_no = int(parts[1])
        ayah_no = int(parts[2])
    except ValueError:
        return None
    return {
        'canonical_ref': canonical_ref,
        'parsed': {
            'surah_no': surah_no,
            'ayah_start': ayah_no,
            'ayah_end': ayah_no,
            'parse_type': 'named_anchor',
        },
        'match': match,
    }

def classify_ask_query(query: str) -> dict[str, Any]:
    text = normalize_query_text(query)
    if not text:
        return {
            "route_type": AskRouteType.UNSUPPORTED_FOR_NOW.value,
            "action_type": AskActionType.UNKNOWN.value,
            "confidence": 0.0,
            "signals": [],
            "reason": "empty_query",
            "normalized_query": "",
        }

    explicit = looks_like_explicit_quran_reference(text)
    arabic_quote = looks_like_arabic_quran_quote(text)
    hadith_citation = parse_hadith_citation(text)

    if arabic_quote["matched"] and (not explicit["matched"] or arabic_quote["arabic_letter_count"] >= 20):
        action = detect_action_type(text, route_hint=AskRouteType.ARABIC_QURAN_QUOTE.value)
        tafsir_intent = detect_tafsir_intent(text)
        secondary_intents: list[str] = []
        if tafsir_intent["matched"]:
            secondary_intents.append("tafsir_request")
        if action["action_type"] in {AskActionType.VERIFY_SOURCE.value, AskActionType.VERIFY_THEN_EXPLAIN.value}:
            secondary_intents.append("quote_verification")
        return {
            "route_type": AskRouteType.ARABIC_QURAN_QUOTE.value,
            "action_type": action["action_type"],
            "confidence": 0.92 if arabic_quote["verifier_route"].get("route") == "UTHMANI_FIRST" else 0.84,
            "signals": arabic_quote["signals"] + action["signals"] + (["tafsir_intent"] if tafsir_intent["matched"] else []),
            "secondary_intents": secondary_intents,
            "reason": "strong_arabic_quote_payload_detected",
            "normalized_query": text,
            "verifier_route": arabic_quote["verifier_route"],
            "arabic_letter_count": arabic_quote["arabic_letter_count"],
            "arabic_token_count": arabic_quote["arabic_token_count"],
            "quote_payload": arabic_quote["quote_payload"],
        }

    if explicit["matched"]:
        action = detect_action_type(text, route_hint=AskRouteType.EXPLICIT_QURAN_REFERENCE.value)
        tafsir_intent = detect_tafsir_intent(text)
        action_type = action["action_type"]
        if action_type == AskActionType.UNKNOWN.value:
            action_type = AskActionType.EXPLAIN.value
        return {
            "route_type": AskRouteType.EXPLICIT_QURAN_REFERENCE.value,
            "action_type": action_type,
            "confidence": 0.98,
            "signals": explicit["signals"] + action["signals"] + (["tafsir_intent"] if tafsir_intent["matched"] else []),
            "secondary_intents": ["tafsir_request"] if tafsir_intent["matched"] else [],
            "reason": "explicit_quran_reference_detected",
            "normalized_query": explicit["normalized_query"],
            "parsed_reference": explicit["parsed"],
            "reference_text": explicit["reference_text"],
            "reference_match_type": explicit["match_type"],
        }

    if hadith_citation is not None:
        action = detect_action_type(text, route_hint=AskRouteType.EXPLICIT_HADITH_REFERENCE.value)
        action_type = action["action_type"]
        if action_type == AskActionType.UNKNOWN.value:
            action_type = AskActionType.FETCH_TEXT.value
        secondary_intents: list[str] = ["hadith_citation_lookup"]
        if action_type == AskActionType.EXPLAIN.value:
            secondary_intents.append("hadith_explanation_request")
        return {
            "route_type": AskRouteType.EXPLICIT_HADITH_REFERENCE.value,
            "action_type": action_type,
            "confidence": 0.95,
            "signals": ["hadith_citation_parse"] + action["signals"],
            "secondary_intents": secondary_intents,
            "reason": "explicit_hadith_reference_detected",
            "normalized_query": text,
            "parsed_hadith_citation": {
                "collection_source_id": hadith_citation.collection_source_id,
                "collection_slug": hadith_citation.collection_slug,
                "reference_type": hadith_citation.reference_type.value,
                "canonical_ref": hadith_citation.canonical_ref,
                "hadith_number": hadith_citation.hadith_number,
                "book_number": hadith_citation.book_number,
                "chapter_number": hadith_citation.chapter_number,
            },
        }

    named_anchor = _resolve_named_quran_anchor(text)
    if named_anchor is not None:
        action = detect_action_type(text, route_hint=AskRouteType.EXPLICIT_QURAN_REFERENCE.value)
        tafsir_intent = detect_tafsir_intent(text)
        action_type = action["action_type"]
        if action_type == AskActionType.UNKNOWN.value:
            action_type = AskActionType.EXPLAIN.value
        return {
            "route_type": AskRouteType.EXPLICIT_QURAN_REFERENCE.value,
            "action_type": action_type,
            "confidence": 0.9,
            "signals": ["named_quran_anchor"] + action["signals"] + (["tafsir_intent"] if tafsir_intent["matched"] else []),
            "secondary_intents": ["tafsir_request"] if tafsir_intent["matched"] else [],
            "reason": "named_quran_anchor_detected",
            "normalized_query": text,
            "parsed_reference": named_anchor["parsed"],
            "reference_text": named_anchor["canonical_ref"].replace('quran:', '').replace(':', ':'),
            "reference_match_type": "named_anchor",
        }



    topical = detect_topical_query_intent(text, allow_multi_source=False)
    if topical.get("matched"):
        return {
            "route_type": str(topical.get("route_type")),
            "action_type": str(topical.get("action_type") or AskActionType.EXPLAIN.value),
            "confidence": float(topical.get("confidence") or 0.7),
            "signals": list(topical.get("signals") or []),
            "secondary_intents": ["topical_retrieval"],
            "reason": str(topical.get("reason") or "supported_topical_query_detected"),
            "normalized_query": text,
            "topic_query": str(topical.get("topic_query") or text),
        }

    if topical.get("needs_clarification"):
        clarify = build_clarify_instruction(
            reason=str(topical.get("reason") or "needs_clarification"),
            domain=str(topical.get('clarify_domain') or 'hadith'),
            concept_matches=list(topical.get('concept_matches') or []),
        )
        payload = {
            "route_type": AskRouteType.UNSUPPORTED_FOR_NOW.value,
            "action_type": AskActionType.UNKNOWN.value,
            "confidence": float(topical.get("confidence") or 0.5),
            "signals": list(topical.get("signals") or []),
            "reason": str(topical.get("reason") or "needs_clarification"),
            "normalized_query": text,
            "topic_query": str(topical.get("topic_query") or text),
            "needs_clarification": True,
        }
        if clarify is not None:
            payload['clarify'] = serialize_clarify_instruction(clarify)
        return payload

    return {
        "route_type": AskRouteType.UNSUPPORTED_FOR_NOW.value,
        "action_type": AskActionType.UNKNOWN.value,
        "confidence": 0.15,
        "signals": arabic_quote.get("signals", []),
        "reason": arabic_quote.get("reason") or str(topical.get("reason") or "unsupported_query_type_for_now"),
        "normalized_query": text,
    }
