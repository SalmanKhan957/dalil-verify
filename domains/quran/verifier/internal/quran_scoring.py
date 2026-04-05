from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from shared.utils.arabic_text import (
    normalize_arabic_aggressive,
    tokenize,
)


def compute_candidate_score(
    normalized_query: str,
    query_tokens: list[str],
    row: dict[str, Any],
    original_query: str,
    *,
    aggressive_query: str | None = None,
    aggressive_query_tokens: list[str] | None = None,
) -> dict[str, Any]:
    light_query = normalized_query
    aggressive_query = aggressive_query if aggressive_query is not None else normalize_arabic_aggressive(original_query)

    text_display = row["text_display"]
    text_light = row["text_normalized_light"]
    text_aggressive = row["text_normalized_aggressive"]

    query_len = max(len(light_query), 1)
    text_len = max(len(text_light), 1)
    length_ratio = min(query_len, text_len) / max(query_len, text_len)

    light_query_tokens = query_tokens
    aggressive_query_tokens = aggressive_query_tokens if aggressive_query_tokens is not None else tokenize(aggressive_query)

    light_query_token_set = set(light_query_tokens)
    aggressive_query_token_set = set(aggressive_query_tokens)

    light_text_token_set = set(row["tokens_light"])
    aggressive_text_token_set = set(row["tokens_aggressive"])

    token_overlap_count_light = len(light_query_token_set.intersection(light_text_token_set))
    token_overlap_count_aggressive = len(
        aggressive_query_token_set.intersection(aggressive_text_token_set)
    )

    token_coverage_light = (
        (token_overlap_count_light / len(light_query_token_set)) * 100
        if light_query_token_set
        else 0.0
    )

    token_coverage_aggressive = (
        (token_overlap_count_aggressive / len(aggressive_query_token_set)) * 100
        if aggressive_query_token_set
        else 0.0
    )

    token_coverage = max(token_coverage_light, token_coverage_aggressive)

    exact_display = 100.0 if original_query.strip() == text_display.strip() else 0.0
    exact_normalized_light = 100.0 if light_query == text_light else 0.0
    exact_normalized_aggressive = 100.0 if aggressive_query == text_aggressive else 0.0

    contains_query_in_text_light = 100.0 if light_query and light_query in text_light else 0.0
    contains_query_in_text_aggressive = 100.0 if aggressive_query and aggressive_query in text_aggressive else 0.0
    contains_text_in_query_light = 100.0 if text_light and text_light in light_query else 0.0

    ratio_score = float(fuzz.ratio(light_query, text_light))
    token_set_score = float(fuzz.token_set_ratio(light_query, text_light))
    token_sort_score = float(fuzz.token_sort_ratio(light_query, text_light))
    partial_raw = float(fuzz.partial_ratio(light_query, text_light))
    aggressive_token_set_score = float(fuzz.token_set_ratio(aggressive_query, text_aggressive))

    adjusted_partial = partial_raw * length_ratio

    short_candidate_penalty = 0.0
    if text_len < max(6, int(query_len * 0.35)) and exact_normalized_light != 100.0:
        short_candidate_penalty = 25.0

    composite_score = (
        (0.25 * exact_normalized_light)
        + (0.12 * exact_normalized_aggressive)
        + (0.08 * exact_display)
        + (0.18 * contains_query_in_text_light)
        + (0.10 * contains_query_in_text_aggressive)
        + (0.12 * token_coverage)
        + (0.06 * token_set_score)
        + (0.04 * aggressive_token_set_score)
        + (0.02 * token_sort_score)
        + (0.02 * ratio_score)
        + (0.01 * adjusted_partial)
    ) - short_candidate_penalty

    return {
        "score": round(max(composite_score, 0.0), 2),
        "exact_display": round(exact_display, 2),
        "exact_normalized_light": round(exact_normalized_light, 2),
        "exact_normalized_aggressive": round(exact_normalized_aggressive, 2),
        "contains_query_in_text_light": round(contains_query_in_text_light, 2),
        "contains_query_in_text_aggressive": round(contains_query_in_text_aggressive, 2),
        "contains_text_in_query_light": round(contains_text_in_query_light, 2),
        "ratio_score": round(ratio_score, 2),
        "token_set_score": round(token_set_score, 2),
        "aggressive_token_set_score": round(aggressive_token_set_score, 2),
        "token_sort_score": round(token_sort_score, 2),
        "partial_raw": round(partial_raw, 2),
        "adjusted_partial": round(adjusted_partial, 2),
        "token_overlap_count_light": token_overlap_count_light,
        "token_overlap_count_aggressive": token_overlap_count_aggressive,
        "token_coverage_light": round(token_coverage_light, 2),
        "token_coverage_aggressive": round(token_coverage_aggressive, 2),
        "token_coverage": round(token_coverage, 2),
        "length_ratio": round(length_ratio, 4),
        "short_candidate_penalty": round(short_candidate_penalty, 2),
        "row": row,
    }
