from collections import Counter, defaultdict
import time
from typing import Any

from rapidfuzz.distance import Levenshtein

from scripts.common.quran_citation_units import get_canonical_unit_rank, get_result_canonical_unit_type
from scripts.common.text_normalization import normalize_arabic_aggressive, normalize_arabic_light, tokenize
from scripts.evaluation.quran_verifier_baseline import determine_match_status
from scripts.common.quran_scoring import compute_candidate_score


STRONG_MATCH_SCORE_MIN = 19.0
STRONG_MATCH_COVERAGE_MIN = 50.0
NEAR_IDENTICAL_AYAH_MAX_GLOBAL_CHAR_DISTANCE = 3
NEAR_IDENTICAL_AYAH_MAX_LOCAL_TOKEN_DISTANCE = 2
NEAR_IDENTICAL_AYAH_MAX_TOKEN_COUNT_DELTA = 1
NEAR_IDENTICAL_AYAH_MIN_TOKEN_LENGTH = 4
ALTERNATIVE_BACKFILL_SCORE_MIN = 19.0
ALTERNATIVE_BACKFILL_COVERAGE_MIN = 65.0
PASSAGE_BACKFILL_SCORE_MIN = 19.0
PASSAGE_BACKFILL_COVERAGE_MIN = 65.0
CROSS_LANE_AYAH_BACKFILL_SCORE_MIN = 15.0
CROSS_LANE_AYAH_BACKFILL_COVERAGE_MIN = 50.0
PARALLEL_PASSAGE_FROM_BEST_SCORE_MIN = 19.0
PARALLEL_PASSAGE_FROM_BEST_COVERAGE_MIN = 40.0
PARALLEL_PASSAGE_QUERY_RELAXED_COVERAGE_MIN = 50.0
PARALLEL_PASSAGE_QUERY_RELAXED_MAX_MISSING_QUERY_TOKENS = 4
PARALLEL_PASSAGE_QUERY_RELAXED_MIN_QUERY_TOKENS = 6


def build_exact_groups(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row.get(field) or "").strip()
        if key:
            groups[key].append(row)
    return dict(groups)



def build_passage_rows_by_window_size(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()

    for row in rows:
        citation_key = str(
            row.get("canonical_source_id")
            or row.get("citation_string")
            or row.get("source_id")
            or ""
        )
        if not citation_key or citation_key in seen:
            continue

        window_size = row.get("window_size")
        if window_size is None:
            start_ayah = row.get("start_ayah")
            end_ayah = row.get("end_ayah")
            if start_ayah is None or end_ayah is None:
                continue
            window_size = int(end_ayah) - int(start_ayah) + 1

        seen.add(citation_key)
        grouped[int(window_size)].append(row)

    return dict(grouped)



def build_unique_exact_map(
    exact_groups: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, Any] | None]:
    exact_map: dict[str, dict[str, Any] | None] = {}
    for key, rows in exact_groups.items():
        if not rows:
            continue
        exact_map[key] = rows[0] if len(rows) == 1 else None
    return exact_map



def _normalized_needles(query: str) -> tuple[str, str]:
    return normalize_arabic_light(query), normalize_arabic_aggressive(query)



def _missing_query_token_count(query_tokens: list[str], candidate_tokens: list[str]) -> int:
    if not query_tokens:
        return 0
    query_counter = Counter(query_tokens)
    candidate_counter = Counter(candidate_tokens)
    missing_counter = query_counter - candidate_counter
    return int(sum(missing_counter.values()))



def _candidate_is_relaxed_parallel_from_query(
    query: str,
    candidate: dict[str, Any],
) -> bool:
    row = candidate.get("row") or {}
    query_light = normalize_arabic_light(query)
    query_aggressive = normalize_arabic_aggressive(query)
    query_light_tokens = tokenize(query_light)
    query_aggressive_tokens = tokenize(query_aggressive)

    if len(query_light_tokens) < PARALLEL_PASSAGE_QUERY_RELAXED_MIN_QUERY_TOKENS:
        return False

    candidate_light_tokens = tokenize(row.get("text_normalized_light") or "")
    candidate_aggressive_tokens = tokenize(row.get("text_normalized_aggressive") or "")

    missing_light = _missing_query_token_count(query_light_tokens, candidate_light_tokens)
    missing_aggressive = _missing_query_token_count(query_aggressive_tokens, candidate_aggressive_tokens)
    missing_query_tokens = min(missing_light, missing_aggressive)

    if missing_query_tokens > PARALLEL_PASSAGE_QUERY_RELAXED_MAX_MISSING_QUERY_TOKENS:
        return False

    # Important: this is a projection-only rescue rule, not normal verifier admission.
    # Do not reuse determine_match_status(...) here because the whole point of this
    # path is to allow a strong cross-surah parallel even when the winning passage
    # became more specific by one differentiating token.
    return float(candidate.get("token_coverage") or 0.0) >= PARALLEL_PASSAGE_QUERY_RELAXED_COVERAGE_MIN



def _candidate_citation_key(item: dict[str, Any]) -> str:
    return str(
        item.get("canonical_source_id")
        or item.get("citation")
        or item.get("source_id")
        or ""
    )



