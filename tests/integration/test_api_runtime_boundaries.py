import httpx
import pytest

from apps.ask_api.main import app as ask_app
from apps.public_api.main import app as public_app
from apps.verifier_api.main import app as verifier_app
from services.quran_runtime import bootstrap as runtime_bootstrap


async def _request_json(app, method: str, url: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, url, **kwargs)
    return response


@pytest.mark.anyio
async def test_shared_runtime_bootstrap_is_loaded_once_across_apps():
    runtime_bootstrap.refresh_runtime_state()
    first_count = int(runtime_bootstrap.RUNTIME_BOOT_INFO["load_count"])

    async with ask_app.router.lifespan_context(ask_app):
        pass
    async with public_app.router.lifespan_context(public_app):
        pass
    async with verifier_app.router.lifespan_context(verifier_app):
        pass

    assert runtime_bootstrap.runtime_state_loaded() is True
    assert int(runtime_bootstrap.RUNTIME_BOOT_INFO["load_count"]) == first_count


@pytest.mark.anyio
async def test_public_api_openapi_contains_verifier_and_ask_routes():
    async with public_app.router.lifespan_context(public_app):
        response = await _request_json(public_app, "GET", "/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/verify/quran" in paths
    assert "/ask" in paths
    assert "/ask/explain" in paths


@pytest.mark.anyio
async def test_public_api_health_reports_loaded_runtime():
    async with public_app.router.lifespan_context(public_app):
        response = await _request_json(public_app, "GET", "/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["simple_runtime_loaded"] is True
    assert payload["english_translation_loaded"] is True
    assert payload["simple_quran_rows_loaded"] > 0


@pytest.mark.anyio
async def test_ask_api_supports_explicit_reference_and_arabic_quote_lanes():
    async with ask_app.router.lifespan_context(ask_app):
        explicit = await _request_json(ask_app, "POST", "/ask", json={"query": "What does 94:5-6 say?"})
        arabic = await _request_json(ask_app, "POST", "/ask", json={"query": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"})

    assert explicit.status_code == 200
    explicit_payload = explicit.json()
    assert explicit_payload["ok"] is True
    assert explicit_payload["route_type"] == "explicit_quran_reference"
    assert explicit_payload["result"]["quran_span"]["citation_string"] == "Quran 94:5-6"

    assert arabic.status_code == 200
    arabic_payload = arabic.json()
    assert arabic_payload["ok"] is True
    assert arabic_payload["route_type"] == "arabic_quran_quote"
    assert arabic_payload["result"]["verifier_result"]["best_match"]["canonical_source_id"] == "quran:1:1:ar"


@pytest.mark.anyio
async def test_ask_api_abstains_cleanly_on_unsupported_query():
    async with ask_app.router.lifespan_context(ask_app):
        response = await _request_json(ask_app, "POST", "/ask", json={"query": "What does Islam say about anxiety?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["route_type"] == "policy_restricted_request"
    assert payload["error"]


@pytest.mark.anyio
async def test_public_api_handles_verifier_and_ask_lanes_together():
    async with public_app.router.lifespan_context(public_app):
        verify = await _request_json(public_app, "POST", "/verify/quran", json={"text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"})
        explain = await _request_json(public_app, "POST", "/ask", json={"query": "Explain 94:5-6"})

    assert verify.status_code == 200
    assert verify.json()["best_match"]["canonical_source_id"] == "quran:1:1:ar"

    assert explain.status_code == 200
    explain_payload = explain.json()
    assert explain_payload["route_type"] == "explicit_quran_reference"
    assert explain_payload["result"]["resolution"]["canonical_source_id"] == "quran:94:5-6"


@pytest.mark.anyio
async def test_verifier_api_is_verifier_only_and_reports_health():
    async with verifier_app.router.lifespan_context(verifier_app):
        health = await _request_json(verifier_app, "GET", "/health")
        verify = await _request_json(verifier_app, "POST", "/verify/quran", json={"text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"})
        ask = await _request_json(verifier_app, "POST", "/ask", json={"query": "Explain 94:5-6"})

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert verify.status_code == 200
    assert verify.json()["best_match"]["canonical_source_id"] == "quran:1:1:ar"
    assert ask.status_code == 404
