from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from pipelines.evaluation.suites.quran_tafsir_acceptance import (
    HttpClient,
    LocalAppClient,
    build_markdown_report as build_base_markdown_report,
    normalize_body,
    normalize_text,
)


@dataclass(slots=True)
class CaseResult:
    case_id: str
    category: str
    query: str
    passed: bool
    checks: dict[str, bool]
    response: dict[str, Any]
    failure_reasons: list[str]


def load_suite(path: str | Path) -> dict[str, Any]:
    suite = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_suite_structure(suite)
    return suite


def _validate_suite_structure(suite: dict[str, Any]) -> None:
    required_top = {"suite_id", "endpoint", "thresholds", "cases"}
    missing = required_top - set(suite)
    if missing:
        raise ValueError(f"Suite missing required top-level keys: {sorted(missing)}")
    case_ids: set[str] = set()
    for case in suite["cases"]:
        case_id = case["case_id"]
        if case_id in case_ids:
            raise ValueError(f"Duplicate case_id detected: {case_id}")
        case_ids.add(case_id)
        for key in ("category", "query", "request", "expected"):
            if key not in case:
                raise ValueError(f"Case {case_id} missing key: {key}")


def _source_domains_from_bundles(body: dict[str, Any]) -> list[str]:
    composition = body.get("composition") or {}
    bundles = composition.get("source_bundles") or []
    domains: list[str] = []
    for bundle in bundles:
        domain = bundle.get("domain")
        if isinstance(domain, str):
            domains.append(domain)
    return domains


def _source_ids_from_bundles(body: dict[str, Any]) -> list[str]:
    composition = body.get("composition") or {}
    bundles = composition.get("source_bundles") or []
    ids: list[str] = []
    for bundle in bundles:
        source_id = bundle.get("source_id")
        if isinstance(source_id, str):
            ids.append(source_id)
    return ids


def _bundle_count_for_domain(body: dict[str, Any], domain: str) -> int:
    composition = body.get("composition") or {}
    bundles = composition.get("source_bundles") or []
    return sum(1 for bundle in bundles if bundle.get("domain") == domain)


def _conversation_followup_ready(body: dict[str, Any]) -> bool:
    composition = body.get("composition") or {}
    followup = composition.get("followup") or {}
    if isinstance(followup.get("followup_ready"), bool):
        return bool(followup["followup_ready"])
    conversation = body.get("conversation") or {}
    return bool(conversation.get("followup_ready"))


def _has_nonempty_answer_text(body: dict[str, Any]) -> bool:
    return bool(normalize_text(body.get("answer_text")))


def _render_mode(body: dict[str, Any]) -> str | None:
    diagnostics = body.get("diagnostics") or {}
    value = diagnostics.get("render_mode")
    if isinstance(value, str) and value:
        return value
    orchestration = body.get("orchestration") or {}
    orchestration_diagnostics = orchestration.get("diagnostics") or {}
    value = orchestration_diagnostics.get("render_mode")
    return value if isinstance(value, str) and value else None


def _answer_length(body: dict[str, Any]) -> int:
    return len(normalize_text(body.get("answer_text")))


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> CaseResult:
    expected = case["expected"]
    body = normalize_body(response["json"])

    checks: dict[str, bool] = {}
    failure_reasons: list[str] = []

    route_type = body.get("route_type")
    action_type = body.get("action_type")
    terminal_state = body.get("terminal_state")
    answer_mode = body.get("answer_mode")
    composition = body.get("composition") or {}
    composition_mode = composition.get("composition_mode")
    composition_policy = composition.get("policy") or {}
    composition_followup = composition.get("followup") or {}
    source_domains = _source_domains_from_bundles(body)
    source_ids = _source_ids_from_bundles(body)
    citations = body.get("citations") or []
    warnings = body.get("warnings") or []

    expected_route_type = expected.get("route_type")
    checks["route_type"] = True if expected_route_type is None else route_type == expected_route_type

    expected_action_type = expected.get("action_type")
    checks["action_type"] = True if expected_action_type is None else action_type == expected_action_type

    expected_terminal_state = expected.get("terminal_state")
    checks["terminal_state"] = True if expected_terminal_state is None else terminal_state == expected_terminal_state

    expected_composition_mode = expected.get("composition_mode")
    checks["composition_mode"] = True if expected_composition_mode is None else composition_mode == expected_composition_mode

    expected_ok = expected.get("ok")
    checks["ok"] = True if expected_ok is None else bool(body.get("ok")) == bool(expected_ok)

    expected_answer_mode = expected.get("answer_mode")
    checks["answer_mode"] = True if expected_answer_mode is None else answer_mode == expected_answer_mode

    required_domains = expected.get("required_domains") or []
    checks["required_domains"] = all(domain in source_domains for domain in required_domains)

    excluded_domains = expected.get("excluded_domains") or []
    checks["excluded_domains"] = all(domain not in source_domains for domain in excluded_domains)

    required_source_ids = expected.get("required_source_ids") or []
    checks["required_source_ids"] = all(source_id in source_ids for source_id in required_source_ids)

    required_bundle_counts = expected.get("required_bundle_counts") or {}
    checks["required_bundle_counts"] = all(
        _bundle_count_for_domain(body, domain) >= count
        for domain, count in required_bundle_counts.items()
    )

    should_have_citations = expected.get("should_have_citations")
    checks["citations_present"] = True if should_have_citations is None else ((len(citations) > 0) == bool(should_have_citations))

    followup_ready = expected.get("followup_ready")
    checks["followup_ready"] = True if followup_ready is None else (_conversation_followup_ready(body) == bool(followup_ready))

    required_anchor_domains = expected.get("required_anchor_domains") or []
    active_anchor_refs = composition_followup.get("active_anchor_refs") or []
    checks["required_anchor_domains"] = all(
        any(isinstance(anchor_ref, str) and anchor_ref.startswith(f"{domain}:") for anchor_ref in active_anchor_refs)
        for domain in required_anchor_domains
    )

    expected_abstention_reason = expected.get("abstention_reason_code")
    actual_abstention_reason = (composition.get("abstention") or {}).get("reason_code")
    checks["abstention_reason_code"] = True if expected_abstention_reason is None else actual_abstention_reason == expected_abstention_reason

    expected_warning = expected.get("required_warning")
    checks["required_warning"] = True if expected_warning is None else expected_warning in warnings

    answer_kind = expected.get("answer_kind")
    if answer_kind == "nonempty":
        checks["answer_quality"] = _has_nonempty_answer_text(body)
    elif answer_kind == "empty":
        checks["answer_quality"] = not _has_nonempty_answer_text(body)
    else:
        checks["answer_quality"] = True

    expected_public_scope = expected.get("public_scope")
    actual_public_scope = composition_policy.get("public_scope")
    checks["public_scope"] = True if expected_public_scope is None else actual_public_scope == expected_public_scope

    expected_render_mode = expected.get("render_mode")
    actual_render_mode = _render_mode(body)
    checks["render_mode"] = True if expected_render_mode is None else actual_render_mode == expected_render_mode

    answer_min_length = expected.get("answer_min_length")
    checks["answer_min_length"] = True if answer_min_length is None else _answer_length(body) >= int(answer_min_length)

    for name, passed in checks.items():
        if not passed:
            failure_reasons.append(name)

    return CaseResult(
        case_id=case["case_id"],
        category=case["category"],
        query=case["query"],
        passed=all(checks.values()),
        checks=checks,
        response=body,
        failure_reasons=failure_reasons,
    )


