from __future__ import annotations

"""Facade for Quran verifier scoring/ranking helpers used by the API runtime."""

from domains.quran.verifier.internal.quran_status import get_status_rank
from domains.quran.verifier.fusion import build_fusion_output
from domains.quran.verifier.baseline_passage import (
    build_passage_result,
    compute_best_passage_matches,
    load_quran_passage_dataset,
)
from domains.quran.verifier.baseline_ayah import (
    assess_verifier_query,
    build_result as build_ayah_result,
    compute_best_matches as compute_ayah_matches,
    determine_match_status,
    load_quran_dataset,
)

__all__ = [
    "get_status_rank",
    "build_fusion_output",
    "build_passage_result",
    "compute_best_passage_matches",
    "load_quran_passage_dataset",
    "assess_verifier_query",
    "build_ayah_result",
    "compute_ayah_matches",
    "determine_match_status",
    "load_quran_dataset",
]
