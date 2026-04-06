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
from domains.hadith.citations.parser import parse_hadith_citation


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

    # Strong Arabic quote payload dominates, because quote verification is more specific
    # than a loose sentence-level parse.
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

    return {
        "route_type": AskRouteType.UNSUPPORTED_FOR_NOW.value,
        "action_type": AskActionType.UNKNOWN.value,
        "confidence": 0.15,
        "signals": arabic_quote.get("signals", []),
        "reason": arabic_quote.get("reason") or "unsupported_query_type_for_now",
        "normalized_query": text,
    }
