import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_ask_api_health_and_openapi_contract():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            openapi = await client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json()["service"] == "dalil-ask-api"

    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/ask" in paths
    assert "/ask/explain" in paths
    assert "/verify/quran" not in paths
