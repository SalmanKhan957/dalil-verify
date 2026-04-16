from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from domains.quran.verifier import bootstrap as verifier_runtime
from infrastructure.config.release_lock import build_release_posture, get_startup_validation_info
from infrastructure.telemetry.logging import append_jsonl_log
from domains.quran.verifier.translation import attach_english_translation
from domains.quran.verifier.long_span_fastpath import (
    build_long_span_debug_block,
    is_long_span_fastpath_enabled,
    try_long_span_exact_match,
)
from domains.quran.verifier.matching import get_result_canonical_unit_type
from domains.quran.verifier.matching import build_lane_match_collections
from domains.quran.verifier.ranking import get_status_rank
from domains.quran.verifier.matching import (
    ROUTE_SIMPLE_FIRST,
    ROUTE_UTHMANI_FIRST,
    detect_quran_query_route,
)
from domains.quran.verifier.matching import (
    normalize_arabic_aggressive,
    normalize_arabic_light,
    sanitize_quran_text_for_matching_with_meta,
    tokenize,
)
from domains.quran.verifier.matching import GIANT_MIN_TOKEN_COUNT
from domains.quran.verifier.ranking import build_fusion_output
from domains.quran.verifier.ranking import (
    build_passage_result,
    compute_best_passage_matches,
)
from domains.quran.verifier.ranking import (
    build_ayah_result,
    compute_ayah_matches,
    determine_match_status,
    assess_verifier_query,
)

from domains.quran.verifier.types import CorpusRuntime


def build_health_payload() -> dict:
    return {
        "status": "ok",
        "service": "dalil-verify-api",
        "simple_runtime_loaded": verifier_runtime.SIMPLE_RUNTIME is not None,
        "simple_quran_rows_loaded": len(verifier_runtime.SIMPLE_RUNTIME.rows) if verifier_runtime.SIMPLE_RUNTIME else 0,
        "simple_quran_passage_rows_loaded": len(verifier_runtime.SIMPLE_RUNTIME.passage_rows) if verifier_runtime.SIMPLE_RUNTIME else 0,
        "uthmani_runtime_loaded": verifier_runtime.UTHMANI_RUNTIME is not None,
        "uthmani_quran_rows_loaded": len(verifier_runtime.UTHMANI_RUNTIME.rows) if verifier_runtime.UTHMANI_RUNTIME else 0,
        "uthmani_quran_passage_rows_loaded": len(verifier_runtime.UTHMANI_RUNTIME.passage_rows) if verifier_runtime.UTHMANI_RUNTIME else 0,
        "english_translation_loaded": verifier_runtime.ENGLISH_TRANSLATION_INFO.get("loaded", False),
        "english_translation_rows_loaded": verifier_runtime.ENGLISH_TRANSLATION_INFO.get("row_count", 0),
        "runtime_artifacts": verifier_runtime.RUNTIME_ARTIFACT_INFO,
        "source_governance": verifier_runtime.SOURCE_GOVERNANCE_INFO,
        "release_posture": build_release_posture(),
        "startup_validation": get_startup_validation_info(),
    }


# remaining file unchanged from original after build_health_payload

def _resolve_exact_ayah_row(query: str, runtime: CorpusRuntime) -> tuple[dict | None, dict[str, str | bool]]:
    light = normalize_arabic_light(query)
    aggressive = normalize_arabic_aggressive(query)

    row = runtime.exact_light_map.get(light)
    if row:
        return row, {"matched": True, "strategy": f"{runtime.label}_exact_ayah_light", "ambiguous": False}
    if light in runtime.exact_light_map and runtime.exact_light_map[light] is None:
        return None, {"matched": False, "strategy": f"{runtime.label}_exact_ayah_light_ambiguous", "ambiguous": True}

    row = runtime.exact_aggressive_map.get(aggressive)
    if row:
        return row, {"matched": True, "strategy": f"{runtime.label}_exact_ayah_aggressive", "ambiguous": False}
    if aggressive in runtime.exact_aggressive_map and runtime.exact_aggressive_map[aggressive] is None:
        return None, {"matched": False, "strategy": f"{runtime.label}_exact_ayah_aggressive_ambiguous", "ambiguous": True}

    return None, {"matched": False, "strategy": "none", "ambiguous": False}


def _prefer_ayah_for_exact_single_ayah(ayah_result: dict, passage_result: dict) -> None:
    ayah_best = (ayah_result or {}).get("best_match") or {}
    passage_best = (passage_result or {}).get("best_match") or {}
    if not ayah_best or not passage_best:
        return
    if (ayah_result or {}).get("match_status") != "Exact match found":
        return
    if passage_best.get("window_size", 1) <= 1:
        return
    component_citations = set(passage_best.get("component_citations") or [])
    ayah_citation = ayah_best.get("citation")
    if ayah_citation and ayah_citation in component_citations:
        passage_result["match_status"] = "Close / partial match found"
        passage_result["confidence"] = "medium"


def _dedupe_candidates(candidates: list[dict], limit: int = 5) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        row = candidate.get("row") or {}
        key = row.get("canonical_source_id") or row.get("citation_string")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


def _sort_candidates(candidates: list[dict], limit: int = 5) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda x: (
            x.get("score", 0.0),
            x.get("exact_normalized_light", 0.0),
            x.get("contains_query_in_text_light", 0.0),
            x.get("token_coverage", 0.0),
        ),
        reverse=True,
    )
    return _dedupe_candidates(ordered, limit=limit)


