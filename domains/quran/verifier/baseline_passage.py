from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from domains.quran.verifier.internal.quran_ranking import sort_verifier_candidates
from domains.quran.verifier.internal.quran_scoring import compute_candidate_score
from domains.quran.verifier.baseline_ayah import (
    classify_query,
    determine_match_status,
)
from shared.utils.arabic_text import normalize_arabic_light, normalize_arabic_aggressive, tokenize


def load_quran_passage_dataset(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Quran passage CSV not found: {csv_path}")

    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["window_size"] = int(row["window_size"])
            row["surah_no"] = int(row["surah_no"])
            row["start_ayah"] = int(row["start_ayah"])
            row["end_ayah"] = int(row["end_ayah"])
            row["translation_name"] = row.get("translation_name") or ""
            text_display = row.get("text_display") or ""
            row["text_normalized_light"] = normalize_arabic_light(text_display)
            row["text_normalized_aggressive"] = normalize_arabic_aggressive(text_display)
            row["component_citations_json"] = row.get("component_citations_json") or "[]"
            row["component_source_ids_json"] = row.get("component_source_ids_json") or "[]"

            row["tokens_light"] = tokenize(row["text_normalized_light"])
            row["tokens_aggressive"] = tokenize(row["text_normalized_aggressive"])

            rows.append(row)

    if not rows:
        raise ValueError("No rows loaded from Quran passage CSV.")

    return rows


def compute_best_passage_matches(
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

    return sort_verifier_candidates(candidates, top_k=top_k)


def build_passage_result(query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
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
                "start_ayah": alt_row["start_ayah"],
                "end_ayah": alt_row["end_ayah"],
                "window_size": alt_row["window_size"],
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
            "Based only on the current indexed Quran passage source. "
            "This is not a fatwa or a complete survey of all Islamic literature."
        ),
        "best_match": {
            "source_type": best_row["source_type"],
            "source_id": best_row["source_id"],
            "citation": best_row["citation_string"],
            "canonical_source_id": best_row["canonical_source_id"],
            "surah_no": best_row["surah_no"],
            "start_ayah": best_row["start_ayah"],
            "end_ayah": best_row["end_ayah"],
            "window_size": best_row["window_size"],
            "surah_name_ar": best_row["surah_name_ar"],
            "text_display": best_row["text_display"],
            "text_normalized_light": best_row["text_normalized_light"],
            "text_normalized_aggressive": best_row["text_normalized_aggressive"],
            "component_citations": json.loads(best_row["component_citations_json"]),
            "component_source_ids": json.loads(best_row["component_source_ids_json"]),
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
        description="Baseline Quran passage verifier (2/3-ayah windows)."
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/processed/quran_passages/quran_passage_windows_v1.csv",
        help="Path to Quran passage CSV.",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="User input to verify against Quran passage windows.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.data)
    rows = load_quran_passage_dataset(dataset_path)
    candidates = compute_best_passage_matches(args.query, rows, top_k=5)
    result = build_passage_result(args.query, candidates)

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
