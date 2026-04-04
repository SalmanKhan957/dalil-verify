import httpx
import pytest

from apps.public_api.main import app


@pytest.mark.anyio
async def test_public_api_route_tags_and_basic_contracts():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            openapi = await client.get("/openapi.json")
            verify = await client.post("/verify/quran", json={"text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"})
            explain = await client.post("/ask/explain", json={"query": "94:5-6"})

    assert openapi.status_code == 200
    schema = openapi.json()
    assert schema["info"]["title"] == "Dalil Public API"
    assert "verifier" in {tag["name"] for tag in schema.get("tags", [])} or "/verify/quran" in schema["paths"]

    assert verify.status_code == 200
    verify_payload = verify.json()
    assert verify_payload["best_match"]["citation"] == "Quran 1:1"

    assert explain.status_code == 200
    explain_payload = explain.json()
    assert explain_payload["ok"] is True
    assert explain_payload["resolution"]["canonical_source_id"] == "quran:94:5-6"
