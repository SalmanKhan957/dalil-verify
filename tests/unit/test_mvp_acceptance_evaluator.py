from __future__ import annotations

from pipelines.evaluation.suites.mvp_acceptance import evaluate_case, summarize_results


def test_evaluate_case_passes_for_three_source_tafsir_answer() -> None:
    case = {
        "case_id": "surah_ikhlas_tafsir_three_sources",
        "category": "named_quran_anchor_tafsir",
        "query": "Tafsir of Surah Ikhlas",
        "request": {"query": "Tafsir of Surah Ikhlas"},
        "expected": {
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "terminal_state": "answered",
            "composition_mode": "quran_with_tafsir",
            "ok": True,
            "required_domains": ["quran", "tafsir"],
            "required_source_ids": [
                "tafsir:ibn-kathir-en",
                "tafsir:maarif-al-quran-en",
                "tafsir:tafheem-al-quran-en",
            ],
            "required_bundle_counts": {"quran": 1, "tafsir": 3},
            "should_have_citations": True,
            "followup_ready": True,
            "required_anchor_domains": ["quran", "tafsir"],
            "answer_kind": "nonempty",
            "public_scope": "bounded_source_grounded",
            "render_mode": "quran_with_tafsir",
        },
    }
    response = {
        "status_code": 200,
        "json": {
            "ok": True,
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "terminal_state": "answered",
            "answer_text": "Surah al-Ikhlas affirms Allah's absolute oneness.",
            "citations": [
                {"source_domain": "quran", "source_id": "quran:tanzil-simple"},
                {"source_domain": "tafsir", "source_id": "tafsir:ibn-kathir-en"},
            ],
            "warnings": [],
            "orchestration": {"diagnostics": {"render_mode": "quran_with_tafsir"}},
            "composition": {
                "composition_mode": "quran_with_tafsir",
                "policy": {"public_scope": "bounded_source_grounded"},
                "rendering": {},
                "followup": {
                    "followup_ready": True,
                    "active_anchor_refs": [
                        "quran:112:1-4",
                        "tafsir:ibn-kathir-en:84552",
                    ],
                },
                "source_bundles": [
                    {"domain": "quran", "source_id": "quran:tanzil-simple"},
                    {"domain": "tafsir", "source_id": "tafsir:ibn-kathir-en"},
                    {"domain": "tafsir", "source_id": "tafsir:maarif-al-quran-en"},
                    {"domain": "tafsir", "source_id": "tafsir:tafheem-al-quran-en"},
                ],
            },
        },
    }

    result = evaluate_case(case, response)
    assert result.passed is True


def test_evaluate_case_passes_for_policy_abstain() -> None:
    case = {
        "case_id": "policy_abstain_public_mixed_scope_anxiety",
        "category": "abstain",
        "query": "What does Islam say about anxiety?",
        "request": {"query": "What does Islam say about anxiety?"},
        "expected": {
            "route_type": "policy_restricted_request",
            "terminal_state": "abstain",
            "composition_mode": "abstain",
            "ok": False,
            "abstention_reason_code": "policy_restricted",
            "answer_kind": "empty",
            "public_scope": "bounded_source_grounded",
            "render_mode": "abstain",
        },
    }
    response = {
        "status_code": 200,
        "json": {
            "ok": False,
            "route_type": "policy_restricted_request",
            "action_type": "unknown",
            "terminal_state": "abstain",
            "answer_text": None,
            "citations": [],
            "warnings": [],
            "orchestration": {"diagnostics": {"render_mode": "abstain"}},
            "composition": {
                "composition_mode": "abstain",
                "policy": {"public_scope": "bounded_source_grounded"},
                "rendering": {},
                "followup": {"followup_ready": False, "active_anchor_refs": []},
                "source_bundles": [],
                "abstention": {"reason_code": "policy_restricted"},
            },
        },
    }

    result = evaluate_case(case, response)
    assert result.passed is True


def test_summarize_results_flags_failed_gate() -> None:
    suite = {
        "suite_id": "dalil-mvp-acceptance-v1",
        "thresholds": {
            "overall_pass_rate_min": 1.0,
            "answered_rate_min": 1.0,
            "clarify_rate_min": 1.0,
            "abstain_rate_min": 1.0,
            "followup_ready_rate_min": 1.0,
            "comparative_tafsir_rate_min": 1.0,
            "unexpected_error_rate_max": 0.0,
        },
        "cases": [
            {
                "case_id": "anchored_followup_hadith_summarize",
                "expected": {
                    "terminal_state": "answered",
                    "followup_ready": True,
                    "required_bundle_counts": {"hadith": 1},
                    "ok": True,
                },
            }
        ],
    }
    failing = evaluate_case(
        {
            "case_id": "anchored_followup_hadith_summarize",
            "category": "anchored_followup_hadith",
            "query": "Summarize this hadith",
            "request": {"query": "Summarize this hadith"},
            "expected": {
                "route_type": "anchored_followup_hadith",
                "action_type": "explain",
                "terminal_state": "answered",
                "ok": True,
                "required_bundle_counts": {"hadith": 1},
                "followup_ready": True,
            },
        },
        {
            "status_code": 200,
            "json": {
                "ok": False,
                "route_type": "policy_restricted_request",
                "action_type": "unknown",
                "terminal_state": "abstain",
                "answer_text": None,
                "citations": [],
                "warnings": [],
                "orchestration": {"diagnostics": {"render_mode": "abstain"}},
                "composition": {
                    "composition_mode": "abstain",
                    "policy": {"public_scope": "bounded_source_grounded"},
                "rendering": {},
                    "followup": {"followup_ready": False, "active_anchor_refs": []},
                    "source_bundles": [],
                    "abstention": {"reason_code": "policy_restricted"},
                },
            },
        },
    )
    summary = summarize_results(suite, [failing])
    assert summary["all_gates_passed"] is False
    assert summary["gates"]["overall_pass_gate"] is False


def test_evaluate_case_accepts_render_mode_from_orchestration_diagnostics_only() -> None:
    case = {
        "case_id": "explicit_hadith_explain_bukhari_7",
        "category": "explicit_hadith_explain",
        "query": "Explain Bukhari 7",
        "request": {"query": "Explain Bukhari 7"},
        "expected": {
            "route_type": "explicit_hadith_reference",
            "action_type": "explain",
            "terminal_state": "answered",
            "composition_mode": "hadith_explanation",
            "ok": True,
            "required_domains": ["hadith"],
            "should_have_citations": True,
            "answer_kind": "nonempty",
            "public_scope": "bounded_source_grounded",
            "render_mode": "hadith_explanation",
        },
    }
    response = {
        "status_code": 200,
        "json": {
            "ok": True,
            "route_type": "explicit_hadith_reference",
            "action_type": "explain",
            "terminal_state": "answered",
            "answer_text": "In simple terms: this hadith records Heraclius questioning Abu Sufyan.",
            "citations": [{"source_domain": "hadith", "source_id": "hadith:sahih-al-bukhari-en"}],
            "warnings": [],
            "orchestration": {"diagnostics": {"render_mode": "hadith_explanation"}},
            "composition": {
                "composition_mode": "hadith_explanation",
                "policy": {"public_scope": "bounded_source_grounded"},
                "rendering": {},
                "followup": {"followup_ready": True, "active_anchor_refs": ["hadith:sahih-al-bukhari-en:7"]},
                "source_bundles": [{"domain": "hadith", "source_id": "hadith:sahih-al-bukhari-en"}],
            },
        },
    }
    result = evaluate_case(case, response)
    assert result.checks["render_mode"] is True