def _build_non_retrieval_response(
    query: str,
    *,
    preferred_lane: str,
    boundary_note: str,
    debug_payload: dict | None = None,
) -> dict:
    return {
        "query": query,
        "preferred_lane": preferred_lane,
        "match_status": "Cannot assess",
        "confidence": "low",
        "boundary_note": boundary_note,
        "best_match": None,
        "exact_matches": [],
        "strong_matches": [],
        "also_related": [],
        "debug": debug_payload,
    }


def _empty_ayah_result(query: str) -> dict:
    return {
        "query": query,
        "mode": "verifier",
        "match_status": "No reliable match found in current corpus",
        "confidence": "low",
        "boundary_note": (
            "Based only on the current indexed Quran Arabic source. "
            "This is not a fatwa or a complete survey of all Islamic literature."
        ),
        "best_match": None,
        "alternatives": [],
    }


def _empty_passage_result(query: str) -> dict:
    return {
        "query": query,
        "mode": "verifier",
        "match_status": "No reliable match found in current corpus",
        "confidence": "low",
        "boundary_note": (
            "Based only on the current indexed Quran passage source. "
            "This is not a fatwa or a complete survey of all Islamic literature."
        ),
        "best_match": None,
        "alternatives": [],
    }


def _safe_build_ayah_result(query: str, candidates: list[dict]) -> dict:
    if not candidates:
        return _empty_ayah_result(query)
    try:
        return build_ayah_result(query, candidates[:5])
    except IndexError:
        return _empty_ayah_result(query)


def _safe_build_passage_result(query: str, candidates: list[dict]) -> dict:
    if not candidates:
        return _empty_passage_result(query)
    try:
        return build_passage_result(query, candidates[:5])
    except IndexError:
        return _empty_passage_result(query)


LONG_QUERY_TOKEN_THRESHOLD = 15
LONG_QUERY_AYAH_SHORTLIST_LIMIT = 180
LONG_QUERY_PASSAGE_SHORTLIST_LIMIT = 120
LONG_QUERY_AYAH_TOP_K = 8


def _is_long_query(query: str) -> bool:
    return len(tokenize(normalize_arabic_light(query))) >= LONG_QUERY_TOKEN_THRESHOLD


def _query_token_count(query: str) -> int:
    return len(tokenize(normalize_arabic_light(query)))


def _is_giant_query(query: str) -> bool:
    return _query_token_count(query) >= GIANT_MIN_TOKEN_COUNT


def _has_any_runtime_exact_ayah_signal(query: str) -> bool:
    """
    Allow ultra-short canonical ayah input to bypass the Cannot-assess gate
    if the query has an exact-ayah signal in any active runtime.

    This covers both:
    - unique exact ayah hits (row is not None)
    - repeated exact ayah strings like الم where the exact map is ambiguous
      because the same normalized text exists in multiple ayat
    """
    for runtime in [verifier_runtime.SIMPLE_RUNTIME, verifier_runtime.UTHMANI_RUNTIME]:
        if runtime is None:
            continue

        row, meta = _resolve_exact_ayah_row(query, runtime)
        if row is not None:
            return True

        if bool(meta.get("ambiguous")):
            return True

    return False


def _likely_surahs_from_ayah_candidates(candidates: list[dict], limit: int = 3) -> list[int]:
    scores: dict[int, float] = {}
    for candidate in candidates[:12]:
        row = candidate.get("row") or {}
        surah_no = row.get("surah_no")
        if surah_no is None:
            continue
        surah_no = int(surah_no)
        scores[surah_no] = scores.get(surah_no, 0.0) + float(candidate.get("score") or 0.0)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [surah for surah, _ in ordered[:limit]]


def _strong_passage_win(public_response: dict) -> bool:
    best = public_response.get("best_match") or {}
    coverage = float((best.get("scoring_breakdown") or {}).get("token_coverage") or 0.0)
    unit_type = best.get("canonical_unit_type") or get_result_canonical_unit_type(
        {"best_match": best},
        lane="passage",
    )

    return (
        public_response.get("preferred_lane") == "passage"
        and public_response.get("match_status") == "Exact match found"
        and public_response.get("confidence") == "high"
        and coverage >= 95.0
        and float(best.get("score") or 0.0) >= 80.0
        and unit_type in {"single_ayah", "contiguous_span"}
    )



def _build_related_ayah_candidates_for_strong_matches(
    runtime: CorpusRuntime,
    *,
    query: str,
    long_query: bool,
    base_limit: int,
) -> tuple[list[dict], dict]:
    if runtime.ayah_shortlist_index is None:
        return [], {"strategy": "unavailable", "candidate_count": 0, "reason": "ayah_shortlist_index_missing"}

    shortlist_rows, shortlist_meta = runtime.ayah_shortlist_index.shortlist_rows(
        query,
        limit=base_limit,
        allow_exact_shortcircuit=False,
    )
    candidates = compute_ayah_matches(
        query,
        shortlist_rows,
        top_k=LONG_QUERY_AYAH_TOP_K if long_query else 5,
    )
    return candidates, {
        **shortlist_meta,
        "strategy": f"{runtime.label}_related_ayah_token_qgram",
        "reason": "support_strong_matches_after_unique_exact_ayah",
    }


