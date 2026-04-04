
from __future__ import annotations

from typing import Any

from services.quran_runtime.matching import (
    GIANT_ANCHOR_SIZE,
    GIANT_MIN_TOKEN_COUNT,
    QuranSurahSpanIndex,
)
from services.quran_runtime.matching import normalize_arabic_light, tokenize


GIANT_MIN_CHAR_COUNT = 350


def is_long_span_fastpath_enabled(query: str) -> bool:
    normalized = normalize_arabic_light(query)
    token_count = len(tokenize(normalized))
    return token_count >= GIANT_MIN_TOKEN_COUNT or len(normalized) >= GIANT_MIN_CHAR_COUNT


def try_long_span_exact_match(
    query: str,
    *,
    surah_span_index: QuranSurahSpanIndex | None,
    likely_surahs: list[int] | None = None,
    min_window_size: int = 2,
    top_k: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if surah_span_index is None:
        return [], {"engine": "none", "candidate_count": 0, "reason": "surah_span_index_unavailable"}

    if not is_long_span_fastpath_enabled(query):
        return [], {"engine": "none", "candidate_count": 0, "reason": "fastpath_not_enabled"}

    return surah_span_index.find_giant_exact_passage_candidates(
        query,
        likely_surahs=likely_surahs,
        min_window_size=min_window_size,
        top_k=top_k,
        anchor_size=GIANT_ANCHOR_SIZE,
        min_token_count=GIANT_MIN_TOKEN_COUNT,
    )


def build_long_span_debug_block(meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    return {
        "enabled": True,
        "engine": meta.get("engine"),
        "candidate_count": meta.get("candidate_count", 0),
        "lookup_source": meta.get("lookup_source"),
        "surah_scope": meta.get("surah_scope"),
        "anchor_size": meta.get("anchor_size", GIANT_ANCHOR_SIZE),
        "query_token_count": meta.get("query_token_count"),
        "reason": meta.get("reason"),
    }

