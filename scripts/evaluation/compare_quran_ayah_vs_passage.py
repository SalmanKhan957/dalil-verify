from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.common.text_normalization import normalize_arabic_light, tokenize
from scripts.evaluation.quran_verifier_baseline import (
    build_result as build_ayah_result,
    compute_best_matches as compute_ayah_matches,
    load_quran_dataset,
)
from scripts.evaluation.quran_passage_verifier_baseline import (
    build_passage_result,
    compute_best_passage_matches,
    load_quran_passage_dataset,
)


STATUS_RANK = {
    "Cannot assess": 0,
    "No reliable match found in current corpus": 1,
    "Close / partial match found": 2,
    "Exact match found": 3,
}


def get_best_score(result: dict[str, Any]) -> float:
    best = result.get("best_match")
    if not best:
        return 0.0
    return float(best.get("score", 0.0))


def get_status_rank(result: dict[str, Any]) -> int:
    return STATUS_RANK.get(result.get("match_status", ""), 0)


def get_query_token_count(query: str) -> int:
    return len(tokenize(normalize_arabic_light(query)))


def choose_preferred_lane(
    query: str,
    ayah_result: dict[str, Any],
    passage_result: dict[str, Any],
) -> tuple[str, str, str]:
    """
    Decide whether ayah or passage is the better primary response.
    Returns:
        (preferred_lane, decision_rule, rationale)
    """
    if ayah_result.get("mode") == "ask_engine":
        return (
            "ask_engine",
            "ask_routing",
            "Query looks like a question and should route to the ask engine.",
        )

    if (
        ayah_result.get("match_status") == "Cannot assess"
        and passage_result.get("match_status") == "Cannot assess"
    ):
        return (
            "none",
            "cannot_assess",
            "Input is too short, too vague, or unsuitable for reliable verification.",
        )

    ayah_rank = get_status_rank(ayah_result)
    passage_rank = get_status_rank(passage_result)

    ayah_score = get_best_score(ayah_result)
    passage_score = get_best_score(passage_result)

    token_count = get_query_token_count(query)

    ayah_best = ayah_result.get("best_match") or {}
    passage_best = passage_result.get("best_match") or {}

    ayah_contains_query = (
        ayah_best.get("scoring_breakdown", {}).get("contains_query_in_text_light", 0) == 100.0
        or ayah_best.get("scoring_breakdown", {}).get("contains_query_in_text_aggressive", 0) == 100.0
    )

    passage_spans_multiple = (
        passage_best.get("start_ayah") is not None
        and passage_best.get("end_ayah") is not None
        and passage_best.get("start_ayah") != passage_best.get("end_ayah")
    )

    if passage_rank > ayah_rank:
        return (
            "passage",
            "status_rank_passage",
            "Passage lane produced a stronger match classification than the ayah lane.",
        )

    if ayah_rank > passage_rank:
        return (
            "ayah",
            "status_rank_ayah",
            "Ayah lane produced a stronger match classification than the passage lane.",
        )

    if ayah_rank <= 1 and passage_rank <= 1:
        return (
            "ayah",
            "weak_both_default_ayah",
            "Both lanes are weak; defaulting to ayah lane for stricter precision.",
        )

    if ayah_contains_query and ayah_score >= (passage_score - 8.0):
        return (
            "ayah",
            "precision_guard_ayah",
            "A single ayah already contains the query cleanly; preferring ayah for precision.",
        )

    if (
        passage_rank >= 2
        and token_count >= 6
        and passage_spans_multiple
        and passage_score >= (ayah_score - 5.0)
    ):
        return (
            "passage",
            "long_query_competitive_passage",
            "Query is long enough to likely span adjacent ayat, and passage lane is competitive or stronger.",
        )

    if ayah_score >= (passage_score + 5.0):
        return (
            "ayah",
            "material_score_advantage_ayah",
            "Ayah lane produced a materially stronger score.",
        )

    if passage_spans_multiple and passage_score >= (ayah_score + 3.0) and token_count >= 5:
        return (
            "passage",
            "multi_ayah_score_advantage_passage",
            "Passage lane matched a multi-ayah window and is stronger than the ayah lane.",
        )

    return (
        "ayah",
        "default_safe_ayah",
        "Defaulting to ayah lane as the safer primary citation.",
    )


def build_fusion_output(
    query: str,
    ayah_result: dict[str, Any],
    passage_result: dict[str, Any],
) -> dict[str, Any]:
    preferred_lane, decision_rule, rationale = choose_preferred_lane(query, ayah_result, passage_result)

    if preferred_lane == "passage":
        preferred_result = passage_result
        secondary_result = ayah_result
    elif preferred_lane == "ayah":
        preferred_result = ayah_result
        secondary_result = passage_result
    else:
        preferred_result = ayah_result
        secondary_result = passage_result

    ayah_best = ayah_result.get("best_match") or {}
    passage_best = passage_result.get("best_match") or {}

    return {
        "query": query,
        "preferred_lane": preferred_lane,
        "decision_rule": decision_rule,
        "rationale": rationale,
        "query_token_count": get_query_token_count(query),
        "preferred_result": preferred_result,
        "secondary_result": secondary_result,
        "ayah_result": ayah_result,
        "passage_result": passage_result,
        "analytics": {
            "ayah_status_rank": get_status_rank(ayah_result),
            "passage_status_rank": get_status_rank(passage_result),
            "ayah_score": get_best_score(ayah_result),
            "passage_score": get_best_score(passage_result),
            "score_delta_passage_minus_ayah": round(get_best_score(passage_result) - get_best_score(ayah_result), 2),
            "ayah_citation": ayah_best.get("citation"),
            "passage_citation": passage_best.get("citation"),
            "passage_window_size": passage_best.get("window_size"),
            "passage_spans_multiple": (
                passage_best.get("start_ayah") is not None
                and passage_best.get("end_ayah") is not None
                and passage_best.get("start_ayah") != passage_best.get("end_ayah")
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ayah lane vs passage lane for Quran verification."
    )
    parser.add_argument(
        "--ayah-data",
        type=str,
        default="data/processed/quran/quran_arabic_canonical.csv",
        help="Path to canonical ayah CSV.",
    )
    parser.add_argument(
        "--passage-data",
        type=str,
        default="data/processed/quran_passages/quran_passage_windows_v1.csv",
        help="Path to Quran passage CSV.",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="User input to compare across ayah and passage lanes.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    args = parser.parse_args()

    ayah_rows = load_quran_dataset(Path(args.ayah_data))
    passage_rows = load_quran_passage_dataset(Path(args.passage_data))

    ayah_candidates = compute_ayah_matches(args.query, ayah_rows, top_k=5)
    passage_candidates = compute_best_passage_matches(args.query, passage_rows, top_k=5)

    ayah_result = build_ayah_result(args.query, ayah_candidates)
    passage_result = build_passage_result(args.query, passage_candidates)

    fusion_output = build_fusion_output(
        query=args.query,
        ayah_result=ayah_result,
        passage_result=passage_result,
    )

    if args.pretty:
        print(json.dumps(fusion_output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(fusion_output, ensure_ascii=False))


if __name__ == "__main__":
    main()