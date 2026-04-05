from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_explain_route_surfaces_source_policy_for_tafsir_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DALIL_QURAN_REPOSITORY_MODE', 'csv')
    monkeypatch.delenv('DALIL_DATABASE_URL', raising=False)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post(
                '/ask/explain',
                json={
                    'query': 'Tafsir of Surah Ikhlas',
                    'include_tafsir': True,
                    'tafsir_limit': 2,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['source_policy']['quran']['allowed'] is True
    assert payload['source_policy']['quran']['text_source_origin'] == 'implicit_default'
    assert payload['source_policy']['quran']['translation_source_origin'] == 'implicit_default'
    assert payload['source_policy']['tafsir']['requested'] is True
    assert payload['source_policy']['tafsir']['request_origin'] == 'explicit_flag'
    assert payload['source_policy']['tafsir']['included'] is True
    assert payload['source_policy']['tafsir']['selected_source_id'] == 'tafsir:ibn-kathir-en'
    assert payload['source_policy']['tafsir']['policy_reason'] == 'selected'


@pytest.mark.anyio
async def test_ask_route_surfaces_source_policy_for_suppressed_tafsir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DALIL_QURAN_REPOSITORY_MODE', 'csv')
    monkeypatch.delenv('DALIL_DATABASE_URL', raising=False)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post(
                '/ask',
                json={
                    'query': 'Tafsir of Surah Ikhlas',
                    'include_tafsir': False,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['source_policy']['tafsir']['requested'] is False
    assert payload['source_policy']['tafsir']['request_origin'] == 'explicit_suppression'
    assert payload['source_policy']['tafsir']['included'] is False
    assert payload['source_policy']['tafsir']['policy_reason'] == 'suppressed_by_request'


@pytest.mark.anyio
async def test_ask_route_marks_explicit_quran_source_override_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DALIL_QURAN_REPOSITORY_MODE', 'csv')
    monkeypatch.delenv('DALIL_DATABASE_URL', raising=False)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post(
                '/ask',
                json={
                    'query': 'What does 112:1-4 say?',
                    'quran_text_source_id': 'quran:tanzil-simple',
                    'quran_translation_source_id': 'quran:towards-understanding-en',
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['source_policy']['quran']['text_source_origin'] == 'explicit_override'
    assert payload['source_policy']['quran']['translation_source_origin'] == 'explicit_override'