def _candidate_is_exact_match(
    query: str,
    candidate: dict | None,
    *,
    min_window_size: int = 1,
) -> bool:
    if not candidate:
        return False
    row = candidate.get("row") or {}
    if int(row.get("window_size") or 1) < min_window_size:
        return False
    try:
        return determine_match_status(query, candidate) == "Exact match found"
    except Exception:
        return False


def _best_candidate_is_exact_match(
    query: str,
    candidates: list[dict] | None,
    *,
    min_window_size: int = 1,
) -> bool:
    return _candidate_is_exact_match(
        query,
        candidates[0] if candidates else None,
        min_window_size=min_window_size,
    )


def _is_terminal_exact_passage_engine(engine: str | None) -> bool:
    return engine in {"static_exact_window", "surah_span_exact", "giant_exact_anchor"}


def _merge_passage_candidates(
    runtime: CorpusRuntime,
    query: str,
    *,
    static_candidates: list[dict],
    ayah_candidates: list[dict],
) -> tuple[list[dict], dict]:
    if runtime.surah_span_index is None or not _is_long_query(query):
        return _sort_candidates(static_candidates, limit=5), {"engine": "static_window", "candidate_count": len(static_candidates[:5])}

    dynamic_candidates, dynamic_meta = runtime.surah_span_index.find_long_passage_candidates(
        query,
        ayah_seed_candidates=ayah_candidates,
        passage_seed_candidates=static_candidates,
        min_window_size=2,
        max_window_size=40,
        top_k=5,
    )
    if not dynamic_candidates:
        return _sort_candidates(static_candidates, limit=5), {"engine": "static_window", "candidate_count": len(static_candidates[:5])}

    merged = _sort_candidates(dynamic_candidates + static_candidates, limit=5)
    engine = dynamic_meta.get("engine") or "static_window"
    return merged, {
        "engine": engine,
        "candidate_count": len(merged),
        "dynamic_candidate_count": len(dynamic_candidates),
        **dynamic_meta,
    }


def _should_include_related(preferred_result: dict, related_item: dict | None) -> bool:
    if not related_item:
        return False
    score = float(related_item.get("score") or 0.0)
    preferred_status = preferred_result.get("match_status")
    preferred_confidence = preferred_result.get("confidence")
    if preferred_status == "Exact match found" and preferred_confidence == "high":
        return score >= 40.0
    return score >= 15.0


def compact_result_for_api(
    fusion_output: dict,
    *,
    debug: bool = False,
    english_translation_map: dict[tuple[int, int], dict] | None = None,
    query_preprocessing: dict | None = None,
    query_routing: dict | None = None,
    selected_runtime: str | None = None,
    runtime_evaluations: list[dict] | None = None,
    stage_timings: dict | None = None,
    exact_matches: list[dict[str, Any]] | None = None,
    strong_matches: list[dict[str, Any]] | None = None,
    collection_debug: dict[str, Any] | None = None,
) -> dict:
    preferred_lane = fusion_output.get("preferred_lane", "none")
    preferred_result = fusion_output.get("preferred_result") or {}
    preferred_best = preferred_result.get("best_match")
    secondary_result = fusion_output.get("secondary_result") or {}
    secondary_best = secondary_result.get("best_match")

    if preferred_best:
        preferred_best = attach_english_translation(preferred_best, english_translation_map or {})
        preferred_best["matching_corpus"] = selected_runtime

    response = {
        "query": fusion_output.get("query", ""),
        "preferred_lane": preferred_lane,
        "match_status": preferred_result.get("match_status", "Cannot assess"),
        "confidence": preferred_result.get("confidence", "low"),
        "boundary_note": preferred_result.get(
            "boundary_note",
            "Based only on the current indexed Quran sources.",
        ),
        "best_match": preferred_best,
        "exact_matches": [dict(item) for item in (exact_matches or [])],
        "strong_matches": [dict(item) for item in (strong_matches or [])],
        "also_related": [],
        "debug": None,
    }

    seen_citations = set()
    if preferred_best and preferred_best.get("citation"):
        seen_citations.add(preferred_best["citation"])
    for item in response["exact_matches"] + response["strong_matches"]:
        citation = item.get("citation")
        if citation:
            seen_citations.add(citation)

    if secondary_best:
        secondary_best = attach_english_translation(secondary_best, english_translation_map or {})
        secondary_best["matching_corpus"] = selected_runtime

    if (
        secondary_best
        and secondary_best.get("citation")
        and secondary_best["citation"] not in seen_citations
        and _should_include_related(preferred_result, secondary_best)
    ):
        response["also_related"].append(
            {
                "lane": "passage" if preferred_lane == "ayah" else "ayah",
                "citation": secondary_best.get("citation"),
                "canonical_source_id": secondary_best.get("canonical_source_id"),
                "text_display": secondary_best.get("text_display"),
                "english_translation": secondary_best.get("english_translation"),
                "matching_corpus": selected_runtime,
                "score": secondary_best.get("score"),
            }
        )
        seen_citations.add(secondary_best["citation"])

    for alt in preferred_result.get("alternatives", []):
        citation = alt.get("citation")
        if citation and citation not in seen_citations and _should_include_related(preferred_result, alt):
            alt = dict(alt)
            alt["matching_corpus"] = selected_runtime
            response["also_related"].append(alt)
            seen_citations.add(citation)

    response["also_related"] = response["also_related"][:3]

    if debug:
        response["debug"] = {
            "decision_rule": fusion_output.get("decision_rule"),
            "rationale": fusion_output.get("rationale"),
            "query_token_count": fusion_output.get("query_token_count"),
            "analytics": fusion_output.get("analytics"),
            "ayah_result": fusion_output.get("ayah_result"),
            "passage_result": fusion_output.get("passage_result"),
            "secondary_result": fusion_output.get("secondary_result"),
            "shortlist": fusion_output.get("shortlist"),
            "english_translation": verifier_runtime.ENGLISH_TRANSLATION_INFO,
            "query_preprocessing": query_preprocessing or fusion_output.get("query_preprocessing") or {},
            "query_routing": query_routing or {},
            "selected_runtime": selected_runtime,
            "runtime_evaluations": runtime_evaluations or [],
            "stage_timings": stage_timings or {},
            "collection_debug": collection_debug or {},
        }

    return response


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence or "", 0)