def _candidate_row_citation_key(candidate: dict[str, Any]) -> str:
    row = candidate.get("row") or {}
    return str(
        row.get("canonical_source_id")
        or row.get("citation_string")
        or row.get("source_id")
        or ""
    )

def _ayah_citation_tuple(item: dict[str, Any]) -> tuple[int, int] | None:
    surah_no = item.get("surah_no")
    ayah_no = item.get("ayah_no")
    if surah_no is None or ayah_no is None:
        return None
    return int(surah_no), int(ayah_no)

def _with_match_kind(item: dict[str, Any], match_kind: str) -> dict[str, Any]:
    item["match_kind"] = match_kind
    return item


def _passage_component_ayah_keys(item: dict[str, Any]) -> set[tuple[int, int]]:
    surah_no = item.get("surah_no")
    start_ayah = item.get("start_ayah")
    end_ayah = item.get("end_ayah")
    if surah_no is None or start_ayah is None or end_ayah is None:
        return set()

    surah_no_i = int(surah_no)
    start_i = int(start_ayah)
    end_i = int(end_ayah)
    return {(surah_no_i, ayah_no) for ayah_no in range(start_i, end_i + 1)}

def _passage_span_tuple(item: dict[str, Any]) -> tuple[int, int, int] | None:
    surah_no = item.get("surah_no")
    start_ayah = item.get("start_ayah")
    end_ayah = item.get("end_ayah")
    if surah_no is None or start_ayah is None or end_ayah is None:
        return None
    return int(surah_no), int(start_ayah), int(end_ayah)


def _candidate_passage_span_tuple(candidate: dict[str, Any]) -> tuple[int, int, int] | None:
    row = candidate.get("row") or {}
    surah_no = row.get("surah_no")
    start_ayah = row.get("start_ayah")
    end_ayah = row.get("end_ayah")
    if surah_no is None or start_ayah is None or end_ayah is None:
        return None
    return int(surah_no), int(start_ayah), int(end_ayah)


def _span_contains(a: tuple[int, int, int], b: tuple[int, int, int]) -> bool:
    a_surah, a_start, a_end = a
    b_surah, b_start, b_end = b
    return a_surah == b_surah and a_start <= b_start and a_end >= b_end

def _spans_overlap(a: tuple[int, int, int], b: tuple[int, int, int]) -> bool:
    a_surah, a_start, a_end = a
    b_surah, b_start, b_end = b
    if a_surah != b_surah:
        return False
    return not (a_end < b_start or b_end < a_start)


def _should_suppress_passage_overlap(
    candidate_span: tuple[int, int, int] | None,
    anchor_spans: list[tuple[int, int, int]],
) -> bool:
    if candidate_span is None:
        return False
    for anchor_span in anchor_spans:
        if _spans_overlap(candidate_span, anchor_span):
            return True
    return False


def _should_suppress_passage_wrapper(
    candidate_span: tuple[int, int, int] | None,
    anchor_spans: list[tuple[int, int, int]],
) -> bool:
    if candidate_span is None:
        return False
    for anchor_span in anchor_spans:
        if _span_contains(candidate_span, anchor_span) or _span_contains(anchor_span, candidate_span):
            return True
    return False


def _collect_anchor_spans(items: list[dict[str, Any]] | None) -> list[tuple[int, int, int]]:
    spans: list[tuple[int, int, int]] = []
    for item in items or []:
        span = _passage_span_tuple(item)
        if span is not None:
            spans.append(span)
    return spans


def _passage_candidate_survives_suppression(
    candidate_span: tuple[int, int, int] | None,
    *,
    anchor_spans: list[tuple[int, int, int]],
    accepted_spans: list[tuple[int, int, int]],
) -> bool:
    if _should_suppress_passage_wrapper(candidate_span, anchor_spans):
        return False
    if _should_suppress_passage_overlap(candidate_span, anchor_spans):
        return False
    if _should_suppress_passage_wrapper(candidate_span, accepted_spans):
        return False
    if _should_suppress_passage_overlap(candidate_span, accepted_spans):
        return False
    return True



