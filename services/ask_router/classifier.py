from __future__ import annotations

from typing import Any

from services.ask_router.heuristics import (
    detect_action_type,
    looks_like_arabic_quran_quote,
    looks_like_explicit_quran_reference,
    normalize_query_text,
)
from services.ask_router.route_types import AskActionType, AskRouteType


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

    # Strong Arabic quote payload dominates, because quote verification is more specific
    # than a loose sentence-level parse.
    if arabic_quote["matched"] and (not explicit["matched"] or arabic_quote["arabic_letter_count"] >= 20):
        action = detect_action_type(text, route_hint=AskRouteType.ARABIC_QURAN_QUOTE.value)
        return {
            "route_type": AskRouteType.ARABIC_QURAN_QUOTE.value,
            "action_type": action["action_type"],
            "confidence": 0.92 if arabic_quote["verifier_route"].get("route") == "UTHMANI_FIRST" else 0.84,
            "signals": arabic_quote["signals"] + action["signals"],
            "reason": "strong_arabic_quote_payload_detected",
            "normalized_query": text,
            "verifier_route": arabic_quote["verifier_route"],
            "arabic_letter_count": arabic_quote["arabic_letter_count"],
            "arabic_token_count": arabic_quote["arabic_token_count"],
            "quote_payload": arabic_quote["quote_payload"],
        }

    if explicit["matched"]:
        action = detect_action_type(text, route_hint=AskRouteType.EXPLICIT_QURAN_REFERENCE.value)
        action_type = action["action_type"]
        if action_type == AskActionType.UNKNOWN.value:
            action_type = AskActionType.EXPLAIN.value
        return {
            "route_type": AskRouteType.EXPLICIT_QURAN_REFERENCE.value,
            "action_type": action_type,
            "confidence": 0.98,
            "signals": explicit["signals"] + action["signals"],
            "reason": "explicit_quran_reference_detected",
            "normalized_query": explicit["normalized_query"],
            "parsed_reference": explicit["parsed"],
            "reference_text": explicit["reference_text"],
            "reference_match_type": explicit["match_type"],
        }

    return {
        "route_type": AskRouteType.UNSUPPORTED_FOR_NOW.value,
        "action_type": AskActionType.UNKNOWN.value,
        "confidence": 0.15,
        "signals": arabic_quote.get("signals", []),
        "reason": arabic_quote.get("reason") or "unsupported_query_type_for_now",
        "normalized_query": text,
    }
