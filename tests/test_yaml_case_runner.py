from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

import apps.api.main as api_main

CASES_ROOT = Path(__file__).resolve().parent / "cases"
FUNCTIONAL_FILES = [
    "smoke.yml",
    "regression_core.yml",
    "whitespace.yml",
    "adversarial.yml",
]
PERF_FILE = "performance.yml"
API_FILE = "api_contract.yml"


def _load_yaml(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


@pytest.fixture(scope="module")
def client() -> TestClient:
    # Important: use TestClient as a context manager so FastAPI/Starlette
    # lifespan startup runs and the verifier corpus/indexes are initialized.
    with TestClient(api_main.app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _disable_jsonl_logging(monkeypatch: pytest.MonkeyPatch):
    # Keep file logging out of the critical path for test runs.
    if hasattr(api_main, "append_jsonl_log"):
        monkeypatch.setattr(api_main, "append_jsonl_log", lambda *args, **kwargs: None)


FUNCTIONAL_CASES: list[dict[str, Any]] = []
for name in FUNCTIONAL_FILES:
    for row in _load_yaml(CASES_ROOT / name):
        row = dict(row)
        row["__file__"] = name
        FUNCTIONAL_CASES.append(row)


@pytest.mark.parametrize(
    "case",
    FUNCTIONAL_CASES,
    ids=[f"{row['__file__']}::{row['id']}" for row in FUNCTIONAL_CASES],
)
def test_functional_yaml_cases(client: TestClient, case: dict[str, Any]):
    response = client.post("/verify/quran", json={"text": case["input_text"]})
    assert response.status_code == 200, f"{case['description']}\nbody={response.text}"
    data = response.json()
    expected = case.get("expected", {})

    if "preferred_lane" in expected:
        assert data.get("preferred_lane") == expected["preferred_lane"], case["description"]
    if "match_status" in expected:
        assert data.get("match_status") == expected["match_status"], case["description"]
    for forbidden_status in expected.get("forbid_match_statuses", []):
        assert data.get("match_status") != forbidden_status, case["description"]

    if "confidence" in expected:
        assert data.get("confidence") == expected["confidence"], case["description"]
    for forbidden_confidence in expected.get("forbid_confidences", []):
        assert data.get("confidence") != forbidden_confidence, case["description"]

    best_match = data.get("best_match")
    if "best_citation" in expected:
        assert best_match is not None, case["description"]
        assert best_match.get("citation") == expected["best_citation"], case["description"]

    if "best_window_size" in expected:
        assert best_match is not None, case["description"]
        assert best_match.get("window_size") == expected["best_window_size"], case["description"]

    if "english_translation" in expected:
        english = (best_match or {}).get("english_translation")
        if expected["english_translation"] is True:
            assert english is not None and english.get("text"), case["description"]
        else:
            assert english in (None, {}), case["description"]

    for forbidden_citation in expected.get("forbid_best_citations", []):
        if best_match is not None:
            assert best_match.get("citation") != forbidden_citation, case["description"]


API_CASES = _load_yaml(CASES_ROOT / API_FILE)


@pytest.mark.parametrize("case", API_CASES, ids=[row["id"] for row in API_CASES])
def test_api_contract_yaml_cases(client: TestClient, case: dict[str, Any]):
    qs = case.get("query_string")
    url = "/verify/quran" if not qs else f"/verify/quran?{qs}"
    response = client.post(url, json=case.get("request", {}))
    expected = case.get("expected", {})

    assert response.status_code == expected["status_code"], f"{case['description']}\nbody={response.text}"

    if response.status_code == 200:
        data = response.json()
        if "best_citation" in expected:
            assert data.get("best_match", {}).get("citation") == expected["best_citation"], case["description"]
        for forbidden_status in expected.get("forbid_match_statuses", []):
            assert data.get("match_status") != forbidden_status, case["description"]
        if "debug_present" in expected:
            if expected["debug_present"]:
                assert data.get("debug") is not None, case["description"]
            else:
                assert data.get("debug") in (None, {}), case["description"]


PERF_CASES = _load_yaml(CASES_ROOT / PERF_FILE)


@pytest.mark.parametrize("case", PERF_CASES, ids=[row["id"] for row in PERF_CASES])
def test_performance_yaml_cases(client: TestClient, case: dict[str, Any]):
    response = client.post("/verify/quran?debug=true", json={"text": case["input_text"]})
    assert response.status_code == 200, f"{case['description']}\nbody={response.text}"
    data = response.json()
    expected = case.get("expected", {})
    perf = case.get("performance", {})

    if "best_citation" in expected:
        assert data.get("best_match", {}).get("citation") == expected["best_citation"], case["description"]
    if "preferred_lane" in expected:
        assert data.get("preferred_lane") == expected["preferred_lane"], case["description"]

    debug = data.get("debug") or {}
    stage_timings = debug.get("stage_timings") or {}
    request_total_ms = stage_timings.get("request_total_ms")
    assert request_total_ms is not None, f"No request_total_ms in debug for {case['id']}"

    max_request_total_ms = perf.get("max_request_total_ms")
    if max_request_total_ms is not None:
        assert request_total_ms <= max_request_total_ms, (
            f"{case['id']} exceeded threshold: {request_total_ms}ms > {max_request_total_ms}ms"
        )
