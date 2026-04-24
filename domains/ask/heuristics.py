from __future__ import annotations

import re
from typing import Any

from domains.quran.verifier.matching import detect_quran_query_route
from domains.quran.citations.normalizer import normalize_reference_text
from domains.quran.citations.reference_parser import parse_quran_reference
from domains.quran.citations.surah_aliases import SURAH_ALIASES, resolve_surah_name
from domains.ask.route_types import AskActionType

ARABIC_LETTER_RE = re.compile(r"[\u0621-\u063A\u0641-\u064A\u066E-\u06D3\u06FA-\u06FF]")
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
ARABIC_TOKEN_RE = re.compile(r"[\u0600-\u06FF]+")
ARABIC_SEGMENT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\s\u0640\u0610-\u061A\u06D6-\u06ED\u0660-\u0669]+")
# Bidi format controls (LRM/RLM, embedding/override, isolates, BOM). Injected by
# some clipboards when copying Arabic — invisible but break ARABIC_SEGMENT_RE
# fullmatch, silently routing short quotes (e.g. muqatta'at) to policy_restricted.
_BIDI_CONTROL_RE = re.compile(r"[‎‏‪-‮⁦-⁩﻿]")
DIGIT_REFERENCE_RE = re.compile(r"\b(?P<surah>\d{1,3})\s*:\s*(?P<start>\d{1,3})(?:\s*[-–—]\s*(?P<end>\d{1,3}))?\b")
SURAH_PREFIX_RE = re.compile(
    r"\b(?:surah|surat|surahs)\s+(?P<name>[a-z][a-z\-\s']{1,40}?)(?:\s+(?:ayah|ayahs|verse|verses)\s*)?(?P<start>\d{1,3})?(?:\s*[-–—]\s*(?P<end>\d{1,3}))?\b",
    re.IGNORECASE,
)
AYAH_OF_SURAH_RE = re.compile(
    r"\b(?:ayah|ayahs|verse|verses)\s+(?P<start>\d{1,3})(?:\s*[-–—]\s*(?P<end>\d{1,3}))?\s+of\s+(?:surah|surat)\s+(?P<name>[a-z][a-z\-\s']{1,40})\b",
    re.IGNORECASE,
)
SURAH_ONLY_RE = re.compile(
    r"\b(?:surah|surat)\s+(?P<name>[a-z][a-z\-\s']{1,40})\b",
    re.IGNORECASE,
)

VERIFY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bis this true\b",
        r"\bis this real\b",
        r"\bis this correct\b",
        r"\bis this authentic\b",
        r"\bis this from (?:the )?quran\b",
        r"\bverify\b",
        r"\bcheck if\b",
        r"\bconfirm\b",
        r"\bsource\b",
        r"\bwhere is this from\b",
        r"\bdoes this exist\b",
        r"\bquote check\b",
    ]
]

EXPLAIN_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bexplain\b",
        r"\bmeaning\b",
        r"\bmean\b",
        r"\bwhat does\b",
        r"\bwhat is being said\b",
        r"\btafsir\b",
        r"\binterpret\b",
        r"\bcommentary\b",
    ]
]

FETCH_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bshow me\b",
        r"\bshow\b",
        r"\bgive me\b",
        r"\bquote\b",
        r"\bdisplay\b",
        r"\bwhat does .* say\b",
        r"\bwhat is\b",
        r"\bbring\b",
        r"\bfetch\b",
        r"\btext\b",
    ]
]

WHAT_DOES_SAY_RE = re.compile(r"\bwhat does .+ say\b", re.IGNORECASE)

ARABIC_VERIFY_HINT_RE = re.compile(r"(?:هل هذا صحيح|هل هذا من القرآن|تحقق|تأكد|صحيح\?)")
ARABIC_EXPLAIN_HINT_RE = re.compile(r"(?:اشرح|فسر|ما معنى|ما تفسير|وضح)")

# Longest aliases first so 'al ikhlas' beats 'ikhlas'.
SURAH_ALIAS_KEYS = sorted(SURAH_ALIASES.keys(), key=len, reverse=True)
SURAH_ALIAS_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(alias) for alias in SURAH_ALIAS_KEYS) + r")\b",
    re.IGNORECASE,
)