def _dedupe_by_citation(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = _candidate_citation_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped



def _lookup_group_rows(
    query: str,
    *,
    exact_light_groups: dict[str, list[dict[str, Any]]],
    exact_aggressive_groups: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    light_query, aggressive_query = _normalized_needles(query)
    merged: list[dict[str, Any]] = []
    merged.extend(exact_light_groups.get(light_query, []))
    merged.extend(exact_aggressive_groups.get(aggressive_query, []))

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for row in merged:
        key = str(row.get("canonical_source_id") or row.get("citation_string") or row.get("source_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows



def _attach_translation(item: dict[str, Any], english_translation_map: dict[tuple[int, int], dict] | None) -> dict[str, Any]:
    if not english_translation_map:
        return item

    enriched = dict(item)
    source_type = enriched.get("source_type")

    if source_type == "quran" and enriched.get("ayah_no") is not None:
        key = (int(enriched["surah_no"]), int(enriched["ayah_no"]))
        translation = english_translation_map.get(key)
        if translation:
            enriched["english_translation"] = {
                "translation_name": translation.get("translation_name"),
                "text": translation.get("text"),
                "ayah_keys": [f"{translation['surah_no']}:{translation['ayah_no']}"]
            }
        return enriched

    start_ayah = enriched.get("start_ayah")
    end_ayah = enriched.get("end_ayah")
    surah_no = enriched.get("surah_no")
    if source_type == "quran_passage" and start_ayah is not None and end_ayah is not None and surah_no is not None:
        components = []
        texts = []
        translation_name = ""
        for ayah_no in range(int(start_ayah), int(end_ayah) + 1):
            translation = english_translation_map.get((int(surah_no), ayah_no))
            if not translation:
                continue
            if not translation_name:
                translation_name = translation.get("translation_name") or ""
            components.append(
                {
                    "surah_no": int(surah_no),
                    "ayah_no": ayah_no,
                    "text": translation.get("text"),
                }
            )
            texts.append(translation.get("text") or "")

        if components:
            enriched["english_translation"] = {
                "translation_name": translation_name,
                "text": " ".join([t for t in texts if t]).strip(),
                "ayah_keys": [f"{int(surah_no)}:{item['ayah_no']}" for item in components],
                "components": components,
            }
    return enriched



def _format_ayah_exact_row(
    row: dict[str, Any],
    *,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
) -> dict[str, Any]:
    item = {
        "source_type": row.get("source_type"),
        "source_id": row.get("source_id"),
        "citation": row.get("citation_string"),
        "canonical_source_id": row.get("canonical_source_id"),
        "surah_no": int(row.get("surah_no")),
        "ayah_no": int(row.get("ayah_no")),
        "surah_name_ar": row.get("surah_name_ar"),
        "text_display": row.get("text_display"),
        "match_kind": "full_exact_ayah",
        "matching_corpus": matching_corpus,
        "canonical_unit_type": "single_ayah",
        "canonical_unit_rank": get_canonical_unit_rank("single_ayah"),
    }
    return _attach_translation(item, english_translation_map)



def _format_passage_exact_row(
    row: dict[str, Any],
    *,
    matching_corpus: str,
    retrieval_engine: str | None = None,
    score: float | None = None,
    token_coverage: float | None = None,
    english_translation_map: dict[tuple[int, int], dict] | None = None,
) -> dict[str, Any]:
    item = {
        "source_type": row.get("source_type"),
        "source_id": row.get("source_id"),
        "citation": row.get("citation_string"),
        "canonical_source_id": row.get("canonical_source_id"),
        "surah_no": int(row.get("surah_no")),
        "start_ayah": int(row.get("start_ayah")),
        "end_ayah": int(row.get("end_ayah")),
        "window_size": int(row.get("window_size") or (int(row.get("end_ayah")) - int(row.get("start_ayah")) + 1)),
        "surah_name_ar": row.get("surah_name_ar"),
        "text_display": row.get("text_display"),
        "retrieval_engine": retrieval_engine or row.get("retrieval_engine") or "static_exact_window",
        "match_kind": "full_exact_passage",
        "matching_corpus": matching_corpus,
    }
    if score is not None:
        item["score"] = float(score)
    if token_coverage is not None:
        item["token_coverage"] = float(token_coverage)
    unit_type = get_result_canonical_unit_type({"best_match": item}, lane="passage")
    item["canonical_unit_type"] = unit_type
    item["canonical_unit_rank"] = get_canonical_unit_rank(unit_type)
    return _attach_translation(item, english_translation_map)



def _format_ayah_candidate(
    candidate: dict[str, Any],
    *,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
) -> dict[str, Any]:
    row = candidate.get("row") or {}
    item = {
        "source_type": row.get("source_type"),
        "source_id": row.get("source_id"),
        "citation": row.get("citation_string"),
        "canonical_source_id": row.get("canonical_source_id"),
        "surah_no": int(row.get("surah_no")),
        "ayah_no": int(row.get("ayah_no")),
        "surah_name_ar": row.get("surah_name_ar"),
        "text_display": row.get("text_display"),
        "score": float(candidate.get("score") or 0.0),
        "token_coverage": float(candidate.get("token_coverage") or 0.0),
        "matching_corpus": matching_corpus,
        "canonical_unit_type": "single_ayah",
        "canonical_unit_rank": get_canonical_unit_rank("single_ayah"),
    }
    return _attach_translation(item, english_translation_map)



def _format_ayah_candidate_with_kind(
    candidate: dict[str, Any],
    *,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    match_kind: str,
) -> dict[str, Any]:
    return _with_match_kind(
        _format_ayah_candidate(
            candidate,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        ),
        match_kind,
    )



def _format_passage_candidate(
    candidate: dict[str, Any],
    *,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
) -> dict[str, Any]:
    row = candidate.get("row") or {}
    item = {
        "source_type": row.get("source_type"),
        "source_id": row.get("source_id"),
        "citation": row.get("citation_string"),
        "canonical_source_id": row.get("canonical_source_id"),
        "surah_no": int(row.get("surah_no")),
        "start_ayah": int(row.get("start_ayah")),
        "end_ayah": int(row.get("end_ayah")),
        "window_size": int(row.get("window_size") or 1),
        "surah_name_ar": row.get("surah_name_ar"),
        "text_display": row.get("text_display"),
        "score": float(candidate.get("score") or 0.0),
        "token_coverage": float(candidate.get("token_coverage") or 0.0),
        "retrieval_engine": candidate.get("retrieval_engine") or row.get("retrieval_engine") or "static_window",
        "matching_corpus": matching_corpus,
    }
    unit_type = get_result_canonical_unit_type({"best_match": item}, lane="passage")
    item["canonical_unit_type"] = unit_type
    item["canonical_unit_rank"] = get_canonical_unit_rank(unit_type)
    return _attach_translation(item, english_translation_map)



def collect_exact_ayah_matches(
    query: str,
    *,
    runtime: Any,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
) -> list[dict[str, Any]]:
    rows = _lookup_group_rows(
        query,
        exact_light_groups=runtime.exact_light_groups,
        exact_aggressive_groups=runtime.exact_aggressive_groups,
    )
    items = [
        _format_ayah_exact_row(
            row,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )
        for row in rows
    ]
    items = _dedupe_by_citation(items)
    return sorted(items, key=lambda x: (int(x.get("surah_no") or 0), int(x.get("ayah_no") or 0)))



def collect_exact_passage_matches(
    query: str,
    *,
    runtime: Any,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    static_rows = _lookup_group_rows(
        query,
        exact_light_groups=runtime.passage_exact_light_groups,
        exact_aggressive_groups=runtime.passage_exact_aggressive_groups,
    )
    for row in static_rows:
        items.append(
            _format_passage_exact_row(
                row,
                matching_corpus=matching_corpus,
                retrieval_engine="static_exact_window",
                english_translation_map=english_translation_map,
            )
        )

    if getattr(runtime, "surah_span_index", None) is not None:
        dynamic_candidates, _ = runtime.surah_span_index.find_all_exact_span_lookup_candidates(
            query,
            min_window_size=2,
        )
        for candidate in dynamic_candidates:
            row = candidate.get("row") or {}
            items.append(
                _format_passage_exact_row(
                    row,
                    matching_corpus=matching_corpus,
                    retrieval_engine=candidate.get("retrieval_engine") or "surah_span_exact",
                    score=candidate.get("score"),
                    token_coverage=candidate.get("token_coverage"),
                    english_translation_map=english_translation_map,
                )
            )

    filtered: list[dict[str, Any]] = []
    for item in _dedupe_by_citation(items):
        if item.get("canonical_unit_type") in {"contiguous_span", "static_window"}:
            filtered.append(item)

    return sorted(
        filtered,
        key=lambda x: (
            -int(x.get("canonical_unit_rank") or 0),
            -float(x.get("score") or 0.0),
            int(x.get("surah_no") or 0),
            int(x.get("start_ayah") or 0),
            int(x.get("end_ayah") or 0),
        ),
    )





def _should_skip_parallel_projection_scan(
    query: str,
    best_match: dict[str, Any] | None,
) -> bool:
    if not best_match:
        return True
    query_tokens = tokenize(normalize_arabic_light(query))
    best_match_tokens = tokenize(best_match.get("text_normalized_light") or "")
    best_length_ratio = ((best_match.get("scoring_breakdown") or {}).get("length_ratio") or 1.0)
    return (
        len(query_tokens) >= 20
        or len(best_match_tokens) >= 25
        or float(best_length_ratio) <= 0.35
    )


def collect_parallel_passage_from_index(
    *,
    query: str,
    runtime: Any,
    best_match: dict[str, Any] | None,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    exclude_citations: set[str],
    limit: int = 3,
    anchor_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not best_match:
        return items
    if best_match.get("source_type") != "quran_passage":
        return items
    # Close/partial winners may not carry retrieval_engine on the final best_match
    # object even though passage analytics classify them as static_window. For the
    # indexed neighbor path, source_type + canonical_source_id + window_size are
    # sufficient; do not block on retrieval_engine here.

    best_surah_no = best_match.get("surah_no")
    best_window_size = best_match.get("window_size")
    best_canonical_source_id = str(best_match.get("canonical_source_id") or "")
    if best_surah_no is None or best_window_size is None or not best_canonical_source_id:
        return items

    neighbor_lookup = getattr(runtime, "passage_neighbor_lookup", {}) or {}
    row_lookup = getattr(runtime, "passage_row_lookup", {}) or {}
    neighbor_candidates = list(neighbor_lookup.get((int(best_window_size), best_canonical_source_id), []))
    if not neighbor_candidates:
        return items

    seen = set(exclude_citations)
    anchor_spans = _collect_anchor_spans(anchor_items)
    accepted_spans: list[tuple[int, int, int]] = []

    query_light = normalize_arabic_light(query)
    query_aggressive = normalize_arabic_aggressive(query)
    query_light_tokens = tokenize(query_light)
    query_aggressive_tokens = tokenize(query_aggressive)

    for neighbor in neighbor_candidates:
        canonical_source_id = str(neighbor.get("canonical_source_id") or "")
        if not canonical_source_id:
            continue
        row = row_lookup.get(canonical_source_id)
        if not row:
            continue

        citation_key = str(
            row.get("canonical_source_id")
            or row.get("citation_string")
            or row.get("source_id")
            or ""
        )
        if not citation_key or citation_key in seen:
            continue

        row_surah_no = row.get("surah_no")
        if row_surah_no is None or int(row_surah_no) == int(best_surah_no):
            continue

        row_window_size = row.get("window_size")
        if row_window_size is None:
            start_ayah = row.get("start_ayah")
            end_ayah = row.get("end_ayah")
            if start_ayah is None or end_ayah is None:
                continue
            row_window_size = int(end_ayah) - int(start_ayah) + 1
        if int(row_window_size) != int(best_window_size):
            continue

        synthetic_candidate = compute_candidate_score(
            query_light,
            query_light_tokens,
            row,
            query,
            aggressive_query=query_aggressive,
            aggressive_query_tokens=query_aggressive_tokens,
        )
        if not _candidate_is_relaxed_parallel_from_query(query, synthetic_candidate):
            continue

        formatted = _format_passage_candidate(
            synthetic_candidate,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )
        if formatted.get("canonical_unit_type") not in {"static_window", "contiguous_span"}:
            continue

        candidate_span = _candidate_passage_span_tuple(synthetic_candidate)
        if not _passage_candidate_survives_suppression(
            candidate_span,
            anchor_spans=anchor_spans,
            accepted_spans=accepted_spans,
        ):
            continue

        formatted["match_kind"] = "parallel_passage_from_index"
        items.append(formatted)
        seen.add(citation_key)
        if candidate_span is not None:
            accepted_spans.append(candidate_span)
        if len(items) >= limit:
            break

    return items

def _candidate_is_strong(query: str, candidate: dict[str, Any]) -> bool:
    status = determine_match_status(query, candidate)
    if status not in {"Exact match found", "Close / partial match found"}:
        return False
    score = float(candidate.get("score") or 0.0)
    coverage = float(candidate.get("token_coverage") or 0.0)
    return score >= STRONG_MATCH_SCORE_MIN and coverage >= STRONG_MATCH_COVERAGE_MIN

def _candidate_is_cross_lane_ayah_backfill(candidate: dict[str, Any]) -> bool:
    score = float(candidate.get("score") or 0.0)
    coverage = float(candidate.get("token_coverage") or 0.0)
    return (
        score >= CROSS_LANE_AYAH_BACKFILL_SCORE_MIN
        and coverage >= CROSS_LANE_AYAH_BACKFILL_COVERAGE_MIN
    )

def _candidate_is_passage_backfill(candidate: dict[str, Any]) -> bool:
    score = float(candidate.get("score") or 0.0)
    coverage = float(candidate.get("token_coverage") or 0.0)
    return (
        score >= PASSAGE_BACKFILL_SCORE_MIN
        and coverage >= PASSAGE_BACKFILL_COVERAGE_MIN
    )

def _candidate_is_alternative_backfill(candidate: dict[str, Any]) -> bool:
    score = float(candidate.get("score") or 0.0)
    coverage = float(candidate.get("token_coverage") or 0.0)
    return (
        score >= ALTERNATIVE_BACKFILL_SCORE_MIN
        and coverage >= ALTERNATIVE_BACKFILL_COVERAGE_MIN
    )

def _small_token_edit(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return Levenshtein.distance(a, b) <= NEAR_IDENTICAL_AYAH_MAX_LOCAL_TOKEN_DISTANCE


def _aligned_near_identical_tokens(anchor_tokens: list[str], candidate_tokens: list[str]) -> bool:
    if len(anchor_tokens) < NEAR_IDENTICAL_AYAH_MIN_TOKEN_LENGTH:
        return False

    len_a = len(anchor_tokens)
    len_b = len(candidate_tokens)
    if abs(len_a - len_b) > NEAR_IDENTICAL_AYAH_MAX_TOKEN_COUNT_DELTA:
        return False

    # Case 1: same token count -> allow exactly one tiny token-level mismatch.
    if len_a == len_b:
        mismatch_positions = []
        for i, (a_tok, b_tok) in enumerate(zip(anchor_tokens, candidate_tokens)):
            if a_tok != b_tok:
                mismatch_positions.append((i, a_tok, b_tok))
                if len(mismatch_positions) > 1:
                    return False

        if len(mismatch_positions) != 1:
            return False

        _, a_tok, b_tok = mismatch_positions[0]
        return _small_token_edit(a_tok, b_tok)

    # Case 2: one token inserted/deleted -> all remaining tokens must align exactly.
    # anchor longer by 1
    if len_a == len_b + 1:
        for skip_idx in range(len_a):
            reduced = anchor_tokens[:skip_idx] + anchor_tokens[skip_idx + 1 :]
            if reduced == candidate_tokens:
                return True
        return False

    # candidate longer by 1
    if len_b == len_a + 1:
        for skip_idx in range(len_b):
            reduced = candidate_tokens[:skip_idx] + candidate_tokens[skip_idx + 1 :]
            if reduced == anchor_tokens:
                return True
        return False

    return False


def _is_near_identical_sibling_ayah(
    *,
    best_match: dict[str, Any] | None,
    candidate: dict[str, Any],
    best_match_is_full_exact_ayah: bool,
) -> bool:
    if not best_match or not best_match_is_full_exact_ayah:
        return False
    if (best_match.get("canonical_unit_type") or "single_ayah") != "single_ayah":
        return False

    row = candidate.get("row") or {}
    anchor_text = normalize_arabic_light(best_match.get("text_display") or "")
    candidate_text = normalize_arabic_light(row.get("text_display") or "")

    if not anchor_text or not candidate_text or anchor_text == candidate_text:
        return False

    if Levenshtein.distance(anchor_text, candidate_text) > NEAR_IDENTICAL_AYAH_MAX_GLOBAL_CHAR_DISTANCE:
        return False

    anchor_tokens = tokenize(anchor_text)
    candidate_tokens = tokenize(candidate_text)

    return _aligned_near_identical_tokens(anchor_tokens, candidate_tokens)



def collect_strong_ayah_matches(
    query: str,
    *,
    candidates: list[dict[str, Any]],
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    exclude_citations: set[str],
    limit: int = 3,
    best_match: dict[str, Any] | None = None,
    best_match_is_full_exact_ayah: bool = False,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set(exclude_citations)

    # Pass 1: preserve current strong-match behavior exactly as-is.
    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _candidate_is_strong(query, candidate):
            continue

        items.append(
            _format_ayah_candidate_with_kind(
                candidate,
                english_translation_map=english_translation_map,
                matching_corpus=matching_corpus,
                match_kind="strong",
            )
        )
        seen.add(citation_key)
        if len(items) >= limit:
            break

    if len(items) >= limit:
        return items

    # Pass 2: conservative fallback for near-identical sibling ayahs.
    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _is_near_identical_sibling_ayah(
            best_match=best_match,
            candidate=candidate,
            best_match_is_full_exact_ayah=best_match_is_full_exact_ayah,
        ):
            continue

        items.append(
            _format_ayah_candidate_with_kind(
                candidate,
                english_translation_map=english_translation_map,
                matching_corpus=matching_corpus,
                match_kind="near_identical_sibling_ayah",
            )
        )
        seen.add(citation_key)
        if len(items) >= limit:
            break

    # Pass 3: optional backfill from ayah alternatives / related candidates.
    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _candidate_is_alternative_backfill(candidate):
            continue

        items.append(
            _format_ayah_candidate_with_kind(
                candidate,
                english_translation_map=english_translation_map,
                matching_corpus=matching_corpus,
                match_kind="alternative_backfill",
            )
        )
        seen.add(citation_key)
        if len(items) >= limit:
            break

    return items

def collect_cross_lane_ayah_backfill(
    *,
    candidates: list[dict[str, Any]],
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    exclude_citations: set[str],
    limit: int = 3,
    blocked_ayah_keys: set[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set(exclude_citations)
    blocked_ayah_keys = blocked_ayah_keys or set()

    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _candidate_is_cross_lane_ayah_backfill(candidate):
            continue

        row = candidate.get("row") or {}
        ayah_key = _ayah_citation_tuple(row)
        if ayah_key is not None and ayah_key in blocked_ayah_keys:
            continue

        formatted = _format_ayah_candidate(
            candidate,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )
        formatted["match_kind"] = "cross_lane_ayah_backfill"

        items.append(formatted)
        seen.add(citation_key)

        if len(items) >= limit:
            break

    return items



def collect_strong_passage_matches(
    query: str,
    *,
    candidates: list[dict[str, Any]],
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    exclude_citations: set[str],
    limit: int = 3,
    anchor_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set(exclude_citations)

    anchor_spans = _collect_anchor_spans(anchor_items)

    accepted_strong_spans: list[tuple[int, int, int]] = []

    # Pass 1: keep current strict passage strong-match behavior.
    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _candidate_is_strong(query, candidate):
            continue

        formatted = _format_passage_candidate(
            candidate,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )

        unit_type = formatted.get("canonical_unit_type")
        if unit_type == "heuristic_expansion":
            continue

        candidate_span = _candidate_passage_span_tuple(candidate)

        if not _passage_candidate_survives_suppression(
            candidate_span,
            anchor_spans=anchor_spans,
            accepted_spans=accepted_strong_spans,
        ):
            continue

        items.append(_with_match_kind(formatted, "strong"))
        seen.add(citation_key)

        if candidate_span is not None:
            accepted_strong_spans.append(candidate_span)

        if len(items) >= limit:
            return items

    # Pass 2: passage-only alternative backfill.
    # This fills leftover slots without weakening main strong-match semantics.
    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _candidate_is_passage_backfill(candidate):
            continue

        formatted = _format_passage_candidate(
            candidate,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )

        unit_type = formatted.get("canonical_unit_type")
        if unit_type not in {"static_window", "contiguous_span"}:
            continue

        candidate_span = _candidate_passage_span_tuple(candidate)

        if not _passage_candidate_survives_suppression(
            candidate_span,
            anchor_spans=anchor_spans,
            accepted_spans=accepted_strong_spans,
        ):
            continue

        formatted["match_kind"] = "alternative_backfill_passage"
        items.append(formatted)
        seen.add(citation_key)

        if candidate_span is not None:
            accepted_strong_spans.append(candidate_span)

        if len(items) >= limit:
            break

    return items
    
def collect_parallel_passage_from_best_match(
    *,
    query: str,
    runtime: Any,
    best_match: dict[str, Any] | None,
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    exclude_citations: set[str],
    limit: int = 1,
    anchor_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not best_match:
        return items
    if best_match.get("source_type") != "quran_passage":
        return items
    best_match_engine = str(best_match.get("retrieval_engine") or "")
    if best_match_engine and best_match_engine not in {"static_exact_window", "static_window"}:
        return items

    best_text = best_match.get("text_display") or ""
    best_surah_no = best_match.get("surah_no")
    best_window_size = best_match.get("window_size")

    if not best_text or best_surah_no is None or best_window_size is None:
        return items

    best_light = normalize_arabic_light(best_text)
    best_aggressive = normalize_arabic_aggressive(best_text)
    best_light_tokens = tokenize(best_light)
    best_aggressive_tokens = tokenize(best_aggressive)

    query_light = normalize_arabic_light(query)
    query_aggressive = normalize_arabic_aggressive(query)
    query_light_tokens = tokenize(query_light)
    query_aggressive_tokens = tokenize(query_aggressive)

    seen = set(exclude_citations)

    anchor_spans = _collect_anchor_spans(anchor_items)

    accepted_spans: list[tuple[int, int, int]] = []

    candidate_rows = list(
        getattr(runtime, "passage_rows_by_window_size", {}).get(int(best_window_size), [])
    )

    for row in candidate_rows:
        citation_key = str(
            row.get("canonical_source_id")
            or row.get("citation_string")
            or row.get("source_id")
            or ""
        )
        if not citation_key or citation_key in seen:
            continue

        row_surah_no = row.get("surah_no")
        if row_surah_no is None or int(row_surah_no) == int(best_surah_no):
            continue

        row_window_size = row.get("window_size")
        if row_window_size is None:
            start_ayah = row.get("start_ayah")
            end_ayah = row.get("end_ayah")
            if start_ayah is None or end_ayah is None:
                continue
            row_window_size = int(end_ayah) - int(start_ayah) + 1

        if int(row_window_size) != int(best_window_size):
            continue

        synthetic_candidate = compute_candidate_score(
            best_light,
            best_light_tokens,
            row,
            best_text,
            aggressive_query=best_aggressive,
            aggressive_query_tokens=best_aggressive_tokens,
        )

        match_kind = "parallel_passage_from_best_match"
        if (
            float(synthetic_candidate.get("score") or 0.0) < PARALLEL_PASSAGE_FROM_BEST_SCORE_MIN
            or float(synthetic_candidate.get("token_coverage") or 0.0) < PARALLEL_PASSAGE_FROM_BEST_COVERAGE_MIN
        ):
            synthetic_candidate = compute_candidate_score(
                query_light,
                query_light_tokens,
                row,
                query,
                aggressive_query=query_aggressive,
                aggressive_query_tokens=query_aggressive_tokens,
            )
            if not _candidate_is_relaxed_parallel_from_query(query, synthetic_candidate):
                continue
            match_kind = "parallel_passage_from_query_relaxed"

        formatted = _format_passage_candidate(
            synthetic_candidate,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )

        if formatted.get("canonical_unit_type") not in {"static_window", "contiguous_span"}:
            continue

        candidate_span = _candidate_passage_span_tuple(synthetic_candidate)

        if not _passage_candidate_survives_suppression(
            candidate_span,
            anchor_spans=anchor_spans,
            accepted_spans=accepted_spans,
        ):
            continue

        formatted["match_kind"] = match_kind
        items.append(formatted)
        seen.add(citation_key)

        if candidate_span is not None:
            accepted_spans.append(candidate_span)

        if len(items) >= limit:
            break

    return items


def build_lane_match_collections(
    query: str,
    *,
    preferred_lane: str,
    runtime: Any,
    ayah_candidates: list[dict[str, Any]],
    passage_candidates: list[dict[str, Any]],
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    best_match: dict[str, Any] | None,
    related_ayah_candidates: list[dict[str, Any]] | None = None,
    return_debug_meta: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    collection_start = time.perf_counter()
    exact_matches: list[dict[str, Any]] = []
    strong_matches: list[dict[str, Any]] = []
    collection_debug: dict[str, Any] = {
        "preferred_lane": preferred_lane,
        "stage_timings": {},
        "counts": {},
    }

    best_citation_key = _candidate_citation_key(best_match or {})
    exclude_citations = {best_citation_key} if best_citation_key else set()

    if preferred_lane == "ayah":
        stage_start = time.perf_counter()
        raw_exact_matches = collect_exact_ayah_matches(
            query,
            runtime=runtime,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )

        collection_debug["stage_timings"]["exact_matches_ms"] = round((time.perf_counter() - stage_start) * 1000.0, 3)

        best_match_is_full_exact_ayah = any(
            _candidate_citation_key(item) == best_citation_key
            for item in raw_exact_matches
        )

        exact_matches = raw_exact_matches
        if best_citation_key:
            exact_matches = [
                item
                for item in raw_exact_matches
                if _candidate_citation_key(item) != best_citation_key
            ]

        exclude_citations.update(
            _candidate_citation_key(item)
            for item in exact_matches
            if _candidate_citation_key(item)
        )

        strong_source_candidates = (
            related_ayah_candidates
            if related_ayah_candidates is not None
            else ayah_candidates
        )

        stage_start = time.perf_counter()
        strong_matches = collect_strong_ayah_matches(
            query,
            candidates=strong_source_candidates,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
            exclude_citations=exclude_citations,
            limit=3,
            best_match=best_match,
            best_match_is_full_exact_ayah=best_match_is_full_exact_ayah,
        )
        collection_debug["stage_timings"]["strong_matches_ms"] = round((time.perf_counter() - stage_start) * 1000.0, 3)
        collection_debug["counts"] = {
            "exact_matches": len(exact_matches),
            "strong_matches": len(strong_matches),
        }
        collection_debug["stage_timings"]["collection_total_ms"] = round((time.perf_counter() - collection_start) * 1000.0, 3)
        if return_debug_meta:
            return exact_matches, strong_matches, collection_debug
        return exact_matches, strong_matches

    if preferred_lane == "passage":
        stage_start = time.perf_counter()
        exact_matches = collect_exact_passage_matches(
            query,
            runtime=runtime,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )

        collection_debug["stage_timings"]["exact_matches_ms"] = round((time.perf_counter() - stage_start) * 1000.0, 3)

        # Do not repeat the current best_match inside exact_matches.
        if best_citation_key:
            exact_matches = [
                item
                for item in exact_matches
                if _candidate_citation_key(item) != best_citation_key
            ]

        exclude_citations.update(
            _candidate_citation_key(item)
            for item in exact_matches
            if _candidate_citation_key(item)
        )

        anchor_items: list[dict[str, Any]] = []
        if best_match:
            anchor_items.append(best_match)
        anchor_items.extend(exact_matches)

        stage_start = time.perf_counter()
        strong_matches = collect_strong_passage_matches(
            query,
            candidates=passage_candidates,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
            exclude_citations=exclude_citations,
            limit=3,
            anchor_items=anchor_items,
        )

        collection_debug["stage_timings"]["strong_matches_ms"] = round((time.perf_counter() - stage_start) * 1000.0, 3)

        # Projection-only supplement for passage cases that ended up with no usable
        # strong passage matches after wrapper suppression.
        # Prefer precomputed indexed neighbors when available; only fall back to
        # the expensive best-match scan for short winners.
        if (
            not strong_matches
            and best_match
            and best_match.get("source_type") == "quran_passage"
        ):
            parallel_exclude = set(exclude_citations)
            parallel_anchor_items = list(anchor_items)

            if getattr(runtime, "passage_neighbor_lookup", None):
                stage_start = time.perf_counter()
                parallel_matches = collect_parallel_passage_from_index(
                    query=query,
                    runtime=runtime,
                    best_match=best_match,
                    english_translation_map=english_translation_map,
                    matching_corpus=matching_corpus,
                    exclude_citations=parallel_exclude,
                    limit=3,
                    anchor_items=parallel_anchor_items,
                )
                collection_debug["stage_timings"]["parallel_passage_from_index_ms"] = round(
                    (time.perf_counter() - stage_start) * 1000.0, 3
                )
                collection_debug["counts"]["parallel_passage_from_index"] = len(parallel_matches)
                strong_matches.extend(parallel_matches)
            elif not _should_skip_parallel_projection_scan(query, best_match):
                stage_start = time.perf_counter()
                parallel_matches = collect_parallel_passage_from_best_match(
                    query=query,
                    runtime=runtime,
                    best_match=best_match,
                    english_translation_map=english_translation_map,
                    matching_corpus=matching_corpus,
                    exclude_citations=parallel_exclude,
                    limit=3,
                    anchor_items=parallel_anchor_items,
                )

                collection_debug["stage_timings"]["parallel_passage_from_best_match_ms"] = round(
                    (time.perf_counter() - stage_start) * 1000.0, 3
                )
                collection_debug["counts"]["parallel_passage_from_best_match"] = len(parallel_matches)
                strong_matches.extend(parallel_matches)
            else:
                collection_debug["counts"]["parallel_passage_from_best_match_skipped"] = 1

        # Cross-lane fallback:
        # if passage strong matches are empty, backfill from ayah candidates,
        # but never include ayahs that are component ayahs of the winning passage.
        if not strong_matches:
            cross_lane_source_candidates = (
                related_ayah_candidates
                if related_ayah_candidates is not None
                else ayah_candidates
            )

            cross_lane_exclude = set(exclude_citations)
            cross_lane_exclude.update(
                _candidate_citation_key(item)
                for item in strong_matches
                if _candidate_citation_key(item)
            )

            blocked_ayah_keys: set[tuple[int, int]] = set()
            if best_match:
                blocked_ayah_keys.update(_passage_component_ayah_keys(best_match))
            for item in exact_matches:
                blocked_ayah_keys.update(_passage_component_ayah_keys(item))

            stage_start = time.perf_counter()
            strong_matches = collect_cross_lane_ayah_backfill(
                candidates=cross_lane_source_candidates,
                english_translation_map=english_translation_map,
                matching_corpus=matching_corpus,
                exclude_citations=cross_lane_exclude,
                limit=3,
                blocked_ayah_keys=blocked_ayah_keys,
            )

            collection_debug["stage_timings"]["cross_lane_ayah_backfill_ms"] = round((time.perf_counter() - stage_start) * 1000.0, 3)

        collection_debug["counts"].update({
            "exact_matches": len(exact_matches),
            "strong_matches": len(strong_matches),
        })
        collection_debug["stage_timings"]["collection_total_ms"] = round((time.perf_counter() - collection_start) * 1000.0, 3)
        if return_debug_meta:
            return exact_matches, strong_matches, collection_debug
        return exact_matches, strong_matches

    collection_debug["stage_timings"]["collection_total_ms"] = round((time.perf_counter() - collection_start) * 1000.0, 3)
    if return_debug_meta:
        return [], [], collection_debug
    return [], []
