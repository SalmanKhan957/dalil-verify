from __future__ import annotations

from enum import Enum


class AskRouteType(str, Enum):
    EXPLICIT_QURAN_REFERENCE = "explicit_quran_reference"
    ARABIC_QURAN_QUOTE = "arabic_quran_quote"
    EXPLICIT_HADITH_REFERENCE = "explicit_hadith_reference"
    TOPICAL_TAFSIR_QUERY = "topical_tafsir_query"
    TOPICAL_HADITH_QUERY = "topical_hadith_query"
    TOPICAL_MULTI_SOURCE_QUERY = "topical_multi_source_query"
    UNSUPPORTED_FOR_NOW = "unsupported_for_now"


class AskActionType(str, Enum):
    EXPLAIN = "explain"
    FETCH_TEXT = "fetch_text"
    VERIFY_SOURCE = "verify_source"
    VERIFY_THEN_EXPLAIN = "verify_then_explain"
    UNKNOWN = "unknown"