def normalize_query_text(query: str) -> str:
    stripped = _BIDI_CONTROL_RE.sub("", query or "")
    return re.sub(r"\s+", " ", stripped.strip())


def _normalize_range(start: str | None, end: str | None) -> tuple[int | None, int | None]:
    if not start:
        return None, None
    s = int(start)
    e = int(end) if end else s
    return s, e


def _build_reference_text(surah_no: int | None, ayah_start: int | None = None, ayah_end: int | None = None, *,
                          surah_name: str | None = None) -> str | None:
    if surah_no is None and not surah_name:
        return None

    if surah_name:
        base = f"surah {surah_name}"
    elif surah_no is not None:
        if ayah_start is None:
            return str(surah_no)
        base = str(surah_no)
    else:
        return None

    if ayah_start is None:
        return base
    if ayah_end is None or ayah_end == ayah_start:
        suffix = str(ayah_start)
    else:
        suffix = f"{ayah_start}-{ayah_end}"

    if surah_name:
        return f"{base} {suffix}"
    return f"{base}:{suffix}"


def get_explicit_reference_parse(query: str) -> dict[str, Any] | None:
    normalized = normalize_reference_text(query)
    if not normalized:
        return None
    return parse_quran_reference(normalized)


def extract_explicit_reference_candidate(query: str) -> dict[str, Any] | None:
    text = normalize_query_text(query)
    if not text:
        return None

    # 1) Direct parse of the whole normalized query.
    direct_normalized = normalize_reference_text(text)
    direct_parsed = parse_quran_reference(direct_normalized) if direct_normalized else None
    if direct_parsed is not None:
        return {
            "matched": True,
            "reference_text": direct_normalized,
            "parsed": direct_parsed,
            "match_type": "whole_query_parse",
            "signals": ["explicit_reference_parse"],
        }

    # 2) Numeric citations embedded in natural language.
    digit_match = DIGIT_REFERENCE_RE.search(text)
    if digit_match:
        reference_text = _build_reference_text(
            int(digit_match.group("surah")),
            int(digit_match.group("start")),
            int(digit_match.group("end")) if digit_match.group("end") else None,
        )
        parsed = parse_quran_reference(reference_text or "")
        if parsed is not None:
            return {
                "matched": True,
                "reference_text": reference_text,
                "parsed": parsed,
                "match_type": "embedded_numeric_reference",
                "signals": ["embedded_numeric_reference"],
            }

    lower_text = text.lower()

    # 3) 'ayah 255 of surah baqarah' style.
    ayah_of_surah = AYAH_OF_SURAH_RE.search(lower_text)
    if ayah_of_surah:
        name = (ayah_of_surah.group("name") or "").strip()
        surah_no = resolve_surah_name(name)
        if surah_no is not None:
            start, end = _normalize_range(ayah_of_surah.group("start"), ayah_of_surah.group("end"))
            reference_text = _build_reference_text(None, start, end, surah_name=name)
            parsed = parse_quran_reference(reference_text or "")
            if parsed is not None:
                return {
                    "matched": True,
                    "reference_text": reference_text,
                    "parsed": parsed,
                    "match_type": "ayah_of_surah_reference",
                    "signals": ["ayah_of_surah_reference"],
                }

    # 4) 'surah ikhlas' or 'surah ash-sharh 5-6' anywhere in the sentence.
    for pattern in (SURAH_PREFIX_RE, SURAH_ONLY_RE):
        for match in pattern.finditer(lower_text):
            raw_name = (match.group("name") or "").strip(" .,!?:;\"'")
            if not raw_name:
                continue
            alias_match = SURAH_ALIAS_PATTERN.search(raw_name)
            candidate_name = alias_match.group(0) if alias_match else raw_name
            surah_no = resolve_surah_name(candidate_name)
            if surah_no is None:
                continue
            start, end = _normalize_range(match.groupdict().get("start"), match.groupdict().get("end"))
            reference_text = _build_reference_text(None, start, end, surah_name=candidate_name)
            parsed = parse_quran_reference(reference_text or "")
            if parsed is not None:
                signal = "surah_reference_with_range" if start is not None else "surah_reference_name"
                return {
                    "matched": True,
                    "reference_text": reference_text,
                    "parsed": parsed,
                    "match_type": signal,
                    "signals": [signal],
                }

    # 5) '<surah alias> 255' style without the word 'surah'. We only allow it if an alias is found.
    alias_match = SURAH_ALIAS_PATTERN.search(lower_text)
    if alias_match:
        alias_name = alias_match.group(0)
        surah_no = resolve_surah_name(alias_name)
        if surah_no is not None:
            trailing = lower_text[alias_match.end():]
            ayah_match = re.search(r"\b(?P<start>\d{1,3})(?:\s*[-–—]\s*(?P<end>\d{1,3}))?\b", trailing)
            if ayah_match:
                start, end = _normalize_range(ayah_match.group("start"), ayah_match.group("end"))
                reference_text = _build_reference_text(None, start, end, surah_name=alias_name)
                parsed = parse_quran_reference(reference_text or "")
                if parsed is not None:
                    return {
                        "matched": True,
                        "reference_text": reference_text,
                        "parsed": parsed,
                        "match_type": "surah_alias_with_range",
                        "signals": ["surah_alias_with_range"],
                    }

    return None


