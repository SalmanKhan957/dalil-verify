from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from scripts.common.text_normalization import (
    normalize_arabic_light,
    normalize_arabic_aggressive,
    tokenize,
)


def load_quran_dataset(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Canonical Quran CSV not found: {csv_path}")

    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["surah_no"] = int(row["surah_no"])
            row["ayah_no"] = int(row["ayah_no"])
            row["translation_name"] = row.get("translation_name") or ""
            row["bismillah"] = row.get("bismillah") or ""

            text_display = row.get("text_display") or ""
            row["text_normalized_light"] = normalize_arabic_light(text_display)
            row["text_normalized_aggressive"] = normalize_arabic_aggressive(text_display)

            row["tokens_light"] = tokenize(row["text_normalized_light"])
            row["tokens_aggressive"] = tokenize(row["text_normalized_aggressive"])

            rows.append(row)

    if not rows:
        raise ValueError("No rows loaded from Quran canonical CSV.")

    return rows


def classify_query(query: str) -> str:
    q = query.strip()
    q_norm = normalize_arabic_light(q)
    q_tokens = tokenize(q_norm)

    if len(q_norm) < 6:
        return "cannot_assess"

    if len(q_tokens) < 2:
        return "cannot_assess"

    lowered = q.lower().strip()
    if "?" in q or lowered.startswith("what ") or lowered.startswith("how "):
        return "ask_like"

    if q.startswith("ما ") or q.startswith("ماذا ") or q.startswith("كيف "):
        return "ask_like"

    return "verify_like"


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


def compute_best_matches(
    query: str,
    rows: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    normalized_query = normalize_arabic_light(query)
    aggressive_query = normalize_arabic_aggressive(query)
    query_tokens = tokenize(normalized_query)
    aggressive_query_tokens = tokenize(aggressive_query)

    candidates: list[dict[str, Any]] = []
    for row in rows:
        candidate = compute_candidate_score(
            normalized_query=normalized_query,
            query_tokens=query_tokens,
            row=row,
            original_query=query,
            aggressive_query=aggressive_query,
            aggressive_query_tokens=aggressive_query_tokens,
        )
        candidates.append(candidate)

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["exact_normalized_light"],
            x["exact_normalized_aggressive"],
            x["contains_query_in_text_light"],
            x["contains_query_in_text_aggressive"],
            x["token_coverage"],
        ),
        reverse=True,
    )
    return candidates[:top_k]


def is_exact_excerpt_match(query: str, best_candidate: dict[str, Any], *, min_query_tokens: int = 4) -> bool:
    query_norm = normalize_arabic_light(query)
    query_tokens = tokenize(query_norm)
    if len(query_norm) < 6 or len(query_tokens) < min_query_tokens:
        return False

    contains_light = float(best_candidate.get("contains_query_in_text_light") or 0.0)
    contains_aggressive = float(best_candidate.get("contains_query_in_text_aggressive") or 0.0)
    if contains_light != 100.0 and contains_aggressive != 100.0:
        return False

    # Excerpt-exact is for a contiguous normalized substring inside the canonical text.
    # Keep this strict enough to avoid promoting fuzzy token-set matches.
    coverage = float(best_candidate.get("token_coverage") or 0.0)
    partial_raw = float(best_candidate.get("partial_raw") or 0.0)
    if coverage < 95.0:
        return False
    if partial_raw < 100.0:
        return False
    return True


def determine_match_status(query: str, best_candidate: dict[str, Any]) -> str:
    query_norm = normalize_arabic_light(query)
    query_tokens = tokenize(query_norm)

    if len(query_norm) < 6 or len(query_tokens) < 2:
        return "Cannot assess"

    if (
        best_candidate["exact_display"] == 100.0
        or best_candidate["exact_normalized_light"] == 100.0
    ):
        return "Exact match found"

    if (
        best_candidate["exact_normalized_aggressive"] == 100.0
        and best_candidate["token_coverage"] >= 95.0
        and best_candidate["length_ratio"] >= 0.98
    ):
        return "Exact match found"

    if is_exact_excerpt_match(query, best_candidate):
        return "Exact match found"

    if best_candidate["exact_normalized_aggressive"] == 100.0:
        return "Close / partial match found"

    if (
        (
            best_candidate["contains_query_in_text_light"] == 100.0
            or best_candidate["contains_query_in_text_aggressive"] == 100.0
        )
        and best_candidate["token_coverage"] >= 80.0
        and len(query_tokens) >= 3
    ):
        return "Close / partial match found"

    if (
        max(
            best_candidate["token_set_score"],
            best_candidate["aggressive_token_set_score"],
        ) >= 95.0
        and best_candidate["token_coverage"] >= 80.0
        and len(query_tokens) >= 4
    ):
        return "Close / partial match found"

    if (
        best_candidate["aggressive_token_set_score"] >= 85.0
        and best_candidate["token_coverage"] >= 80.0
        and len(query_tokens) >= 4
    ):
        return "Close / partial match found"

    if best_candidate["score"] >= 60.0 and best_candidate["token_coverage"] >= 50.0:
        return "Close / partial match found"

    return "No reliable match found in current corpus"


