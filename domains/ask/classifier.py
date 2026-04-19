from __future__ import annotations

import re
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
from domains.query_intelligence.hosted_normalization import normalize_query_for_routing
from domains.query_intelligence.models import QueryNormalizationResult
from domains.hadith.citations.parser import parse_hadith_citation


_QURAN_CANONICAL_RE = re.compile(r"^quran:(?P<surah>\d+):(?P<start>\d+)(?:-(?P<end>\d+))?(?::[a-z]+)?$", re.IGNORECASE)
_HADITH_CANONICAL_RE = re.compile(r"^hadith:(?P<collection>[a-z0-9\-]+):(?P<number>\d+)$", re.IGNORECASE)
_ORDINAL_VERSE_RE = re.compile(r"\b(?P<ordinal>first|1st|second|2nd|third|3rd|fourth|4th|last)\s+verse\b", re.IGNORECASE)
_NEXT_PREV_VERSE_RE = re.compile(r"\b(?P<direction>next|previous|prev|before|after)\s+verse\b", re.IGNORECASE)
_GENERIC_FOLLOWUP_RE = re.compile(r"\b(?:what\s+does\s+this\s+mean|what\s+about\s+this|what\s+about\s+that|explain\s+this|summarize\s+this|summarise\s+this|what\s+lesson|what\s+does\s+this\s+teach)\b", re.IGNORECASE)
_HADITH_FOLLOWUP_RE = re.compile(r"\b(?:summari[sz]e\s+this\s+hadith|what\s+lesson\s+does\s+this\s+hadith\s+teach|what\s+does\s+this\s+hadith\s+mean|explain\s+this\s+hadith|summari[sz]e\s+this|what\s+lesson\s+does\s+this\s+teach)\b", re.IGNORECASE)
_SIMPLIFY_FOLLOWUP_RE = re.compile(r"\b(?:say\s+it\s+more\s+simply|say\s+that\s+more\s+simply|simplify(?:\s+(?:this|that|it))?|explain\s+(?:it|this|that)\s+simply|explain\s+(?:it|this|that)\s+in\s+(?:simple|plain)\s+words|(?:in|using)\s+(?:simple|plain)\s+words)\b", re.IGNORECASE)
_REPEAT_FOLLOWUP_RE = re.compile(r"\b(?:show\s+the\s+exact\s+wording\s+again|repeat\s+that|quote\s+that\s+again|show\s+it\s+again)\b", re.IGNORECASE)
_CONTINUE_RE = re.compile(r"^\s*(?:yes|agree|yep|sure|continue|go\s+on|read\s+more|keep\s+reading|what\'?s\s+next|next(?:\s+part|\s+section|\s+page)?)\b", re.IGNORECASE)
_PREVIOUS_SECTION_RE = re.compile(r"^\s*(?:go\s+back|previous(?:\s+part|\s+section|\s+page)?|back(?:\s+up)?|read\s+(?:the\s+)?previous)\b", re.IGNORECASE)

# Quran surah ayah counts (1-indexed by surah number). Canonical truth: Tanzil.net mushaf.
_SURAH_AYAH_COUNTS: dict[int, int] = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
    11: 112, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
    21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
    31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
    41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45,
    51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
    61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
    71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
    81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
    91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
    101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3,
    111: 5, 112: 4, 113: 5, 114: 6,
}
_COMPARE_RE = re.compile(r"\bcompare\b", re.IGNORECASE)
_SHOW_ONLY_RE = re.compile(r"\bshow\s+only\b", re.IGNORECASE)
_BROAD_TOPIC_SHIFT_RE = re.compile(r"\b(?:what does islam say about|generally|in general|theme|topical tafsir|about this theme|give me ahadith|give me hadith)\b", re.IGNORECASE)
_TAFSIR_SOURCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btafheem\b", re.IGNORECASE), 'tafsir:tafheem-al-quran-en'),
    (re.compile(r"\bma['’]?arif\b", re.IGNORECASE), 'tafsir:maarif-al-quran-en'),
    (re.compile(r"\bibn\s*kathir\b", re.IGNORECASE), 'tafsir:ibn-kathir-en'),
    (re.compile(r"\bkathir\b", re.IGNORECASE), 'tafsir:ibn-kathir-en'),
]
_ORDINAL_MAP = {
    'first': 1,
    '1st': 1,
    'second': 2,
    '2nd': 2,
    'third': 3,
    '3rd': 3,
    'fourth': 4,
    '4th': 4,
}


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