def looks_like_explicit_quran_reference(query: str) -> dict[str, Any]:
    text = normalize_query_text(query)
    extracted = extract_explicit_reference_candidate(text)
    if extracted is None:
        return {
            "matched": False,
            "normalized_query": normalize_reference_text(text),
            "signals": [],
            "parsed": None,
            "reference_text": None,
            "match_type": None,
        }

    return {
        "matched": True,
        "normalized_query": normalize_reference_text(text),
        "signals": extracted["signals"],
        "parsed": extracted["parsed"],
        "reference_text": extracted["reference_text"],
        "match_type": extracted["match_type"],
    }


def extract_arabic_quote_payload(query: str) -> str | None:
    text = normalize_query_text(query)
    if not text:
        return None

    segments = [re.sub(r"\s+", " ", m.group(0)).strip() for m in ARABIC_SEGMENT_RE.finditer(text)]
    min_letters = 3 if not LATIN_LETTER_RE.search(text) else 8
    segments = [s for s in segments if len(ARABIC_LETTER_RE.findall(s)) >= min_letters]
    if not segments:
        return None

    payload = " ".join(segments)
    payload = re.sub(r"\s+", " ", payload).strip()
    return payload or None


def looks_like_arabic_quran_quote(query: str) -> dict[str, Any]:
    text = normalize_query_text(query)
    if not text:
        return {
            "matched": False,
            "signals": [],
            "verifier_route": detect_quran_query_route(text),
            "arabic_letter_count": 0,
            "arabic_token_count": 0,
            "latin_letter_count": 0,
            "quote_payload": None,
            "reason": "empty_query",
        }

    arabic_letter_count = len(ARABIC_LETTER_RE.findall(text))
    arabic_token_count = len(ARABIC_TOKEN_RE.findall(text))
    latin_letter_count = len(LATIN_LETTER_RE.findall(text))
    verifier_route = detect_quran_query_route(text)
    payload = extract_arabic_quote_payload(text)
    payload_letter_count = len(ARABIC_LETTER_RE.findall(payload or ""))
    payload_token_count = len(ARABIC_TOKEN_RE.findall(payload or ""))

    signals: list[str] = []
    if arabic_letter_count >= 10:
        signals.append("arabic_length")
    if arabic_token_count >= 2:
        signals.append("arabic_multi_token")
    if verifier_route.get("route") == "UTHMANI_FIRST":
        signals.append("uthmani_markers")
    if verifier_route.get("counts", {}).get("verse_ornaments", 0) > 0:
        signals.append("verse_ornaments")
    if verifier_route.get("counts", {}).get("special_marks", 0) > 0:
        signals.append("special_marks")
    if verifier_route.get("counts", {}).get("small_high_signs", 0) >= 4:
        signals.append("small_high_signs")
    if payload and payload != text:
        signals.append("extracted_arabic_payload")

    arabic_only_payload = (
        latin_letter_count == 0
        and bool(payload)
        and ARABIC_SEGMENT_RE.fullmatch(text) is not None
        and payload_letter_count >= 3
        and payload_token_count >= 1
    )

    if arabic_only_payload:
        signals.append("arabic_only_payload")
    if arabic_only_payload and payload_letter_count < 16:
        signals.append("short_arabic_quote_candidate")

    strong_quote = (
        verifier_route.get("route") == "UTHMANI_FIRST"
        or verifier_route.get("counts", {}).get("verse_ornaments", 0) > 0
        or verifier_route.get("counts", {}).get("special_marks", 0) > 0
        or (payload_letter_count >= 10 and payload_token_count >= 2)
        or (arabic_letter_count >= 20 and arabic_token_count >= 4)
        or arabic_only_payload
    )

    return {
        "matched": bool(strong_quote),
        "signals": signals,
        "verifier_route": verifier_route,
        "arabic_letter_count": arabic_letter_count,
        "arabic_token_count": arabic_token_count,
        "latin_letter_count": latin_letter_count,
        "quote_payload": payload or text,
        "reason": None if strong_quote else "insufficient_quran_quote_signal",
    }


