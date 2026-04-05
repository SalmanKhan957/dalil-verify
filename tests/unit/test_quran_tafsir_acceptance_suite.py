from __future__ import annotations

from pathlib import Path

from pipelines.evaluation.suites.quran_tafsir_acceptance import load_suite


def test_acceptance_suite_loads_and_has_unique_cases() -> None:
    suite = load_suite(Path("evaluation/goldens/quran_tafsir_explain_cases.json"))
    assert suite["suite_id"] == "quran-tafsir-explain-v1"
    assert len(suite["cases"]) >= 20

    ids = [case["case_id"] for case in suite["cases"]]
    assert len(ids) == len(set(ids))


def test_acceptance_thresholds_are_strict() -> None:
    suite = load_suite(Path("evaluation/goldens/quran_tafsir_explain_cases.json"))
    thresholds = suite["thresholds"]
    assert thresholds["quran_resolution_rate_min"] == 1.0
    assert thresholds["citation_presence_rate_min"] == 1.0
    assert thresholds["abstention_rate_min"] == 1.0
    assert thresholds["unexpected_error_rate_max"] == 0.0