def _extract_anchor_refs(request_context: dict[str, Any] | None) -> list[str]:
    if not isinstance(request_context, dict):
        return []
    raw = request_context.get('anchor_refs')
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = str(item or '').strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        values.append(cleaned)
    return values


def _parse_quran_anchor(anchor_ref: str) -> dict[str, int | str] | None:
    match = _QURAN_CANONICAL_RE.match(str(anchor_ref or '').strip())
    if not match:
        return None
    surah_no = int(match.group('surah'))
    start = int(match.group('start'))
    end = int(match.group('end') or start)
    return {
        'canonical_ref': f'quran:{surah_no}:{start}-{end}' if end != start else f'quran:{surah_no}:{start}',
        'surah_no': surah_no,
        'ayah_start': start,
        'ayah_end': end,
    }


def _parse_hadith_anchor(anchor_ref: str) -> dict[str, str] | None:
    match = _HADITH_CANONICAL_RE.match(str(anchor_ref or '').strip())
    if not match:
        return None
    collection_slug = match.group('collection')
    hadith_number = match.group('number')
    return {
        'canonical_ref': f'hadith:{collection_slug}:{hadith_number}',
        'collection_slug': collection_slug,
        'collection_source_id': f'hadith:{collection_slug}',
        'hadith_number': hadith_number,
    }


def _detect_tafsir_source_ids(text: str) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for pattern, source_id in _TAFSIR_SOURCE_PATTERNS:
        if not pattern.search(text):
            continue
        if source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
    return source_ids


def _resolve_followup_quran_target(text: str, quran_anchor: dict[str, int | str]) -> dict[str, Any] | None:
    surah_no = int(quran_anchor['surah_no'])
    ayah_start = int(quran_anchor['ayah_start'])
    ayah_end = int(quran_anchor['ayah_end'])
    span_length = (ayah_end - ayah_start) + 1

    ordinal_match = _ORDINAL_VERSE_RE.search(text)
    if ordinal_match:
        ordinal = ordinal_match.group('ordinal').lower()
        if ordinal == 'last':
            target_ayah = ayah_end
        else:
            offset = _ORDINAL_MAP.get(ordinal)
            if offset is None or offset > span_length:
                return None
            target_ayah = ayah_start + offset - 1
        return {
            'canonical_ref': f'quran:{surah_no}:{target_ayah}',
            'surah_no': surah_no,
            'ayah_start': target_ayah,
            'ayah_end': target_ayah,
            'followup_kind': 'verse_within_anchor_span',
        }

    direction_match = _NEXT_PREV_VERSE_RE.search(text)
    if direction_match:
        direction = direction_match.group('direction').lower()
        if direction in {'previous', 'prev', 'before'}:
            target_ayah = max(1, ayah_start - 1)
        else:
            target_ayah = ayah_end + 1
        return {
            'canonical_ref': f'quran:{surah_no}:{target_ayah}',
            'surah_no': surah_no,
            'ayah_start': target_ayah,
            'ayah_end': target_ayah,
            'followup_kind': 'adjacent_verse',
        }

    if _GENERIC_FOLLOWUP_RE.search(text):
        return {
            'canonical_ref': quran_anchor['canonical_ref'],
            'surah_no': surah_no,
            'ayah_start': ayah_start,
            'ayah_end': ayah_end,
            'followup_kind': 'anchored_scope_repeat',
        }
    return None


def _looks_like_broad_anchored_shift(text: str) -> bool:
    return bool(_BROAD_TOPIC_SHIFT_RE.search(text))


def _looks_like_fresh_scoped_tafsir_query(text: str) -> bool:
    if not text:
        return False
    tafsir_source_ids = _detect_tafsir_source_ids(text)
    if not tafsir_source_ids and not detect_tafsir_intent(text)['matched']:
        return False
    if looks_like_explicit_quran_reference(text)['matched']:
        return True
    lowered = text.casefold()
    return 'surah ' in lowered or 'surat ' in lowered or 'sura ' in lowered or 'chapter ' in lowered