def summarize_results(suite: dict[str, Any], results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.passed)

    def rate(numerator: int, denominator: int) -> float:
        return 1.0 if denominator == 0 else numerator / denominator

    cases = suite["cases"]
    expected_by_id = {case["case_id"]: case["expected"] for case in cases}

    answered_cases = [r for r in results if expected_by_id[r.case_id].get("terminal_state") == "answered"]
    clarify_cases = [r for r in results if expected_by_id[r.case_id].get("terminal_state") == "clarify"]
    abstain_cases = [r for r in results if expected_by_id[r.case_id].get("terminal_state") == "abstain"]
    followup_cases = [r for r in results if expected_by_id[r.case_id].get("followup_ready") is True]
    comparative_tafsir_cases = [r for r in results if (expected_by_id[r.case_id].get("required_bundle_counts") or {}).get("tafsir", 0) >= 3]

    metrics = {
        "overall_pass_rate": rate(passed, total),
        "answered_rate": rate(sum(r.checks["terminal_state"] for r in answered_cases), len(answered_cases)),
        "clarify_rate": rate(sum(r.checks["terminal_state"] for r in clarify_cases), len(clarify_cases)),
        "abstain_rate": rate(sum(r.checks["terminal_state"] for r in abstain_cases), len(abstain_cases)),
        "followup_ready_rate": rate(sum(r.checks["followup_ready"] for r in followup_cases), len(followup_cases)),
        "comparative_tafsir_rate": rate(sum(r.checks["required_bundle_counts"] for r in comparative_tafsir_cases), len(comparative_tafsir_cases)),
        "unexpected_error_rate": rate(sum(not r.checks["ok"] for r in results if expected_by_id[r.case_id].get("ok") is True), len([r for r in results if expected_by_id[r.case_id].get("ok") is True])),
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
    base = build_base_markdown_report(
        {
            "suite_id": summary["suite_id"],
            "total_cases": summary["total_cases"],
            "passed_cases": summary["passed_cases"],
            "failed_cases": summary["failed_cases"],
            "overall_pass_rate": summary["overall_pass_rate"],
            "all_gates_passed": summary["all_gates_passed"],
            "metrics": {
                "quran_resolution_rate": summary["metrics"]["answered_rate"],
                "tafsir_inclusion_rate": summary["metrics"]["comparative_tafsir_rate"],
                "citation_presence_rate": summary["metrics"]["followup_ready_rate"],
                "abstention_rate": summary["metrics"]["abstain_rate"],
                "unexpected_error_rate": summary["metrics"]["unexpected_error_rate"],
            },
            "gates": summary["gates"],
            "failures": summary["failures"],
        }
    )
    extra = [
        "",
        "## MVP Metrics",
        "",
        f"- Answered rate: {summary['metrics']['answered_rate'] * 100:.1f}%",
        f"- Clarify rate: {summary['metrics']['clarify_rate'] * 100:.1f}%",
        f"- Follow-up ready rate: {summary['metrics']['followup_ready_rate'] * 100:.1f}%",
        f"- Comparative tafsir rate: {summary['metrics']['comparative_tafsir_rate'] * 100:.1f}%",
    ]
    return base.rstrip() + "\n" + "\n".join(extra) + "\n"


def run_suite(suite: dict[str, Any], client: Any) -> tuple[list[CaseResult], dict[str, Any]]:
    endpoint = suite["endpoint"]["path"]
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