def _is_strong_response(public_response: dict) -> bool:
    best = public_response.get("best_match") or {}
    return (
        public_response.get("match_status") == "Exact match found"
        and public_response.get("confidence") == "high"
        and bool(best)
    )


def _response_strength(public_response: dict) -> tuple[int, int, float, float]:
    best = public_response.get("best_match") or {}
    score = float(best.get("score") or 0.0)
    coverage = float((best.get("scoring_breakdown") or {}).get("token_coverage") or 0.0)
    return (
        get_status_rank(public_response.get("match_status", "")),
        _confidence_rank(public_response.get("confidence", "")),
        score,
        coverage,
    )


def _should_stop_after_runtime(route_meta: dict, evaluation: dict) -> bool:
    response = evaluation["public_response"]
    route = route_meta.get("route")
    if _is_strong_response(response) or _strong_passage_win(response):
        return True
    if route == ROUTE_SIMPLE_FIRST and response.get("preferred_lane") == "passage":
        best = response.get("best_match") or {}
        coverage = float((best.get("scoring_breakdown") or {}).get("token_coverage") or 0.0)
        if coverage >= 80.0 and float(best.get("score") or 0.0) >= 70.0 and int(best.get("window_size") or 0) >= 5:
            return True
    return False


def _fallback_trigger_reason(evaluation: dict) -> str:
    response = evaluation["public_response"]
    if _is_strong_response(response):
        return "strong_exact_stop"
    if _strong_passage_win(response):
        return "strong_passage_stop"
    return "weak_primary_result"


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _elapsed_ms(start_ms: float) -> float:
    return round(_now_ms() - start_ms, 2)


