from __future__ import annotations

from typing import Any


def verifier_candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, float, float, float, float, float, float]:
    """
    Canonical ranking key for Quran verifier candidates.

    Order is based on the existing ayah/passage verifier ranking and extended with
    token_subsequence_coverage as a final tie-breaker for long-span dynamic passage
    candidates. For non-dynamic candidates, that field defaults to 0.0 and has no effect.
    """
    return (
        float(candidate.get("score", 0.0)),
        float(candidate.get("exact_normalized_light", 0.0)),
        float(candidate.get("exact_normalized_aggressive", 0.0)),
        float(candidate.get("contains_query_in_text_light", 0.0)),
        float(candidate.get("contains_query_in_text_aggressive", 0.0)),
        float(candidate.get("token_coverage", 0.0)),
        float(candidate.get("token_subsequence_coverage", 0.0)),
    )


def sort_verifier_candidates(
    candidates: list[dict[str, Any]],
    *,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    ordered = sorted(candidates, key=verifier_candidate_sort_key, reverse=True)
    if top_k is None:
        return ordered
    return ordered[:top_k]
