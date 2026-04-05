from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_explain_route_surfaces_quran_source_selection_for_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DALIL_QURAN_REPOSITORY_MODE", "csv")
    monkeypatch.delenv("DALIL_DATABASE_URL", raising=False)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={
                    "query": "112:1-2",
                    "include_tafsir": False,
                    "quran_text_source_id": "quran:tanzil-simple",
                    "quran_translation_source_id": "quran:towards-understanding-en",
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["quran_support"]["quran_source_id"] == "quran:tanzil-simple"
    assert payload["quran_support"]["translation_source_id"] == "quran:towards-understanding-en"
    assert payload["quran_source_selection"] == {
        "repository_mode": "csv",
        "source_resolution_strategy": "registry",
        "requested_quran_text_source_id": "quran:tanzil-simple",
        "requested_quran_translation_source_id": "quran:towards-understanding-en",
        "selected_quran_text_source_id": "quran:tanzil-simple",
        "selected_quran_translation_source_id": "quran:towards-understanding-en",
    }


@pytest.mark.anyio
async def test_ask_route_surfaces_quran_source_selection_for_rejected_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DALIL_QURAN_REPOSITORY_MODE", raising=False)
    monkeypatch.delenv("DALIL_DATABASE_URL", raising=False)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask",
                json={
                    "query": "112:1-2",
                    "quran_translation_source_id": "quran:not-approved",
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    result = payload["result"]
    assert result["warnings"] == ["requested_quran_translation_source_override_rejected"]
    assert result["quran_source_selection"] == {
        "repository_mode": None,
        "source_resolution_strategy": "selection_error",
        "requested_quran_text_source_id": "quran:tanzil-simple",
        "requested_quran_translation_source_id": "quran:not-approved",
        "selected_quran_text_source_id": None,
        "selected_quran_translation_source_id": None,
    }