def _evaluate_runtime(
    runtime: CorpusRuntime,
    *,
    raw_query: str,
    matching_query: str,
    debug: bool,
    query_preprocessing: dict,
    query_routing: dict,
) -> dict:
    runtime_start_ms = _now_ms()
    stage_timings: dict[str, float] = {}
    if runtime.ayah_shortlist_index is None or runtime.passage_shortlist_index is None:
        raise HTTPException(status_code=500, detail=f"{runtime.label} runtime indexes are not loaded.")

    long_query = _is_long_query(matching_query)
    giant_query = _is_giant_query(matching_query)
    ayah_related_candidates: list[dict] | None = None
    ayah_related_meta: dict | None = None

    stage_start_ms = _now_ms()
    exact_ayah_row, exact_ayah_meta = _resolve_exact_ayah_row(matching_query, runtime)
    stage_timings["exact_ayah_lookup_ms"] = _elapsed_ms(stage_start_ms)

    giant_fastpath_candidates: list[dict] = []
    giant_fastpath_meta: dict = {"engine": "none", "candidate_count": 0}
    if exact_ayah_row is None and runtime.surah_span_index is not None and is_long_span_fastpath_enabled(matching_query):
        stage_start_ms = _now_ms()
        giant_fastpath_candidates, giant_fastpath_meta = try_long_span_exact_match(
            matching_query,
            surah_span_index=runtime.surah_span_index,
            likely_surahs=None,
            min_window_size=2,
            top_k=1,
        )
        stage_timings["giant_fastpath_ms"] = _elapsed_ms(stage_start_ms)

    if giant_fastpath_candidates:
        ayah_shortlist_rows = []
        ayah_shortlist_meta = {"strategy": "skipped_due_to_giant_exact_fastpath", "candidate_count": 0}
        ayah_candidates = []
        stage_timings["ayah_shortlist_ms"] = 0.0
        stage_timings["ayah_scoring_ms"] = 0.0
        passage_shortlist_rows = []
        passage_shortlist_meta = {
            "strategy": f"{runtime.label}_giant_exact_anchor",
            "candidate_count": 0,
            "lookup_source": giant_fastpath_meta.get("lookup_source"),
        }
        passage_candidates = giant_fastpath_candidates
        dynamic_passage_meta = giant_fastpath_meta
    elif exact_ayah_row is None and giant_query and runtime.surah_span_index is not None:
        # Giant query, but do not skip ayah lane blindly.
        # First give ayah scoring one bounded rescue pass for clipped single-ayah exact excerpts
        # such as long ayah 2:282 pasted without the full ayah boundaries.
        stage_start_ms = _now_ms()
        ayah_limit = LONG_QUERY_AYAH_SHORTLIST_LIMIT if long_query else 250
        ayah_shortlist_rows, ayah_shortlist_meta = runtime.ayah_shortlist_index.shortlist_rows(
            matching_query,
            limit=ayah_limit,
        )
        stage_timings["ayah_shortlist_ms"] = _elapsed_ms(stage_start_ms)

        stage_start_ms = _now_ms()
        ayah_candidates = compute_ayah_matches(
            matching_query,
            ayah_shortlist_rows,
            top_k=LONG_QUERY_AYAH_TOP_K if long_query else 5,
        )
        stage_timings["ayah_scoring_ms"] = _elapsed_ms(stage_start_ms)

        exact_ayah_candidate_hit = _best_candidate_is_exact_match(matching_query, ayah_candidates)
        likely_surahs = _likely_surahs_from_ayah_candidates(ayah_candidates, limit=3) if ayah_candidates else []

        if exact_ayah_candidate_hit:
            passage_shortlist_rows = []
            passage_shortlist_meta = {
                "strategy": f"{runtime.label}_skipped_after_exact_ayah_giant_rescue",
                "candidate_count": 0,
                "reason": "skip_passage_after_exact_ayah_giant_rescue",
                "source": "ayah_scoring",
            }
            passage_candidates = []
            dynamic_passage_meta = {
                "engine": "skipped_after_exact_ayah",
                "candidate_count": 0,
                "reason": "skip_passage_after_exact_ayah_giant_rescue",
                "source": "ayah_scoring",
            }
            stage_timings["giant_partial_ms"] = 0.0
        else:
            stage_start_ms = _now_ms()
            giant_partial_candidates, giant_partial_meta = runtime.surah_span_index.find_giant_partial_passage_candidates(
                matching_query,
                likely_surahs=likely_surahs or None,
                min_window_size=2,
                top_k=5,
            )
            stage_timings["giant_partial_ms"] = _elapsed_ms(stage_start_ms)

            passage_shortlist_rows = []
            passage_shortlist_meta = {
                "strategy": f"{runtime.label}_giant_partial_anchor",
                "candidate_count": 0,
                "lookup_source": giant_partial_meta.get("lookup_source"),
                "surah_scope": giant_partial_meta.get("surah_scope"),
                "ayah_rescue_attempted": True,
            }
            passage_candidates = giant_partial_candidates
            dynamic_passage_meta = giant_partial_meta
            if not giant_partial_candidates:
                dynamic_passage_meta = {
                    **giant_partial_meta,
                    "engine": giant_partial_meta.get("engine") or "giant_partial_anchor",
                    "reason": giant_partial_meta.get("reason", "giant_partial_no_match_fast_fail"),
                    "candidate_count": 0,
                }
    else:
        stage_start_ms = _now_ms()
        if exact_ayah_row is not None:
            ayah_shortlist_rows = [exact_ayah_row]
            ayah_shortlist_meta = {"strategy": exact_ayah_meta.get("strategy"), "candidate_count": 1}
        else:
            ayah_limit = LONG_QUERY_AYAH_SHORTLIST_LIMIT if long_query else 250
            ayah_shortlist_rows, ayah_shortlist_meta = runtime.ayah_shortlist_index.shortlist_rows(
                matching_query,
                limit=ayah_limit,
            )
        stage_timings["ayah_shortlist_ms"] = _elapsed_ms(stage_start_ms)

        stage_start_ms = _now_ms()
        ayah_candidates = compute_ayah_matches(
            matching_query,
            ayah_shortlist_rows,
            top_k=LONG_QUERY_AYAH_TOP_K if long_query else 5,
        )
        stage_timings["ayah_scoring_ms"] = _elapsed_ms(stage_start_ms)

        exact_ayah_candidate_hit = _best_candidate_is_exact_match(matching_query, ayah_candidates)
        likely_surahs = _likely_surahs_from_ayah_candidates(ayah_candidates, limit=3) if long_query else []

        if exact_ayah_candidate_hit:
            if exact_ayah_row is not None:
                stage_start_ms = _now_ms()
                ayah_related_candidates, ayah_related_meta = _build_related_ayah_candidates_for_strong_matches(
                    runtime,
                    query=matching_query,
                    long_query=long_query,
                    base_limit=LONG_QUERY_AYAH_SHORTLIST_LIMIT if long_query else 250,
                )
                stage_timings["ayah_related_shortlist_ms"] = _elapsed_ms(stage_start_ms)
            passage_shortlist_rows = []
            passage_shortlist_meta = {
                "strategy": f"{runtime.label}_skipped_after_exact_ayah",
                "candidate_count": 0,
                "reason": "skip_passage_after_exact_ayah",
                "source": "exact_ayah_map" if exact_ayah_row is not None else "ayah_scoring",
            }
            if ayah_related_meta:
                passage_shortlist_meta["related_ayah_strategy"] = ayah_related_meta.get("strategy")
            passage_candidates = []
            dynamic_passage_meta = {
                "engine": "skipped_after_exact_ayah",
                "candidate_count": 0,
                "reason": "skip_passage_after_exact_ayah",
                "source": "exact_ayah_map" if exact_ayah_row is not None else "ayah_scoring",
            }
            if ayah_related_meta:
                dynamic_passage_meta["related_ayah_strategy"] = ayah_related_meta.get("strategy")
        else:
            passage_limit = LONG_QUERY_PASSAGE_SHORTLIST_LIMIT if long_query else 300
            stage_start_ms = _now_ms()
            passage_shortlist_rows, passage_shortlist_meta = runtime.passage_shortlist_index.shortlist_rows(
                matching_query,
                limit=passage_limit,
            )
            stage_timings["passage_shortlist_ms"] = _elapsed_ms(stage_start_ms)

            stage_start_ms = _now_ms()
            static_passage_candidates = compute_best_passage_matches(matching_query, passage_shortlist_rows, top_k=5)
            stage_timings["passage_scoring_ms"] = _elapsed_ms(stage_start_ms)

            static_exact_passage_hit = _best_candidate_is_exact_match(
                matching_query,
                static_passage_candidates,
                min_window_size=2,
            )

            if static_exact_passage_hit:
                passage_candidates = _sort_candidates(static_passage_candidates, limit=5)
                dynamic_passage_meta = {
                    "engine": "static_exact_window",
                    "candidate_count": len(passage_candidates),
                    "lookup_source": "passage_scoring_exact_verified",
                    "reason": "skip_dynamic_after_exact_static_passage",
                }
            elif long_query and runtime.surah_span_index is not None:
                stage_start_ms = _now_ms()
                exact_long_candidates, exact_long_meta = runtime.surah_span_index.find_exact_span_lookup_candidates(
                    matching_query,
                    min_window_size=2,
                    top_k=5,
                    surah_scope=likely_surahs or None,
                )
                stage_timings["dynamic_passage_ms"] = stage_timings.get("dynamic_passage_ms", 0.0) + _elapsed_ms(stage_start_ms)

                if exact_long_candidates:
                    passage_candidates = exact_long_candidates
                    dynamic_passage_meta = exact_long_meta
                    passage_shortlist_meta = {
                        **passage_shortlist_meta,
                        "exact_precheck_engine": exact_long_meta.get("engine"),
                        "exact_precheck_lookup_source": exact_long_meta.get("lookup_source"),
                    }
                else:
                    stage_start_ms = _now_ms()
                    medium_partial_candidates, medium_partial_meta = runtime.surah_span_index.find_medium_partial_passage_candidates(
                        matching_query,
                        ayah_seed_candidates=ayah_candidates,
                        passage_seed_candidates=static_passage_candidates,
                        likely_surahs=likely_surahs,
                        min_window_size=2,
                        max_window_size=8,
                        top_k=5,
                    )
                    stage_timings["dynamic_passage_ms"] = stage_timings.get("dynamic_passage_ms", 0.0) + _elapsed_ms(stage_start_ms)

                    if medium_partial_candidates:
                        passage_candidates = _sort_candidates(static_passage_candidates + medium_partial_candidates, limit=5)
                        dynamic_passage_meta = medium_partial_meta
                        passage_shortlist_meta = {
                            **passage_shortlist_meta,
                            "exact_precheck_engine": exact_long_meta.get("engine"),
                            "exact_precheck_lookup_source": exact_long_meta.get("lookup_source"),
                            "medium_partial_engine": medium_partial_meta.get("engine"),
                            "medium_partial_lookup_source": medium_partial_meta.get("lookup_source"),
                        }
                    else:
                        stage_start_ms = _now_ms()
                        passage_candidates, dynamic_passage_meta = _merge_passage_candidates(
                            runtime,
                            matching_query,
                            static_candidates=static_passage_candidates,
                            ayah_candidates=ayah_candidates,
                        )
                        stage_timings["dynamic_passage_ms"] = stage_timings.get("dynamic_passage_ms", 0.0) + _elapsed_ms(stage_start_ms)

                        if (
                            runtime.surah_span_index is not None
                            and likely_surahs
                            and not _is_terminal_exact_passage_engine(dynamic_passage_meta.get("engine"))
                            and not _best_candidate_is_exact_match(matching_query, passage_candidates, min_window_size=2)
                        ):
                            stage_start_ms = _now_ms()
                            extra_dynamic, extra_meta = runtime.surah_span_index.find_long_passage_candidates(
                                matching_query,
                                ayah_seed_candidates=ayah_candidates,
                                passage_seed_candidates=static_passage_candidates,
                                likely_surahs=likely_surahs,
                                min_window_size=2,
                                max_window_size=40,
                                top_k=5,
                            )
                            stage_timings["dynamic_passage_ms"] = stage_timings.get("dynamic_passage_ms", 0.0) + _elapsed_ms(stage_start_ms)
                            if extra_dynamic:
                                passage_candidates = _sort_candidates(passage_candidates + extra_dynamic, limit=5)
                                dynamic_passage_meta = extra_meta
            else:
                passage_candidates = _sort_candidates(static_passage_candidates, limit=5)
                dynamic_passage_meta = {
                    "engine": "static_window",
                    "candidate_count": len(passage_candidates),
                }

    ayah_result = _safe_build_ayah_result(matching_query, ayah_candidates)
    passage_result = _safe_build_passage_result(matching_query, passage_candidates)
    if _best_candidate_is_exact_match(matching_query, ayah_candidates):
        _prefer_ayah_for_exact_single_ayah(ayah_result, passage_result)
    if passage_result.get("best_match") and dynamic_passage_meta.get("engine") != "static_window":
        passage_result["best_match"]["retrieval_engine"] = dynamic_passage_meta.get("engine")
        for alt in passage_result.get("alternatives", []):
            alt.setdefault("retrieval_engine", dynamic_passage_meta.get("engine"))

    stage_start_ms = _now_ms()
    fusion_output = build_fusion_output(query=matching_query, ayah_result=ayah_result, passage_result=passage_result)
    stage_timings["fusion_ms"] = _elapsed_ms(stage_start_ms)
    fusion_output["query"] = raw_query
    fusion_output["query_preprocessing"] = {**query_preprocessing, "matching_query": matching_query}
    fusion_output["query_routing"] = query_routing
    fusion_output["shortlist"] = {
        "ayah": ayah_shortlist_meta,
        "ayah_related": ayah_related_meta,
        "passage": passage_shortlist_meta,
        "dynamic_passage": dynamic_passage_meta,
        "giant_fastpath": build_long_span_debug_block(giant_fastpath_meta),
    }
    fusion_output.setdefault("analytics", {})["passage_retrieval_engine"] = (
        (passage_result.get("best_match") or {}).get("retrieval_engine") or dynamic_passage_meta.get("engine")
    )
    fusion_output.setdefault("analytics", {})["matching_corpus"] = runtime.label

    stage_start_ms = _now_ms()
    public_response = compact_result_for_api(
        fusion_output,
        debug=debug,
        english_translation_map=verifier_runtime.ENGLISH_TRANSLATION_MAP,
        query_preprocessing=fusion_output.get("query_preprocessing"),
        query_routing=query_routing,
        selected_runtime=runtime.label,
        stage_timings=stage_timings,
    )

    stage_timings["response_build_ms"] = _elapsed_ms(stage_start_ms)
    stage_timings["runtime_total_ms"] = _elapsed_ms(runtime_start_ms)

    return {
        "runtime": runtime.label,
        "runtime_obj": runtime,
        "fusion_output": fusion_output,
        "public_response": public_response,
        "ayah_candidates": ayah_candidates,
        "related_ayah_candidates": ayah_related_candidates,
        "passage_candidates": passage_candidates,
        "exact_ayah_meta": exact_ayah_meta,
        "ayah_shortlist_meta": ayah_shortlist_meta,
        "passage_shortlist_meta": passage_shortlist_meta,
        "dynamic_passage_meta": dynamic_passage_meta,
        "stage_timings": stage_timings,
    }