def build_result(query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    mode = classify_query(query)

    if mode == "cannot_assess":
        return {
            "query": query,
            "mode": "verifier",
            "match_status": "Cannot assess",
            "confidence": "low",
            "boundary_note": "Input is too short, too generic, or too vague for reliable verification.",
            "best_match": None,
            "alternatives": [],
        }

    if mode == "ask_like":
        return {
            "query": query,
            "mode": "ask_engine",
            "match_status": "Cannot assess",
            "confidence": "low",
            "boundary_note": (
                "This looks like a question rather than a source-verification input. "
                "Route this to the ask engine, not the verifier."
            ),
            "best_match": None,
            "alternatives": [],
        }

    best = candidates[0]
    status = determine_match_status(query, best)

    if status == "Exact match found":
        confidence = "high"
    elif status == "Close / partial match found":
        confidence = "medium"
    else:
        confidence = "low"

    best_row = best["row"]

    alternatives = []
    for c in candidates[1:4]:
        alt_row = c["row"]
        alternatives.append(
            {
                "citation": alt_row["citation_string"],
                "surah_no": alt_row["surah_no"],
                "ayah_no": alt_row["ayah_no"],
                "text_display": alt_row["text_display"],
                "score": c["score"],
                "token_coverage": c["token_coverage"],
            }
        )

    result = {
        "query": query,
        "mode": "verifier",
        "match_status": status,
        "confidence": confidence,
        "boundary_note": (
            "Based only on the current indexed Quran Arabic source. "
            "This is not a fatwa or a complete survey of all Islamic literature."
        ),
        "best_match": {
            "source_type": best_row["source_type"],
            "source_id": best_row["source_id"],
            "citation": best_row["citation_string"],
            "canonical_source_id": best_row["canonical_source_id"],
            "surah_no": best_row["surah_no"],
            "ayah_no": best_row["ayah_no"],
            "surah_name_ar": best_row["surah_name_ar"],
            "text_display": best_row["text_display"],
            "text_normalized_light": best_row["text_normalized_light"],
            "text_normalized_aggressive": best_row["text_normalized_aggressive"],
            "bismillah": best_row["bismillah"],
            "score": best["score"],
            "scoring_breakdown": {
                "exact_display": best["exact_display"],
                "exact_normalized_light": best["exact_normalized_light"],
                "exact_normalized_aggressive": best["exact_normalized_aggressive"],
                "contains_query_in_text_light": best["contains_query_in_text_light"],
                "contains_query_in_text_aggressive": best["contains_query_in_text_aggressive"],
                "contains_text_in_query_light": best["contains_text_in_query_light"],
                "ratio_score": best["ratio_score"],
                "token_set_score": best["token_set_score"],
                "aggressive_token_set_score": best["aggressive_token_set_score"],
                "token_sort_score": best["token_sort_score"],
                "partial_raw": best["partial_raw"],
                "adjusted_partial": best["adjusted_partial"],
                "token_overlap_count_light": best["token_overlap_count_light"],
                "token_overlap_count_aggressive": best["token_overlap_count_aggressive"],
                "token_coverage_light": best["token_coverage_light"],
                "token_coverage_aggressive": best["token_coverage_aggressive"],
                "token_coverage": best["token_coverage"],
                "length_ratio": best["length_ratio"],
                "short_candidate_penalty": best["short_candidate_penalty"],
            },
        },
        "alternatives": alternatives,
    }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baseline Quran lexical verifier (Arabic only, shared normalization)."
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/processed/quran/quran_arabic_canonical.csv",
        help="Path to canonical Quran CSV.",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="User input to verify.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.data)
    rows = load_quran_dataset(dataset_path)
    candidates = compute_best_matches(args.query, rows, top_k=5)
    result = build_result(args.query, candidates)

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
