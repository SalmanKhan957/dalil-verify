from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.common.quran_ranking import sort_verifier_candidates
from scripts.common.quran_scoring import compute_candidate_score
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

GENERIC_SHORT_TOKENS = {
    "من", "في", "على", "الى", "إلى", "عن", "ما", "ماذا", "كيف", "هل",
    "قال", "قالوا", "الله", "للَّه", "الناس", "يوم", "رب", "ربك", "ربهم",
    "هذا", "هذه", "ذلك", "تلك", "كل", "بعض", "ان", "إن", "لا", "لن",
}

ARABIC_QUESTION_PREFIXES = ("ما ", "ماذا ", "كيف ", "هل ", "أين ", "اين ", "متى ", "لماذا ", "كم ", "من ")
ENGLISH_QUESTION_PREFIXES = ("what ", "how ", "where ", "when ", "why ", "is this", "does this", "which ")
META_QUERY_MARKERS = ("هل هذه آية", "هل هذا من القرآن", "اين ورد", "أين ورد", "في القرآن", "في القران")


def _is_generic_two_token_input(tokens: list[str]) -> bool:
    if len(tokens) != 2:
        return False
    if tokens[0] == tokens[1]:
        return True
    generic_hits = sum(1 for token in tokens if token in GENERIC_SHORT_TOKENS)
    short_hits = sum(1 for token in tokens if len(token) <= 3)
    return generic_hits == 2 or (generic_hits >= 1 and short_hits == 2)


def _is_short_repeated_phrase(tokens: list[str]) -> bool:
    return len(tokens) <= 3 and len(set(tokens)) < len(tokens)


def _has_low_structural_signal(tokens: list[str]) -> bool:
    if not tokens:
        return True
    tiny_tokens = sum(1 for token in tokens if len(token) <= 1)
    if tiny_tokens >= max(2, (len(tokens) + 1) // 2):
        return True
    if len(tokens) >= 3 and len(set(tokens)) == 1:
        return True
    return False


def assess_verifier_query(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    q_norm = normalize_arabic_light(q)
    q_tokens = tokenize(q_norm)
    lowered = q.lower().strip()

    if not q_norm:
        return {
            "mode": "cannot_assess",
            "reason": "empty_after_normalization",
            "boundary_note": "Input is empty or unsuitable for reliable verification.",
        }

    if (
        "?" in q
        or lowered.startswith(ENGLISH_QUESTION_PREFIXES)
        # or q.startswith(ARABIC_QUESTION_PREFIXES)
        or any(marker in q for marker in META_QUERY_MARKERS)
    ):
        return {
            "mode": "ask_like",
            "reason": "question_or_meta_query",
            "boundary_note": (
                "This looks like a question or meta-query rather than source-verification input. "
                "Route this to the ask engine, not the verifier."
            ),
        }

    if len(q_norm) < 6 or len(q_tokens) < 2:
        return {
            "mode": "cannot_assess",
            "reason": "too_short",
            "boundary_note": "Input is too short, too generic, or too vague for reliable verification.",
        }

    if _is_generic_two_token_input(q_tokens):
        return {
            "mode": "cannot_assess",
            "reason": "generic_two_token_input",
            "boundary_note": "Input is too short or too generic to verify reliably against the Quran corpus.",
        }

    if _is_short_repeated_phrase(q_tokens):
        return {
            "mode": "cannot_assess",
            "reason": "short_repeated_phrase",
            "boundary_note": "Input is a very short repeated phrase and is too ambiguous for reliable verification.",
        }

    if _has_low_structural_signal(q_tokens):
        return {
            "mode": "cannot_assess",
            "reason": "low_structural_signal",
            "boundary_note": "Input appears too noisy or structurally weak for reliable Quran verification.",
        }

    return {
        "mode": "verify_like",
        "reason": "sufficient_signal",
        "boundary_note": "",
    }


def classify_query(query: str) -> str:
    return assess_verifier_query(query)["mode"]


# def classify_query(query: str) -> str:
#     q = query.strip()
#     q_norm = normalize_arabic_light(q)
#     q_tokens = tokenize(q_norm)

#     if len(q_norm) < 6:
#         return "cannot_assess"

#     if len(q_tokens) < 2:
#         return "cannot_assess"

#     lowered = q.lower().strip()
#     if "?" in q or lowered.startswith("what ") or lowered.startswith("how "):
#         return "ask_like"

#     if q.startswith("ما ") or q.startswith("ماذا ") or q.startswith("كيف "):
#         return "ask_like"

#     return "verify_like"



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

    return sort_verifier_candidates(candidates, top_k=top_k)


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

def is_full_exact_match(best_candidate: dict[str, Any] | None) -> bool:
    if not best_candidate:
        return False
    return (
        best_candidate.get("exact_display") == 100.0
        or best_candidate.get("exact_normalized_light") == 100.0
    )


def determine_match_status(query: str, best_candidate: dict[str, Any]) -> str:
    # Important exception:
    # A full exact ayah hit should still count as exact even if the query is only one token.
    if is_full_exact_match(best_candidate):
        return "Exact match found"

    assessment = assess_verifier_query(query)
    if assessment["mode"] != "verify_like":
        return "Cannot assess"

    query_norm = normalize_arabic_light(query)
    query_tokens = tokenize(query_norm)

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
        and best_candidate["token_coverage"] >= 60.0
        and len(query_tokens) >= 3
    ):
        return "Close / partial match found"

    if (
        max(
            best_candidate["token_set_score"],
            best_candidate["aggressive_token_set_score"],
        ) >= 95.0
        and best_candidate["token_coverage"] >= 70.0
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
    assessment = assess_verifier_query(query)
    mode = assessment["mode"]

    # Important exception:
    # If the best candidate is a full exact ayah, allow it even for otherwise unassessable short input.
    if mode == "cannot_assess":
        if candidates and is_full_exact_match(candidates[0]):
            mode = "verify_like"
        else:
            return {
                "query": query,
                "mode": "verifier",
                "match_status": "Cannot assess",
                "confidence": "low",
                "boundary_note": assessment["boundary_note"],
                "best_match": None,
                "alternatives": [],
            }

    if mode == "ask_like":
        return {
            "query": query,
            "mode": "ask_engine",
            "match_status": "Cannot assess",
            "confidence": "low",
            "boundary_note": assessment["boundary_note"],
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
