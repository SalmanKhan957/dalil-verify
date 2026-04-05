from __future__ import annotations

from pipelines.evaluation.suites.quran_tafsir_acceptance import evaluate_case, summarize_results


def test_evaluate_case_passes_for_good_tafsir_response() -> None:
    case = {
        "case_id": "surah_fatiha_explain",
        "category": "surah_explain",
        "query": "Explain Surah Al-Fatiha",
        "request": {"query": "Explain Surah Al-Fatiha"},
        "expected": {
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "canonical_source_id": "quran:1:1-7",
            "should_include_tafsir": True,
            "should_have_citations": True,
            "should_abstain": False,
            "answer_quality": "explanatory",
        },
    }
    response = {
        "status_code": 200,
        "json": {
            "ok": True,
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "answer_text": "Surah Al-Fatiha begins with praise of Allah and asks Him for guidance to the straight path. In the attached tafsir, it is presented as a foundational prayer of worship, reliance, and guidance.",
            "citations": [
                {"source_domain": "quran", "source_id": "quran:tanzil-simple"},
                {"source_domain": "tafsir", "source_id": "tafsir:ibn-kathir-en"},
            ],
            "quran_support": {
                "citation_string": "Quran 1:1-7",
                "canonical_source_id": "quran:1:1-7",
                "translation_text": "In the name of Allah, the Merciful, the Compassionate...",
            },
            "tafsir_support": [{"source_id": "tafsir:ibn-kathir-en"}],
            "resolution": {"canonical_source_id": "quran:1:1-7"},
            "partial_success": False,
            "warnings": [],
            "error": None,
        },
    }

    result = evaluate_case(case, response)
    assert result.passed is True


def test_summarize_results_flags_unexpected_error_rate() -> None:
    suite = {
        "suite_id": "demo",
        "thresholds": {
            "quran_resolution_rate_min": 1.0,
            "tafsir_inclusion_rate_min": 1.0,
            "citation_presence_rate_min": 1.0,
            "abstention_rate_min": 1.0,
            "unexpected_error_rate_max": 0.0,
            "overall_pass_rate_min": 1.0,
        },
        "cases": [
            {
                "case_id": "case_1",
                "expected": {
                    "canonical_source_id": "quran:1:1-7",
                    "should_include_tafsir": True,
                    "should_have_citations": True,
                    "should_abstain": False,
                },
            }
        ],
    }
    failing_result = evaluate_case(
        {
            "case_id": "case_1",
            "category": "surah_explain",
            "query": "Explain Surah Al-Fatiha",
            "request": {"query": "Explain Surah Al-Fatiha"},
            "expected": {
                "route_type": "explicit_quran_reference",
                "action_type": "explain",
                "canonical_source_id": "quran:1:1-7",
                "should_include_tafsir": True,
                "should_have_citations": True,
                "should_abstain": False,
                "answer_quality": "explanatory",
            },
        },
        {
            "status_code": 200,
            "json": {
                "ok": True,
                "route_type": "explicit_quran_reference",
                "action_type": "explain",
                "answer_text": "Quran 1:1-7 says: In the name of Allah...",
                "citations": [{"source_domain": "quran"}],
                "quran_support": {
                    "citation_string": "Quran 1:1-7",
                    "canonical_source_id": "quran:1:1-7",
                    "translation_text": "Quran 1:1-7 says: In the name of Allah...",
                },
                "tafsir_support": [],
                "resolution": {"canonical_source_id": "quran:1:1-7"},
                "partial_success": True,
                "warnings": ["Tafsir retrieval failed"],
                "error": None,
            },
        },
    )
    summary = summarize_results(suite, [failing_result])
    assert summary["metrics"]["unexpected_error_rate"] == 1.0
    assert summary["all_gates_passed"] is False
