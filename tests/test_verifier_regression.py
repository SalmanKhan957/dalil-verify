from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'verifier_regression_cases.json'


def _noop_log(*args, **kwargs):
    return None


def _load_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)


CASES = _load_cases()


@pytest.fixture(scope='module')
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_verifier_regression_cases(monkeypatch, client: TestClient, case: dict[str, Any]):
    monkeypatch.setattr('apps.api.main.append_jsonl_log', _noop_log)

    debug = bool(case.get('request_debug', False))
    url = '/verify/quran?debug=true' if debug else '/verify/quran'
    response = client.post(url, json={'text': case['query']})

    assert response.status_code == case.get('expected_status_code', 200), case['description']
    data = response.json()

    if 'expected_preferred_lane' in case:
        assert data['preferred_lane'] == case['expected_preferred_lane'], case['description']
    if 'expected_preferred_lane_not' in case:
        assert data['preferred_lane'] != case['expected_preferred_lane_not'], case['description']

    if 'expected_match_status' in case:
        assert data['match_status'] == case['expected_match_status'], case['description']
    for forbidden_status in case.get('forbid_match_statuses', []):
        assert data['match_status'] != forbidden_status, case['description']

    if 'expected_confidence' in case:
        assert data['confidence'] == case['expected_confidence'], case['description']

    best_match = data.get('best_match')
    expected_best_citation = case.get('expected_best_citation', '__missing__')
    if expected_best_citation != '__missing__':
        if expected_best_citation is None:
            assert best_match is None, case['description']
        else:
            assert best_match is not None, case['description']
            assert best_match.get('citation') == expected_best_citation, case['description']

    if best_match is not None:
        if 'expected_best_window_size' in case:
            assert best_match.get('window_size') == case['expected_best_window_size'], case['description']
        if 'expected_best_retrieval_engine' in case:
            assert best_match.get('retrieval_engine') == case['expected_best_retrieval_engine'], case['description']

        if case.get('expect_english_translation') is True:
            english = best_match.get('english_translation')
            assert english is not None, case['description']
            assert english.get('text'), case['description']
        elif case.get('expect_english_translation') is False:
            assert best_match.get('english_translation') in (None, {}), case['description']

    forbidden_citations = set(case.get('forbid_best_citations', []))
    if best_match is not None and forbidden_citations:
        assert best_match.get('citation') not in forbidden_citations, case['description']

    related_citations = {item.get('citation') for item in data.get('also_related', []) if item.get('citation')}
    for forbidden_related in case.get('expected_absent_related_citations', []):
        assert forbidden_related not in related_citations, case['description']

    expected_debug_sanitized = case.get('expected_debug_query_sanitized', None)
    if expected_debug_sanitized is not None:
        debug_data = data.get('debug')
        assert debug_data is not None, case['description']
        preprocessing = debug_data.get('query_preprocessing') or {}
        assert preprocessing.get('was_sanitized') is expected_debug_sanitized, case['description']