def _runtime_order(route_meta: dict) -> list[CorpusRuntime]:
    runtimes: list[CorpusRuntime] = []
    route = route_meta.get("route")

    if route == ROUTE_UTHMANI_FIRST:
        if verifier_runtime.UTHMANI_RUNTIME:
            runtimes.append(verifier_runtime.UTHMANI_RUNTIME)
        if verifier_runtime.SIMPLE_RUNTIME:
            runtimes.append(verifier_runtime.SIMPLE_RUNTIME)
    else:
        if verifier_runtime.SIMPLE_RUNTIME:
            runtimes.append(verifier_runtime.SIMPLE_RUNTIME)
        if verifier_runtime.UTHMANI_RUNTIME:
            runtimes.append(verifier_runtime.UTHMANI_RUNTIME)

    return runtimes


def _choose_runtime_evaluation(route_meta: dict, evaluations: list[dict]) -> tuple[dict, list[dict]]:
    if not evaluations:
        raise HTTPException(status_code=500, detail="No runtime evaluation was produced.")

    if len(evaluations) == 1:
        return evaluations[0], evaluations

    first = evaluations[0]
    second = evaluations[1]

    if _is_strong_response(first["public_response"]):
        return first, evaluations
    if _is_strong_response(second["public_response"]):
        return second, evaluations

    if _response_strength(second["public_response"]) > _response_strength(first["public_response"]):
        return second, evaluations
    return first, evaluations


