from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_ask_route_accepts_tafsir_controls_without_breaking_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.ask_api.routes.ask as ask_route_module

    captured: dict[str, object] = {}

    def _fake_dispatch(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {
            "ok": True,
            "query": query,
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "route": {"route_type": "explicit_quran_reference", "action_type": "explain"},
            "answer_mode": "quran_with_tafsir",
            "answer_text": "Answer",
            "citations": [],
            "quran_support": None,
            "tafsir_support": [],
            "resolution": None,
            "partial_success": False,
            "warnings": [],
            "quran_source_selection": None,
            "debug": None,
            "result": {"answer_mode": "quran_with_tafsir"},
            "error": None,
        }

    monkeypatch.setattr(ask_route_module, "dispatch_ask_query", _fake_dispatch)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask",
                json={
                    "query": "Tafsir of Surah Ikhlas",
                    "include_tafsir": True,
                    "tafsir_source_id": "tafsir:ibn-kathir-en",
                    "tafsir_limit": 2,
                },
            )

    assert response.status_code == 200
    assert captured["query"] == "Tafsir of Surah Ikhlas"
    assert captured["include_tafsir"] is True
    assert captured["tafsir_source_id"] == "tafsir:ibn-kathir-en"
    assert captured["tafsir_limit"] == 2


@pytest.mark.anyio
async def test_explain_route_is_compatibility_alias_over_dispatch_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.ask_api.routes.explain as explain_route_module

    def _fake_dispatch(query: str, **kwargs):
        return {
            "ok": True,
            "query": query,
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "route": {"route_type": "explicit_quran_reference", "action_type": "explain"},
            "answer_mode": "quran_explanation",
            "answer_text": "Answer",
            "citations": [],
            "quran_support": None,
            "tafsir_support": [],
            "resolution": {"canonical_source_id": "quran:112:1-2"},
            "partial_success": False,
            "warnings": [],
            "quran_source_selection": None,
            "debug": None,
            "result": {"answer_text": "Answer"},
            "error": None,
        }

    monkeypatch.setattr(explain_route_module, "dispatch_ask_query", _fake_dispatch)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={
                    "query": "112:1-2",
                    "include_tafsir": False,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert "route" not in payload
    assert "result" not in payload
    assert payload["answer_mode"] == "quran_explanation"
    assert payload["resolution"]["canonical_source_id"] == "quran:112:1-2"


@pytest.mark.anyio
async def test_explain_route_omitted_include_tafsir_defaults_true_for_compatibility(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.ask_api.routes.explain as explain_route_module

    captured: dict[str, object] = {}

    def _fake_dispatch(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {
            "ok": True,
            "query": query,
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "route": {"route_type": "explicit_quran_reference", "action_type": "explain"},
            "answer_mode": "quran_with_tafsir",
            "answer_text": "Answer",
            "citations": [],
            "quran_support": None,
            "tafsir_support": [],
            "resolution": None,
            "partial_success": False,
            "warnings": [],
            "quran_source_selection": None,
            "debug": None,
            "result": {"answer_mode": "quran_with_tafsir"},
            "error": None,
        }

    monkeypatch.setattr(explain_route_module, "dispatch_ask_query", _fake_dispatch)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={
                    "query": "Tafsir of Surah Ikhlas",
                },
            )

    assert response.status_code == 200
    assert captured["query"] == "Tafsir of Surah Ikhlas"
    assert captured["include_tafsir"] is True
