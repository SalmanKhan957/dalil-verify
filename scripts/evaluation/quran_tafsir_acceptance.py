from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import urllib.request


@dataclass(slots=True)
class CaseResult:
    case_id: str
    category: str
    query: str
    passed: bool
    checks: dict[str, bool]
    response: dict[str, Any]
    failure_reasons: list[str]


class LocalAppClient:
    def __init__(self) -> None:
        from fastapi.testclient import TestClient
        from apps.public_api.main import app
        self._TestClient = TestClient
        self._app = app

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Use a context manager so FastAPI lifespan/startup hooks run reliably.
        with self._TestClient(self._app) as client:
            response = client.post(path, json=payload)
            return {"status_code": response.status_code, "json": response.json()}


class HttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            return {"status_code": response.getcode(), "json": json.loads(response.read().decode("utf-8"))}


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


def normalize_text(text: str | None) -> str:
    return " ".join((text or "").lower().split()).strip()


def normalize_body(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize /ask and /ask/explain payloads into one evaluation shape.

    /ask wraps the actual answer payload under `result`, while /ask/explain returns the
    answer payload at the top level. This helper lets the evaluator grade both without
    misreading a healthy response as a failure.
    """
    if isinstance(body.get("result"), dict):
        result = dict(body["result"])
        # Preserve top-level routing metadata if the nested payload omits it.
        result.setdefault("route_type", body.get("route_type"))
        result.setdefault("action_type", body.get("action_type"))
        result.setdefault("error", body.get("error"))
        return result
    return body


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> CaseResult:
    expected = case["expected"]
    body = normalize_body(response["json"])
    checks: dict[str, bool] = {}
    failure_reasons: list[str] = []

    route_type = body.get("route_type")
    action_type = body.get("action_type")
    resolution = body.get("resolution") or {}
    citations = body.get("citations") or []
    tafsir_support = body.get("tafsir_support") or []
    quran_support = body.get("quran_support") or {}
    answer_text = body.get("answer_text") or ""
    translation_text = (quran_support or {}).get("translation_text") or ""
    error = body.get("error")
    partial_success = bool(body.get("partial_success"))

    checks["route_type"] = route_type == expected["route_type"]
    checks["action_type"] = action_type == expected["action_type"]

    expected_canonical = expected.get("canonical_source_id")
    if expected_canonical is None:
        checks["canonical_source_id"] = True
    else:
        actual_canonical = resolution.get("canonical_source_id") or (quran_support or {}).get("canonical_source_id")
        checks["canonical_source_id"] = actual_canonical == expected_canonical

    should_abstain = bool(expected.get("should_abstain"))
    checks["abstention"] = ((not body.get("ok")) or route_type == "unsupported_for_now") if should_abstain else bool(body.get("ok"))

    should_have_citations = bool(expected.get("should_have_citations"))
    checks["citations_present"] = (len(citations) > 0) if should_have_citations else True

    should_include_tafsir = bool(expected.get("should_include_tafsir"))
    if should_include_tafsir:
        has_tafsir_citation = any((c.get("source_domain") == "tafsir") for c in citations)
        checks["tafsir_included"] = len(tafsir_support) > 0 and has_tafsir_citation
    else:
        checks["tafsir_included"] = len(tafsir_support) == 0

    if should_abstain:
        checks["unexpected_error"] = True
        checks["answer_quality"] = True
    else:
        checks["unexpected_error"] = not bool(error) and not partial_success
        normalized_answer = normalize_text(answer_text)
        normalized_translation = normalize_text(translation_text)
        checks["answer_quality"] = bool(normalized_answer) and normalized_answer not in {
            normalized_translation,
            normalize_text(f"{quran_support.get('citation_string', '')} says: {translation_text}"),
        }

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

    cases = suite["cases"]
    expected_by_id = {case["case_id"]: case["expected"] for case in cases}

    def rate(numerator: int, denominator: int) -> float:
        return 1.0 if denominator == 0 else numerator / denominator

    quran_cases = [r for r in results if expected_by_id[r.case_id].get("canonical_source_id")]
    tafsir_cases = [r for r in results if expected_by_id[r.case_id].get("should_include_tafsir")]
    citation_cases = [r for r in results if expected_by_id[r.case_id].get("should_have_citations")]
    abstain_cases = [r for r in results if expected_by_id[r.case_id].get("should_abstain")]

    quran_resolution_rate = rate(sum(r.checks["canonical_source_id"] for r in quran_cases), len(quran_cases))
    tafsir_inclusion_rate = rate(sum(r.checks["tafsir_included"] for r in tafsir_cases), len(tafsir_cases))
    citation_presence_rate = rate(sum(r.checks["citations_present"] for r in citation_cases), len(citation_cases))
    abstention_rate = rate(sum(r.checks["abstention"] for r in abstain_cases), len(abstain_cases))
    unexpected_error_rate = rate(sum(not r.checks["unexpected_error"] for r in results), len(results))
    overall_pass_rate = rate(passed, total)

    thresholds = suite["thresholds"]
    gates = {
        "quran_resolution_gate": quran_resolution_rate >= thresholds["quran_resolution_rate_min"],
        "tafsir_inclusion_gate": tafsir_inclusion_rate >= thresholds["tafsir_inclusion_rate_min"],
        "citation_presence_gate": citation_presence_rate >= thresholds["citation_presence_rate_min"],
        "abstention_gate": abstention_rate >= thresholds["abstention_rate_min"],
        "unexpected_error_gate": unexpected_error_rate <= thresholds["unexpected_error_rate_max"],
        "overall_pass_gate": overall_pass_rate >= thresholds["overall_pass_rate_min"],
    }

    return {
        "suite_id": suite["suite_id"],
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "overall_pass_rate": overall_pass_rate,
        "metrics": {
            "quran_resolution_rate": quran_resolution_rate,
            "tafsir_inclusion_rate": tafsir_inclusion_rate,
            "citation_presence_rate": citation_presence_rate,
            "abstention_rate": abstention_rate,
            "unexpected_error_rate": unexpected_error_rate,
        },
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
    metrics = summary["metrics"]
    gates = summary["gates"]
    lines = [
        f"# Acceptance Report — {summary['suite_id']}",
        "",
        f"- Total cases: {summary['total_cases']}",
        f"- Passed cases: {summary['passed_cases']}",
        f"- Failed cases: {summary['failed_cases']}",
        f"- Overall pass rate: {metrics_to_pct(summary['overall_pass_rate'])}",
        f"- All gates passed: {'yes' if summary['all_gates_passed'] else 'no'}",
        "",
        "## Metrics",
        "",
        f"- Quran resolution rate: {metrics_to_pct(metrics['quran_resolution_rate'])}",
        f"- Tafsir inclusion rate: {metrics_to_pct(metrics['tafsir_inclusion_rate'])}",
        f"- Citation presence rate: {metrics_to_pct(metrics['citation_presence_rate'])}",
        f"- Abstention rate: {metrics_to_pct(metrics['abstention_rate'])}",
        f"- Unexpected error rate: {metrics_to_pct(metrics['unexpected_error_rate'])}",
        "",
        "## Gates",
        "",
    ]
    for gate_name, passed in gates.items():
        lines.append(f"- {gate_name}: {'PASS' if passed else 'FAIL'}")

    if summary["failures"]:
        lines.extend(["", "## Failed Cases", ""])
        for failure in summary["failures"]:
            reasons = ", ".join(failure["failure_reasons"])
            lines.append(f"- `{failure['case_id']}` — {failure['query']} — {reasons}")

    return "\n".join(lines) + "\n"


def metrics_to_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def run_suite(suite: dict[str, Any], client: Any) -> tuple[list[CaseResult], dict[str, Any]]:
    endpoint = suite["endpoint"]["path"]
    results: list[CaseResult] = []
    for case in suite["cases"]:
        response = client.post(endpoint, case["request"])
        results.append(evaluate_case(case, response))
    return results, summarize_results(suite, results)