def _build_continuation_route(
    *,
    continuation_state: dict[str, Any],
    hydrated_state: dict[str, Any] | None,
    quran_anchor: dict[str, Any] | None,
    anchor_refs: set[str] | frozenset[str] | list[str],
    text: str,
    direction: str,
) -> dict[str, Any] | None:
    """Build a continuation route with surah clamping and cross-surah auto-advance."""
    continuation_mode = continuation_state.get('continuation_mode')
    scope = (hydrated_state or {}).get('scope', {})

    if continuation_mode == 'quran_with_tafsir':
        route_type = AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value
        requested_tafsir: list[str] = list(scope.get('tafsir_source_ids') or scope.get('comparative_tafsir_source_ids') or [])
    else:
        route_type = AskRouteType.ANCHORED_FOLLOWUP_QURAN.value
        requested_tafsir = []

    cont_ref = str(continuation_state.get('reference') or '')
    cont_parsed = _parse_quran_anchor(cont_ref) if cont_ref else None
    if cont_parsed is None and quran_anchor is not None:
        cont_parsed = quran_anchor

    followup_quran_ref = None
    parsed_reference = None
    continuation_signals: list[str] = ['anchor_refs_present', 'continuation_intent']

    if cont_parsed:
        surah_no = int(cont_parsed['surah_no'])
        ayah_count = _SURAH_AYAH_COUNTS.get(surah_no, 0)

        if direction == 'forward':
            prev_end = int(cont_parsed['ayah_end'])
            next_start = prev_end + 1
            next_end = next_start + 4  # 5-verse window

            if next_start > ayah_count:
                # Current surah is completed — auto-advance to next surah
                if surah_no >= 114:
                    continuation_signals.append('quran_completed')
                    # Return a graceful termination route
                    return {
                        'route_type': route_type,
                        'action_type': AskActionType.EXPLAIN.value,
                        'confidence': 0.95,
                        'signals': continuation_signals,
                        'secondary_intents': ['anchored_followup', 'continuation'],
                        'reason': 'quran_reading_completed',
                        'normalized_query': text,
                        'anchor_refs': list(anchor_refs),
                        'requested_tafsir_source_ids': requested_tafsir,
                        'followup_kind': 'continuation',
                        'surah_completed': True,
                        'quran_completed': True,
                    }
                # Advance to surah N+1, verses 1-5
                surah_no = surah_no + 1
                next_start = 1
                new_ayah_count = _SURAH_AYAH_COUNTS.get(surah_no, 0)
                next_end = min(5, new_ayah_count) if new_ayah_count else 5
                continuation_signals.append('cross_surah_advance')
            else:
                # Clamp ayah_end to actual surah length
                if ayah_count and next_end > ayah_count:
                    next_end = ayah_count
                    if next_end == ayah_count:
                        continuation_signals.append('surah_boundary_reached')
        else:
            # Backward navigation
            prev_start = int(cont_parsed['ayah_start'])
            next_end = prev_start - 1
            next_start = max(1, next_end - 4)  # 5-verse window backwards

            if next_end < 1:
                # Already at the beginning of the surah
                continuation_signals.append('surah_start_reached')
                next_start = 1
                next_end = min(5, ayah_count) if ayah_count else 5

        canonical = f"quran:{surah_no}:{next_start}-{next_end}" if next_end != next_start else f"quran:{surah_no}:{next_start}"
        followup_quran_ref = {
            'resolved': True,
            'canonical_source_id': canonical,
            'surah_no': surah_no,
            'ayah_start': next_start,
            'ayah_end': next_end,
            'parse_type': 'continuation',
        }
        parsed_reference = {
            'surah_no': surah_no,
            'ayah_start': next_start,
            'ayah_end': next_end,
            'parse_type': 'continuation',
        }

    result: dict[str, Any] = {
        'route_type': route_type,
        'action_type': AskActionType.EXPLAIN.value,
        'confidence': 0.95,
        'signals': continuation_signals,
        'secondary_intents': ['anchored_followup', 'continuation'],
        'reason': 'continuous_reading_intent_detected',
        'normalized_query': text,
        'anchor_refs': list(anchor_refs),
        'requested_tafsir_source_ids': requested_tafsir,
        'followup_kind': 'continuation',
        'continuation_direction': direction,
    }
    if followup_quran_ref:
        result['followup_quran_ref'] = followup_quran_ref
    if parsed_reference:
        result['parsed_reference'] = parsed_reference
        result['reference_text'] = followup_quran_ref['canonical_source_id'] if followup_quran_ref else ''
    return result


