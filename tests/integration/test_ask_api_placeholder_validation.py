from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_ask_route_rejects_openapi_placeholder_source_override() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask",
                json={
                    "query": "Tafsir of Surah Ikhlas",
                    "quran_text_source_id": "string",
                    "include_tafsir": True,
                },
            )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("OpenAPI placeholder" in item["msg"] for item in detail)


@pytest.mark.anyio
async def test_explain_route_rejects_openapi_placeholder_source_override() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={
                    "query": "Tafsir of Surah Ikhlas",
                    "quran_text_source_id": "string",
                    "include_tafsir": True,
                },
            )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("OpenAPI placeholder" in item["msg"] for item in detail)


@pytest.mark.anyio
async def test_openapi_examples_do_not_encourage_placeholder_source_ids() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]

    ask_examples = schemas["AskRequest"]["examples"]
    explain_examples = schemas["ExplainQuranReferenceRequest"]["examples"]

    for example in ask_examples + explain_examples:
        assert example.get("quran_text_source_id") != "string"
        assert example.get("quran_translation_source_id") != "string"
        assert example.get("tafsir_source_id") != "string"
