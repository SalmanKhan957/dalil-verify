from __future__ import annotations

"""Stable internal facade for Quran matching and routing primitives.

Application/runtime modules should import from this package instead of reaching
directly into scripts/* so the runtime has a clean dependency boundary.
"""

from domains.quran.verifier.internal.query_routing import (
    ROUTE_SIMPLE_FIRST,
    ROUTE_UTHMANI_FIRST,
    detect_quran_query_route,
)
from domains.quran.verifier.internal.quran_citation_units import get_result_canonical_unit_type
from domains.quran.verifier.internal.quran_match_collections import (
    build_exact_groups,
    build_lane_match_collections,
    build_passage_rows_by_window_size,
    build_unique_exact_map,
)
from domains.quran.verifier.internal.quran_passage_neighbors import (
    build_passage_row_lookup,
    load_passage_neighbor_lookup,
)
from domains.quran.verifier.internal.quran_span_index import (
    GIANT_ANCHOR_SIZE,
    GIANT_MIN_TOKEN_COUNT,
    QuranSurahSpanIndex,
)
from domains.quran.verifier.internal.retrieval_shortlist import QuranShortlistIndex
from shared.utils.arabic_text import (
    normalize_arabic_aggressive,
    normalize_arabic_light,
    sanitize_quran_text_for_matching,
    sanitize_quran_text_for_matching_with_meta,
    tokenize,
)

__all__ = [
    "ROUTE_SIMPLE_FIRST",
    "ROUTE_UTHMANI_FIRST",
    "detect_quran_query_route",
    "get_result_canonical_unit_type",
    "build_exact_groups",
    "build_lane_match_collections",
    "build_passage_rows_by_window_size",
    "build_unique_exact_map",
    "build_passage_row_lookup",
    "load_passage_neighbor_lookup",
    "GIANT_ANCHOR_SIZE",
    "GIANT_MIN_TOKEN_COUNT",
    "QuranSurahSpanIndex",
    "QuranShortlistIndex",
    "normalize_arabic_aggressive",
    "normalize_arabic_light",
    "sanitize_quran_text_for_matching",
    "sanitize_quran_text_for_matching_with_meta",
    "tokenize",
]