def verify_quran_text(text: str, *, debug: bool = False, client_ip: str | None = None) -> dict[str, Any]:
    request_start_ms = _now_ms()
    if verifier_runtime.SIMPLE_RUNTIME is None:
        raise HTTPException(status_code=500, detail="Simple Quran runtime is not loaded.")

    raw_query = text.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")

    stage_start_ms = _now_ms()
    matching_query, preprocessing_meta = sanitize_quran_text_for_matching_with_meta(raw_query)
    preprocessing_ms = _elapsed_ms(stage_start_ms)
    if not matching_query:
        raise HTTPException(status_code=400, detail="Input text cannot be empty after sanitation.")

    stage_start_ms = _now_ms()
    query_assessment = assess_verifier_query(raw_query)
    assessment_ms = _elapsed_ms(stage_start_ms)

    if query_assessment.get("mode") != "verify_like":
        # Important exception:
        # allow genuine single-word / ultra-short exact ayah hits to proceed.
        exact_ayah_override = _has_any_runtime_exact_ayah_signal(matching_query)

        if not exact_ayah_override:
            preferred_lane = "ask_engine" if query_assessment.get("mode") == "ask_like" else "none"
            public_response = _build_non_retrieval_response(
                raw_query,
                preferred_lane=preferred_lane,
                boundary_note=query_assessment.get("boundary_note") or "Input is not suitable for reliable verification.",
                debug_payload=(
                    {
                        "decision_rule": query_assessment.get("reason"),
                        "rationale": query_assessment.get("boundary_note"),
                        "query_preprocessing": preprocessing_meta,
                        "stage_timings": {
                            "preprocessing_ms": preprocessing_ms,
                            "assessment_ms": assessment_ms,
                            "request_total_ms": _elapsed_ms(request_start_ms),
                        },
                    }
                    if debug
                    else None
                ),
            )
            return public_response

    stage_start_ms = _now_ms()
    query_route = detect_quran_query_route(raw_query)
    routing_ms = _elapsed_ms(stage_start_ms)

    evaluations: list[dict] = []
    fallback_trigger_reason = "single_runtime_only"
    for runtime in _runtime_order(query_route):
        evaluation = _evaluate_runtime(
            runtime,
            raw_query=raw_query,
            matching_query=matching_query,
            debug=debug,
            query_preprocessing=preprocessing_meta,
            query_routing=query_route,
        )
        evaluations.append(evaluation)
        fallback_trigger_reason = _fallback_trigger_reason(evaluation)
        if _should_stop_after_runtime(query_route, evaluation):
            break

    selected_evaluation, evaluations = _choose_runtime_evaluation(query_route, evaluations)
    fusion_output = selected_evaluation["fusion_output"]
    preferred_result = fusion_output.get("preferred_result") or {}
    collection_start_ms = _now_ms()
    exact_matches, strong_matches, collection_debug = build_lane_match_collections(
        matching_query,
        preferred_lane=fusion_output.get("preferred_lane", "none"),
        runtime=selected_evaluation["runtime_obj"],
        ayah_candidates=selected_evaluation.get("ayah_candidates") or [],
        passage_candidates=selected_evaluation.get("passage_candidates") or [],
        english_translation_map=verifier_runtime.ENGLISH_TRANSLATION_MAP,
        matching_corpus=selected_evaluation["runtime"],
        best_match=preferred_result.get("best_match"),
        related_ayah_candidates=selected_evaluation.get("related_ayah_candidates"),
        return_debug_meta=True,
    )
    collection_ms = _elapsed_ms(collection_start_ms)
    stage_start_ms = _now_ms()
    public_response = compact_result_for_api(
        fusion_output,
        debug=debug,
        english_translation_map=verifier_runtime.ENGLISH_TRANSLATION_MAP,
        query_preprocessing=fusion_output.get("query_preprocessing"),
        query_routing={**query_route, "fallback_trigger_reason": fallback_trigger_reason},
        selected_runtime=selected_evaluation["runtime"],
        runtime_evaluations=[
            {
                "runtime": ev["runtime"],
                "preferred_lane": ev["public_response"].get("preferred_lane"),
                "match_status": ev["public_response"].get("match_status"),
                "confidence": ev["public_response"].get("confidence"),
                "best_citation": ((ev["public_response"].get("best_match") or {}).get("citation")),
                "stage_timings": ev.get("stage_timings") or {},
            }
            for ev in evaluations
        ],
        stage_timings={
            "routing_ms": routing_ms,
            "preprocessing_ms": preprocessing_ms,
            "match_collection_ms": collection_ms,
            **{
                f"match_collection_{key}": value
                for key, value in ((collection_debug or {}).get("stage_timings") or {}).items()
            },
            "request_total_ms": _elapsed_ms(request_start_ms),
        },
        exact_matches=exact_matches,
        strong_matches=strong_matches,
        collection_debug=collection_debug,
    )

    request_id = str(uuid4())
    best_match = public_response.get("best_match") or {}
    also_related = public_response.get("also_related") or []
    analytics = fusion_output.get("analytics", {})

    append_jsonl_log(
        {
            "request_id": request_id,
            "service": "verify_quran",
            "client_ip": client_ip,
            "query": raw_query,
            "query_char_count": len(raw_query),
            "query_sanitized_for_matching": matching_query,
            "query_was_sanitized": preprocessing_meta.get("was_sanitized", False),
            "query_token_count": fusion_output.get("query_token_count"),
            "query_route": query_route.get("route"),
            "query_route_score": query_route.get("uthmani_score"),
            "query_route_indicators": query_route.get("indicators"),
            "query_route_strong_score": query_route.get("strong_score"),
            "query_route_weak_score": query_route.get("weak_score"),
            "selected_runtime": selected_evaluation["runtime"],
            "fallback_trigger_reason": fallback_trigger_reason,
            "routing_ms": routing_ms,
            "preprocessing_ms": preprocessing_ms,
            "request_total_ms": _elapsed_ms(request_start_ms),
            "preferred_lane": public_response.get("preferred_lane"),
            "decision_rule": fusion_output.get("decision_rule"),
            "rationale": fusion_output.get("rationale"),
            "match_status": public_response.get("match_status"),
            "confidence": public_response.get("confidence"),
            "preferred_citation": best_match.get("citation"),
            "preferred_canonical_source_id": best_match.get("canonical_source_id"),
            "preferred_has_english_translation": bool(best_match.get("english_translation")),
            "related_citations": [r.get("citation") for r in also_related if r.get("citation")],
            "ayah_status": (fusion_output.get("ayah_result") or {}).get("match_status"),
            "ayah_confidence": (fusion_output.get("ayah_result") or {}).get("confidence"),
            "ayah_citation": analytics.get("ayah_citation"),
            "ayah_score": analytics.get("ayah_score"),
            "ayah_status_rank": analytics.get("ayah_status_rank"),
            "passage_status": (fusion_output.get("passage_result") or {}).get("match_status"),
            "passage_confidence": (fusion_output.get("passage_result") or {}).get("confidence"),
            "passage_citation": analytics.get("passage_citation"),
            "passage_score": analytics.get("passage_score"),
            "passage_status_rank": analytics.get("passage_status_rank"),
            "passage_window_size": analytics.get("passage_window_size"),
            "passage_spans_multiple": analytics.get("passage_spans_multiple"),
            "score_delta_passage_minus_ayah": analytics.get("score_delta_passage_minus_ayah"),
            "passage_retrieval_engine": analytics.get("passage_retrieval_engine"),
            "runtime_stage_timings": selected_evaluation.get("stage_timings") or {},
            "debug_enabled": debug,
        }
    )

    return public_response
