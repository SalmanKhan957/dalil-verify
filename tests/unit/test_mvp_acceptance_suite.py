from __future__ import annotations

from pathlib import Path

from pipelines.evaluation.suites.mvp_acceptance import load_suite


def test_mvp_acceptance_suite_loads_and_has_unique_cases() -> None:
    suite = load_suite(Path("evaluation/goldens/mvp_acceptance_cases.json"))
    assert suite["suite_id"] == "dalil-mvp-acceptance-v1"
    assert len(suite["cases"]) >= 10

    ids = [case["case_id"] for case in suite["cases"]]
    assert len(ids) == len(set(ids))


def test_mvp_acceptance_thresholds_are_strict() -> None:
    suite = load_suite(Path("evaluation/goldens/mvp_acceptance_cases.json"))
    thresholds = suite["thresholds"]
    assert thresholds["overall_pass_rate_min"] == 1.0
    assert thresholds["answered_rate_min"] == 1.0
    assert thresholds["clarify_rate_min"] == 1.0
    assert thresholds["abstain_rate_min"] == 1.0
    assert thresholds["followup_ready_rate_min"] == 1.0
    assert thresholds["comparative_tafsir_rate_min"] == 1.0
    assert thresholds["unexpected_error_rate_max"] == 0.0
