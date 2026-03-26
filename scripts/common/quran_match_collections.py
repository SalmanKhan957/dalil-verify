from __future__ import annotations

from collections import defaultdict
from typing import Any

from scripts.common.quran_citation_units import get_canonical_unit_rank, get_result_canonical_unit_type
from scripts.common.text_normalization import normalize_arabic_aggressive, normalize_arabic_light
from scripts.evaluation.quran_verifier_baseline import determine_match_status


STRONG_MATCH_SCORE_MIN = 50.0
STRONG_MATCH_COVERAGE_MIN = 70.0


def build_exact_groups(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row.get(field) or "").strip()
        if key:
            groups[key].append(row)
    return dict(groups)



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
        "match_status": determine_match_status(candidate.get("original_query") or "", candidate) if candidate.get("original_query") else None,
        "matching_corpus": matching_corpus,
        "canonical_unit_type": "single_ayah",
        "canonical_unit_rank": get_canonical_unit_rank("single_ayah"),
    }
    return _attach_translation(item, english_translation_map)



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



def _candidate_is_strong(query: str, candidate: dict[str, Any]) -> bool:
    status = determine_match_status(query, candidate)
    if status not in {"Exact match found", "Close / partial match found"}:
        return False
    score = float(candidate.get("score") or 0.0)
    coverage = float(candidate.get("token_coverage") or 0.0)
    return score >= STRONG_MATCH_SCORE_MIN and coverage >= STRONG_MATCH_COVERAGE_MIN



def collect_strong_ayah_matches(
    query: str,
    *,
    candidates: list[dict[str, Any]],
    english_translation_map: dict[tuple[int, int], dict] | None,
    matching_corpus: str,
    exclude_citations: set[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set(exclude_citations)
    for candidate in candidates:
        citation_key = _candidate_row_citation_key(candidate)
        if not citation_key or citation_key in seen:
            continue
        if not _candidate_is_strong(query, candidate):
            continue
        row = candidate.get("row") or {}
        formatted = {
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
        items.append(_attach_translation(formatted, english_translation_map))
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
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set(exclude_citations)
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
        if formatted.get("canonical_unit_type") == "heuristic_expansion":
            continue
        items.append(formatted)
        seen.add(citation_key)
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact_matches: list[dict[str, Any]] = []
    strong_matches: list[dict[str, Any]] = []

    best_citation_key = _candidate_citation_key(best_match or {})
    exclude_citations = {best_citation_key} if best_citation_key else set()

    if preferred_lane == "ayah":
        exact_matches = collect_exact_ayah_matches(
            query,
            runtime=runtime,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )
        exclude_citations.update(_candidate_citation_key(item) for item in exact_matches if _candidate_citation_key(item))
        strong_matches = collect_strong_ayah_matches(
            query,
            candidates=ayah_candidates,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
            exclude_citations=exclude_citations,
            limit=3,
        )
        return exact_matches, strong_matches

    if preferred_lane == "passage":
        exact_matches = collect_exact_passage_matches(
            query,
            runtime=runtime,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
        )
        exclude_citations.update(_candidate_citation_key(item) for item in exact_matches if _candidate_citation_key(item))
        strong_matches = collect_strong_passage_matches(
            query,
            candidates=passage_candidates,
            english_translation_map=english_translation_map,
            matching_corpus=matching_corpus,
            exclude_citations=exclude_citations,
            limit=3,
        )
        return exact_matches, strong_matches

    return [], []
