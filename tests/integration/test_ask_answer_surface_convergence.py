from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_ask_route_surfaces_answer_first_fields_without_hiding_legacy_result() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask",
                json={
                    "query": "What does 112:1-2 say?",
                    "quran_text_source_id": "quran:tanzil-simple",
                    "quran_translation_source_id": "quran:towards-understanding-en",
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["answer_mode"] in {"quran_text", "quran_explanation", "verification_then_explain", "quran_with_tafsir"}
    assert payload["answer_text"]
    assert payload["quran_support"]["citation_string"] == "Quran 112:1-2"
    assert payload["quran_source_selection"]["selected_quran_text_source_id"] == "quran:tanzil-simple"
    assert payload["quran_source_selection"]["selected_quran_translation_source_id"] == "quran:towards-understanding-en"
    assert payload["result"]["quran_support"]["citation_string"] == "Quran 112:1-2"


@pytest.mark.anyio
async def test_ask_route_surfaces_abstention_metadata_at_top_level() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/ask", json={"query": "Give me hadith about patience"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["route_type"] == "unsupported_for_now"
    assert payload["answer_mode"] == "abstain"
    assert payload["warnings"] == []
    assert payload["error"]
    assert payload["result"]["answer_mode"] == "abstain"
