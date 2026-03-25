from __future__ import annotations

from typing import Any

CANONICAL_UNIT_RANKS = {
    "single_ayah": 4,
    "contiguous_span": 3,
    "static_window": 2,
    "heuristic_expansion": 1,
    "unknown": 0,
}


def get_canonical_unit_rank(unit_type: str | None) -> int:
    return CANONICAL_UNIT_RANKS.get(unit_type or "unknown", 0)


def _get_start_ayah(best_match: dict[str, Any]) -> int | None:
    value = best_match.get("start_ayah")
    if value is None:
        value = best_match.get("ayah_start")
    return int(value) if value is not None else None


def _get_end_ayah(best_match: dict[str, Any]) -> int | None:
    value = best_match.get("end_ayah")
    if value is None:
        value = best_match.get("ayah_end")
    return int(value) if value is not None else None


def classify_ayah_best_match(best_match: dict[str, Any] | None) -> str:
    if not best_match:
        return "unknown"
    return "single_ayah"


def classify_passage_best_match(best_match: dict[str, Any] | None) -> str:
    if not best_match:
        return "unknown"

    start_ayah = _get_start_ayah(best_match)
    end_ayah = _get_end_ayah(best_match)
    window_size = int(best_match.get("window_size") or 0)
    engine = (best_match.get("retrieval_engine") or "").strip()

    # If passage lane actually resolves to one ayah, call it what it is.
    if start_ayah is not None and end_ayah is not None and start_ayah == end_ayah:
        return "single_ayah"

    # True contiguous span engines
    if engine in {"surah_span_exact", "surah_span_partial", "giant_exact_anchor"}:
        return "contiguous_span"

    # Heuristic / expansion-style engines
    if engine in {"local_seed_expand", "token_subsequence", "giant_partial_anchor"}:
        return "heuristic_expansion"

    # If there is no engine stamped but this is clearly multi-ayah passage output,
    # treat it as a static retrieval window.
    if window_size > 1:
        return "static_window"

    if window_size == 1:
        return "single_ayah"

    return "unknown"


def get_result_canonical_unit_type(result: dict[str, Any] | None, lane: str | None = None) -> str:
    if not result:
        return "unknown"

    best_match = result.get("best_match") or {}
    if not best_match:
        return "unknown"

    if lane == "ayah":
        return classify_ayah_best_match(best_match)

    if lane == "passage":
        return classify_passage_best_match(best_match)

    # Fallback inference
    if "ayah_no" in best_match and "start_ayah" not in best_match:
        return classify_ayah_best_match(best_match)

    return classify_passage_best_match(best_match)


def get_result_canonical_unit_rank(result: dict[str, Any] | None, lane: str | None = None) -> int:
    return get_canonical_unit_rank(get_result_canonical_unit_type(result, lane=lane))


def annotate_result_with_canonical_unit(result: dict[str, Any] | None, lane: str | None = None) -> dict[str, Any] | None:
    if not result:
        return result

    unit_type = get_result_canonical_unit_type(result, lane=lane)
    unit_rank = get_canonical_unit_rank(unit_type)

    result["canonical_unit_type"] = unit_type
    result["canonical_unit_rank"] = unit_rank

    best_match = result.get("best_match")
    if isinstance(best_match, dict):
        best_match["canonical_unit_type"] = unit_type
        best_match["canonical_unit_rank"] = unit_rank

    return result