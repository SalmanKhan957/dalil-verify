from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_explain_route_rejects_invalid_translation_source_override() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={
                    "query": "112:1-4",
                    "include_tafsir": False,
                    "quran_translation_source_id": "hadith:sahih-bukhari-en",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["route_type"] == "explicit_quran_reference"
    assert body["action_type"] == "explain"
    assert body["warnings"] == ["requested_quran_translation_source_override_rejected"]
    assert "translation source" in body["error"]


@pytest.mark.anyio
async def test_ask_route_rejects_invalid_translation_source_override() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask",
                json={
                    "query": "112:1-4",
                    "quran_translation_source_id": "hadith:sahih-bukhari-en",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["route_type"] == "explicit_quran_reference"
    assert body["action_type"] == "explain"
    assert body["result"]["warnings"] == ["requested_quran_translation_source_override_rejected"]
    assert "translation source" in body["result"]["error"]