def _classify_anchored_followup(text: str, request_context: dict[str, Any] | None) -> dict[str, Any] | None:
    anchor_refs = _extract_anchor_refs(request_context)
    if not anchor_refs:
        return None

    quran_anchor = next((parsed for ref in anchor_refs if (parsed := _parse_quran_anchor(ref)) is not None), None)
    hadith_anchor = next((parsed for ref in anchor_refs if (parsed := _parse_hadith_anchor(ref)) is not None), None)
    tafsir_anchor_refs = [ref for ref in anchor_refs if str(ref).startswith('tafsir:')]

    tafsir_source_ids = _detect_tafsir_source_ids(text)
    compare_requested = bool(_COMPARE_RE.search(text))
    show_only_requested = bool(_SHOW_ONLY_RE.search(text))
    fresh_scoped_tafsir_query = _looks_like_fresh_scoped_tafsir_query(text)

    hydrated_state = request_context.get('_hydrated_session_state') if request_context else None
    continuation_state = (hydrated_state or {}).get('scope', {}).get('continuation')
    is_forward = bool(continuation_state and _CONTINUE_RE.search(text))
    is_backward = bool(continuation_state and _PREVIOUS_SECTION_RE.search(text))
    if continuation_state and (is_forward or is_backward):
        return _build_continuation_route(
            continuation_state=continuation_state,
            hydrated_state=hydrated_state,
            quran_anchor=quran_anchor,
            anchor_refs=anchor_refs,
            text=text,
            direction='forward' if is_forward else 'backward',
        )

    if hadith_anchor is not None and _HADITH_FOLLOWUP_RE.search(text):
        return {
            'route_type': AskRouteType.ANCHORED_FOLLOWUP_HADITH.value,
            'action_type': AskActionType.EXPLAIN.value,
            'confidence': 0.9,
            'signals': ['anchor_refs_present', 'anchored_hadith_followup'],
            'secondary_intents': ['anchored_followup'],
            'reason': 'anchored_hadith_followup_detected',
            'normalized_query': text,
            'anchor_refs': list(anchor_refs),
            'parsed_hadith_citation': {
                'collection_source_id': hadith_anchor['collection_source_id'],
                'collection_slug': hadith_anchor['collection_slug'],
                'reference_type': 'collection_number',
                'canonical_ref': hadith_anchor['canonical_ref'],
                'hadith_number': hadith_anchor['hadith_number'],
                'book_number': None,
                'chapter_number': None,
            },
            'followup_kind': 'hadith_followup',
        }

    tafsir_intent = detect_tafsir_intent(text)['matched']
    if quran_anchor is not None and not fresh_scoped_tafsir_query and not _looks_like_broad_anchored_shift(text) and (tafsir_source_ids or tafsir_intent or compare_requested or show_only_requested):
        return {
            'route_type': AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value,
            'action_type': AskActionType.EXPLAIN.value,
            'confidence': 0.88,
            'signals': ['anchor_refs_present', 'anchored_tafsir_followup'] + (['tafsir_source_focus'] if tafsir_source_ids else []) + (['compare_request'] if compare_requested else []),
            'secondary_intents': ['anchored_followup', 'tafsir_request'],
            'reason': 'anchored_tafsir_followup_detected',
            'normalized_query': text,
            'anchor_refs': list(anchor_refs),
            'followup_quran_ref': quran_anchor,
            'requested_tafsir_source_ids': list(tafsir_source_ids),
            'compare_requested': compare_requested,
            'show_only_requested': show_only_requested,
            'followup_kind': 'tafsir_source_followup',
        }

    if quran_anchor is not None:
        quran_target = _resolve_followup_quran_target(text, quran_anchor)
        if quran_target is not None:
            return {
                'route_type': AskRouteType.ANCHORED_FOLLOWUP_QURAN.value,
                'action_type': AskActionType.EXPLAIN.value,
                'confidence': 0.86,
                'signals': ['anchor_refs_present', 'anchored_quran_followup'],
                'secondary_intents': ['anchored_followup'],
                'reason': 'anchored_quran_followup_detected',
                'normalized_query': text,
                'anchor_refs': list(anchor_refs),
                'followup_quran_ref': quran_target,
                'followup_kind': str(quran_target.get('followup_kind') or 'anchored_scope_repeat'),
            }

    return None


def looks_like_anchored_followup_candidate(query: str, *, normalized_query: str | None = None) -> bool:
    text = normalize_query_text(normalized_query if normalized_query is not None else query)
    if not text:
        return False
    if _looks_like_fresh_scoped_tafsir_query(text):
        return False
    if _HADITH_FOLLOWUP_RE.search(text):
        return True
    if _GENERIC_FOLLOWUP_RE.search(text):
        return True
    if _SIMPLIFY_FOLLOWUP_RE.search(text):
        return True
    if _REPEAT_FOLLOWUP_RE.search(text):
        return True
    if _CONTINUE_RE.search(text) or _PREVIOUS_SECTION_RE.search(text):
        return True
    if _ORDINAL_VERSE_RE.search(text) or _NEXT_PREV_VERSE_RE.search(text):
        return True
    if _detect_tafsir_source_ids(text):
        return True
    if _COMPARE_RE.search(text) or _SHOW_ONLY_RE.search(text):
        return True
    return False


