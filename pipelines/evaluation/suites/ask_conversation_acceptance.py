from __future__ import annotations

from typing import Any

from pipelines.evaluation.suites.mvp_acceptance import (
    CaseResult,
    HttpClient,
    LocalAppClient,
    build_markdown_report as build_base_markdown_report,
    evaluate_case,
    load_suite,
)


def _endpoint_path(endpoint: Any) -> str:
    if isinstance(endpoint, dict):
        value = endpoint.get("path")
        return str(value or "/ask")
    return str(endpoint or "/ask")


def _expected_by_id(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case["case_id"]: case["expected"] for case in suite["cases"]}


def _rate(numerator: int, denominator: int, *, empty_value: float = 1.0) -> float:
    return empty_value if denominator == 0 else numerator / denominator


def summarize_results(suite: dict[str, Any], results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.passed)
    expected_by_id = _expected_by_id(suite)

    answered_cases = [r for r in results if expected_by_id[r.case_id].get("terminal_state") == "answered"]
    clarify_cases = [r for r in results if expected_by_id[r.case_id].get("terminal_state") == "clarify"]
    abstain_cases = [r for r in results if expected_by_id[r.case_id].get("terminal_state") == "abstain"]
    followup_cases = [r for r in results if expected_by_id[r.case_id].get("followup_ready") is True]
    comparative_tafsir_cases = [
        r
        for r in results
        if (expected_by_id[r.case_id].get("required_bundle_counts") or {}).get("tafsir", 0) >= 3
    ]
    explicit_ok_cases = [r for r in results if expected_by_id[r.case_id].get("ok") is True]

    metrics = {
        "overall_pass_rate": _rate(passed, total),
        "answered_rate": _rate(
            sum(bool(r.checks.get("terminal_state")) for r in answered_cases),
            len(answered_cases),
            empty_value=1.0,
        ),
        "clarify_rate": _rate(
            sum(bool(r.checks.get("terminal_state")) for r in clarify_cases),
            len(clarify_cases),
            empty_value=1.0,
        ),
        "abstain_rate": _rate(
            sum(bool(r.checks.get("terminal_state")) for r in abstain_cases),
            len(abstain_cases),
            empty_value=1.0,
        ),
        "followup_ready_rate": _rate(
            sum(bool(r.checks.get("followup_ready")) for r in followup_cases),
            len(followup_cases),
            empty_value=1.0,
        ),
        "comparative_tafsir_rate": _rate(
            sum(bool(r.checks.get("required_bundle_counts")) for r in comparative_tafsir_cases),
            len(comparative_tafsir_cases),
            empty_value=1.0,
        ),
        "unexpected_error_rate": _rate(
            sum(not bool(r.checks.get("ok", True)) for r in explicit_ok_cases),
            len(explicit_ok_cases),
            empty_value=0.0,
        ),
    }

    thresholds = suite["thresholds"]
    gates = {
        "overall_pass_gate": metrics["overall_pass_rate"] >= thresholds["overall_pass_rate_min"],
        "answered_gate": metrics["answered_rate"] >= thresholds["answered_rate_min"],
        "clarify_gate": metrics["clarify_rate"] >= thresholds["clarify_rate_min"],
        "abstain_gate": metrics["abstain_rate"] >= thresholds["abstain_rate_min"],
        "followup_ready_gate": metrics["followup_ready_rate"] >= thresholds["followup_ready_rate_min"],
        "comparative_tafsir_gate": metrics["comparative_tafsir_rate"] >= thresholds["comparative_tafsir_rate_min"],
        "unexpected_error_gate": metrics["unexpected_error_rate"] <= thresholds["unexpected_error_rate_max"],
    }

    return {
        "suite_id": suite["suite_id"],
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "overall_pass_rate": metrics["overall_pass_rate"],
        "metrics": metrics,
        "thresholds": thresholds,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "failures": [
            {
                "case_id": item.case_id,
                "category": item.category,
                "query": item.query,
                "failure_reasons": item.failure_reasons,
            }
            for item in results
            if not item.passed
        ],
    }


def build_markdown_report(summary: dict[str, Any]) -> str:
    # The shared MVP markdown builder already expects the ask-conversation metric keys
    # (`answered_rate`, `clarify_rate`, `followup_ready_rate`, etc.). Pass the summary
    # through directly rather than remapping the metric names again.
    base = build_base_markdown_report(summary)
    extra = [
        "",
        "## Ask Conversation Extras",
        "",
        f"- Abstain rate: {summary['metrics']['abstain_rate'] * 100:.1f}%",
        f"- Unexpected error rate: {summary['metrics']['unexpected_error_rate'] * 100:.1f}%",
    ]
    return base.rstrip() + "\n" + "\n".join(extra) + "\n"


def run_suite(suite: dict[str, Any], client: Any) -> tuple[list[CaseResult], dict[str, Any]]:
    endpoint = _endpoint_path(suite.get("endpoint"))
    results: list[CaseResult] = []
    for case in suite["cases"]:
        response = client.post(endpoint, case["request"])
        results.append(evaluate_case(case, response))
    return results, summarize_results(suite, results)


__all__ = [
    "CaseResult",
    "HttpClient",
    "LocalAppClient",
    "build_markdown_report",
    "evaluate_case",
    "load_suite",
    "run_suite",
    "summarize_results",
]
