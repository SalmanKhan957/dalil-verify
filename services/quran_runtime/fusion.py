from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.common.text_normalization import normalize_arabic_light, tokenize
from scripts.common.quran_status import get_result_status_rank
from scripts.common.quran_citation_units import (
    annotate_result_with_canonical_unit,
    get_result_canonical_unit_rank,
    get_result_canonical_unit_type,
)
from services.quran_runtime.baseline_ayah import (
    build_result as build_ayah_result,
    compute_best_matches as compute_ayah_matches,
    load_quran_dataset,
)
from services.quran_runtime.baseline_passage import (
    build_passage_result,
    compute_best_passage_matches,
    load_quran_passage_dataset,
)

CANONICAL_UNIT_SCORE_TIE_MARGIN = 8.0
CANONICAL_UNIT_MIN_SCORE = 80.0


def get_best_score(result: dict[str, Any]) -> float:
    best = result.get("best_match")
    if not best:
        return 0.0
    return float(best.get("score", 0.0))


def get_query_token_count(query: str) -> int:
    return len(tokenize(normalize_arabic_light(query)))


def _maybe_prefer_by_canonical_unit(
    ayah_result: dict[str, Any],
    passage_result: dict[str, Any],
) -> tuple[str, str, str] | None:
    ayah_unit_type = get_result_canonical_unit_type(ayah_result, lane="ayah")
    passage_unit_type = get_result_canonical_unit_type(passage_result, lane="passage")

    ayah_unit_rank = get_result_canonical_unit_rank(ayah_result, lane="ayah")
    passage_unit_rank = get_result_canonical_unit_rank(passage_result, lane="passage")

    if ayah_unit_rank == passage_unit_rank:
        return None

    ayah_status = ayah_result.get("match_status")
    passage_status = passage_result.get("match_status")

    ayah_score = get_best_score(ayah_result)
    passage_score = get_best_score(passage_result)

    # If both are exact, prefer the more canonical Quranic unit.
    if ayah_status == passage_status == "Exact match found":
        if ayah_unit_rank > passage_unit_rank:
            return (
                "ayah",
                "canonical_unit_precedence_exact",
                (
                    f"Both lanes are exact; preferring the more canonical Quranic unit "
                    f"({ayah_unit_type} over {passage_unit_type})."
                ),
            )
        return (
            "passage",
            "canonical_unit_precedence_exact",
            (
                f"Both lanes are exact; preferring the more canonical Quranic unit "
                f"({passage_unit_type} over {ayah_unit_type})."
            ),
        )

    # If both have the same status and are both strong/close, prefer the more canonical unit.
    if ayah_status == passage_status:
        if (
            min(ayah_score, passage_score) >= CANONICAL_UNIT_MIN_SCORE
            and abs(ayah_score - passage_score) <= CANONICAL_UNIT_SCORE_TIE_MARGIN
        ):
            if ayah_unit_rank > passage_unit_rank:
                return (
                    "ayah",
                    "canonical_unit_precedence_close_tie",
                    (
                        f"Both lanes are similarly strong; preferring the more canonical Quranic unit "
                        f"({ayah_unit_type} over {passage_unit_type})."
                    ),
                )
            return (
                "passage",
                "canonical_unit_precedence_close_tie",
                (
                    f"Both lanes are similarly strong; preferring the more canonical Quranic unit "
                    f"({passage_unit_type} over {ayah_unit_type})."
                ),
            )

    return None


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

    ayah_rank = get_result_status_rank(ayah_result)
    passage_rank = get_result_status_rank(passage_result)

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

    canonical_preference = _maybe_prefer_by_canonical_unit(ayah_result, passage_result)
    if canonical_preference is not None:
        return canonical_preference

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
    # Important: annotate here, not inside passage baseline, because apps/api/main.py
    # may stamp retrieval_engine onto passage best_match before fusion.
    annotate_result_with_canonical_unit(ayah_result, lane="ayah")
    annotate_result_with_canonical_unit(passage_result, lane="passage")

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
            "ayah_status_rank": get_result_status_rank(ayah_result),
            "passage_status_rank": get_result_status_rank(passage_result),
            "ayah_score": get_best_score(ayah_result),
            "passage_score": get_best_score(passage_result),
            "score_delta_passage_minus_ayah": round(get_best_score(passage_result) - get_best_score(ayah_result), 2),
            "ayah_citation": ayah_best.get("citation"),
            "passage_citation": passage_best.get("citation"),
            "ayah_canonical_unit_type": ayah_best.get("canonical_unit_type"),
            "ayah_canonical_unit_rank": ayah_best.get("canonical_unit_rank"),
            "passage_canonical_unit_type": passage_best.get("canonical_unit_type"),
            "passage_canonical_unit_rank": passage_best.get("canonical_unit_rank"),
            "passage_window_size": passage_best.get("window_size"),
            "passage_spans_multiple": (
                passage_best.get("start_ayah") is not None
                and passage_best.get("end_ayah") is not None
                and passage_best.get("start_ayah") != passage_best.get("end_ayah")
            ),
            "decision_basis": decision_rule,
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