def detect_action_type(query: str, *, route_hint: str | None = None) -> dict[str, Any]:
    text = normalize_query_text(query)
    lower_text = text.lower()
    signals: list[str] = []

    has_verify = any(p.search(lower_text) for p in VERIFY_PATTERNS) or bool(ARABIC_VERIFY_HINT_RE.search(text))
    has_explain = any(p.search(lower_text) for p in EXPLAIN_PATTERNS) or bool(ARABIC_EXPLAIN_HINT_RE.search(text))
    has_fetch = any(p.search(lower_text) for p in FETCH_PATTERNS)

    if has_verify:
        signals.append("verify_language")
    if has_explain:
        signals.append("explain_language")
    if has_fetch:
        signals.append("fetch_language")

    if route_hint == "arabic_quran_quote":
        if has_verify and has_explain:
            return {"action_type": AskActionType.VERIFY_THEN_EXPLAIN.value, "signals": signals}
        if has_verify:
            return {"action_type": AskActionType.VERIFY_SOURCE.value, "signals": signals}
        if has_explain or has_fetch or "?" in text or "؟" in text:
            return {"action_type": AskActionType.VERIFY_THEN_EXPLAIN.value, "signals": signals or ["question_form"]}
        return {"action_type": AskActionType.VERIFY_SOURCE.value, "signals": signals}

    prefers_fetch = bool(WHAT_DOES_SAY_RE.search(lower_text))
    has_tafsir = detect_tafsir_intent(query)["matched"]
    if has_tafsir:
        has_explain = True
        if "tafsir_intent" not in signals:
            signals.append("tafsir_intent")

    if prefers_fetch and has_fetch and not has_verify and not has_tafsir:
        return {"action_type": AskActionType.FETCH_TEXT.value, "signals": signals}
    if has_explain:
        return {"action_type": AskActionType.EXPLAIN.value, "signals": signals}
    if has_fetch:
        return {"action_type": AskActionType.FETCH_TEXT.value, "signals": signals}
    if has_verify:
        return {"action_type": AskActionType.VERIFY_SOURCE.value, "signals": signals}
    return {"action_type": AskActionType.UNKNOWN.value, "signals": signals}


def detect_tafsir_intent(query: str) -> dict[str, Any]:
    text = normalize_query_text(query)
    if not text:
        return {"matched": False, "signals": []}

    patterns = [
        re.compile(r"\btafsir\b", re.IGNORECASE),
        re.compile(r"\bibn\s*kathir\b", re.IGNORECASE),
        re.compile(r"\btafheem\b", re.IGNORECASE),
        re.compile(r"\bma['’]?arif\b", re.IGNORECASE),
        re.compile(r"\bmaududi\b", re.IGNORECASE),
        re.compile(r"\bqurtubi\b", re.IGNORECASE),
        re.compile(r"\btabari\b", re.IGNORECASE),
        re.compile(r"\bjalalayn\b", re.IGNORECASE),
        re.compile(r"\bcommentary\b", re.IGNORECASE),
        re.compile(r"\bcommentators?\b", re.IGNORECASE),
        re.compile(r"\bmufassir\b", re.IGNORECASE),
        re.compile(r"\bexplain with tafsir\b", re.IGNORECASE),
        re.compile(r"\bwhat do (?:the )?(?:commentators|scholars) say\b", re.IGNORECASE),
    ]

    signals = [pattern.pattern for pattern in patterns if pattern.search(text)]
    return {"matched": bool(signals), "signals": signals}
