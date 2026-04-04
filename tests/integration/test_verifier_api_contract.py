import httpx
import pytest

from apps.verifier_api.main import app


@pytest.mark.anyio
async def test_verifier_api_openapi_contract():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            openapi = await client.get("/openapi.json")

    assert health.status_code == 200
    payload = health.json()
    assert payload["service"] == "dalil-verify-api"
    assert payload["simple_runtime_loaded"] is True

    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/verify/quran" in paths
    assert "/ask" not in paths