def _apply_surah_bounds(parsed: dict[str, Any]) -> dict[str, Any]:
    if parsed.get("ayah_start") is None and parsed.get("ayah_end") is None:
        return {**parsed, "ayah_start": 1, "ayah_end": 5}
    return parsed


def classify_ask_query(
    query: str,
    request_context: dict[str, Any] | None = None,
    *,
    normalization_result: QueryNormalizationResult | None = None,
) -> dict[str, Any]:
    normalization = normalization_result or normalize_query_for_routing(query)
    text = normalize_query_text(normalization.normalized_query)
    if not text:
        return {
            "route_type": AskRouteType.POLICY_RESTRICTED_REQUEST.value,
            "action_type": AskActionType.UNKNOWN.value,
            "confidence": 0.0,
            "signals": [],
            "reason": "empty_query",
            "normalized_query": "",
            "query_normalization": normalization.to_payload(),
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
            "query_normalization": normalization.to_payload(),
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
            "parsed_reference": _apply_surah_bounds(explicit["parsed"]),
            "reference_text": explicit["reference_text"],
            "reference_match_type": explicit["match_type"],
            "query_normalization": normalization.to_payload(),
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
            "query_normalization": normalization.to_payload(),
        }

    anchored_followup = _classify_anchored_followup(text, request_context)
    if anchored_followup is not None:
        anchored_followup.setdefault("query_normalization", normalization.to_payload())
        return anchored_followup

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
            "parsed_reference": _apply_surah_bounds(named_anchor["parsed"]),
            "reference_text": named_anchor["canonical_ref"].replace('quran:', '').replace(':', ':'),
            "reference_match_type": "named_anchor",
            "query_normalization": normalization.to_payload(),
        }

    topical = detect_topical_query_intent(text, allow_multi_source=True)
    if topical.get("matched"):
        detected_route_type = str(topical.get("route_type") or '')
        if detected_route_type == AskRouteType.TOPICAL_MULTI_SOURCE_QUERY.value:
            return {
                "route_type": AskRouteType.POLICY_RESTRICTED_REQUEST.value,
                "action_type": AskActionType.UNKNOWN.value,
                "confidence": float(topical.get("confidence") or 0.6),
                "signals": list(topical.get("signals") or []),
                "secondary_intents": ["topical_retrieval"],
                "reason": "public_mixed_source_topic_requires_future_planner",
                "normalized_query": text,
                "topic_query": str(topical.get("topic_query") or text),
                "restriction_reason": "public_mixed_source_topic_requires_future_planner",
                "query_normalization": normalization.to_payload(),
            }
        return {
            "route_type": detected_route_type,
            "action_type": str(topical.get("action_type") or AskActionType.EXPLAIN.value),
            "confidence": float(topical.get("confidence") or 0.7),
            "signals": list(topical.get("signals") or []),
            "secondary_intents": ["topical_retrieval"],
            "reason": str(topical.get("reason") or "supported_topical_query_detected"),
            "normalized_query": text,
            "topic_query": str(topical.get("topic_query") or text),
            "query_normalization": normalization.to_payload(),
        }

    if topical.get("needs_clarification"):
        clarify = build_clarify_instruction(
            reason=str(topical.get("reason") or "needs_clarification"),
            domain=str(topical.get('clarify_domain') or 'hadith'),
            concept_matches=list(topical.get('concept_matches') or []),
        )
        payload = {
            "route_type": AskRouteType.BROAD_SOURCE_GROUNDED_QUERY.value,
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
        payload['query_normalization'] = normalization.to_payload()
        return payload

    return {
        "route_type": AskRouteType.POLICY_RESTRICTED_REQUEST.value,
        "action_type": AskActionType.UNKNOWN.value,
        "confidence": 0.15,
        "signals": arabic_quote.get("signals", []),
        "reason": arabic_quote.get("reason") or str(topical.get("reason") or "unsupported_query_type_for_now"),
        "normalized_query": text,
        "restriction_reason": str(topical.get("reason") or "unsupported_query_type_for_now"),
        "query_normalization": normalization.to_payload(),
    }
