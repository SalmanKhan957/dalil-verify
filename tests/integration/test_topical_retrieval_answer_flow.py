from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app
from domains.tafsir.types import TafsirLexicalHit


@pytest.mark.anyio
async def test_ask_route_abstains_for_public_topical_hadith_when_lane_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_hadith_search(*args, **kwargs):
        raise AssertionError('Topical hadith search should not be invoked when the public lane is disabled')

    monkeypatch.setattr('domains.hadith.service.HadithService.search_topically', _unexpected_hadith_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'Give me hadith about patience'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is False
    assert payload['route_type'] == 'topical_hadith_query'
    assert payload['answer_mode'] == 'abstain'
    assert payload['terminal_state'] == 'abstain'
    assert payload['hadith_support'] is None
    assert payload['source_policy']['hadith']['selected_capability'] == 'topical_retrieval'
    assert payload['source_policy']['hadith']['policy_reason'] == 'topical_hadith_temporarily_disabled'
    assert payload['source_policy']['hadith']['public_response_scope'] == 'bounded_public_explicit_and_explain'
    assert payload['answer_text'] == 'Topical Hadith answers are temporarily disabled in this release. Direct Hadith references such as “Bukhari 20” are still supported.'
    assert payload['error'] == 'policy_restricted'


@pytest.mark.anyio
async def test_ask_route_abstains_for_public_topical_tafsir_when_lane_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_tafsir_search(*args, **kwargs):
        raise AssertionError('Topical tafsir search should not be invoked when the public lane is disabled')

    monkeypatch.setattr('domains.tafsir.service.TafsirService.search_topically', _unexpected_tafsir_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'What does the Quran say about patience?'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is False
    assert payload['route_type'] == 'topical_tafsir_query'
    assert payload['answer_mode'] == 'abstain'
    assert payload['terminal_state'] == 'abstain'
    assert payload['tafsir_support'] == []
    assert payload['source_policy']['tafsir']['selected_capability'] == 'topical_retrieval'
    assert payload['source_policy']['tafsir']['policy_reason'] == 'topical_tafsir_temporarily_disabled'
    assert payload['answer_text'] == 'Topical Tafsir answers are temporarily disabled in this release. Explicit Quran requests such as “Explain 2:255” are still supported.'
    assert payload['error'] == 'policy_restricted'


@pytest.mark.anyio
async def test_ask_route_can_reenable_public_topical_tafsir_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_tafsir_search(self, *, query_text: str, source_id: str | None = None, surah_no: int | None = None, limit: int = 5):
        assert query_text == 'patience'
        return [
            TafsirLexicalHit(
                section_id=1,
                canonical_section_id='tafsir:ibn-kathir-en:1',
                work_id=1,
                source_id='tafsir:ibn-kathir-en',
                display_name='Tafsir Ibn Kathir (English)',
                citation_label='Tafsir Ibn Kathir',
                surah_no=2,
                ayah_start=153,
                ayah_end=153,
                anchor_verse_key='2:153',
                quran_span_ref='2:153',
                text_plain='Seek help through patience and prayer.',
                text_html='<p>Seek help through patience and prayer.</p>',
                score=0.91,
                matched_terms=('patience',),
                snippet='Seek help through patience and prayer.',
                retrieval_method='python_fallback',
            )
        ]

    from infrastructure.config.settings import settings

    monkeypatch.setattr(settings, 'public_topical_tafsir_enabled', True)
    monkeypatch.setattr('domains.tafsir.service.TafsirService.search_topically', _fake_tafsir_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'What does the Quran say about patience?'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['route_type'] == 'topical_tafsir_query'
    assert payload['answer_mode'] == 'topical_tafsir'
    assert payload['tafsir_support']
    assert payload['source_policy']['tafsir']['selected_capability'] == 'topical_retrieval'


@pytest.mark.anyio
async def test_ask_route_keeps_multi_source_topic_internal_until_later(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_tafsir_search(self, *, query_text: str, source_id: str | None = None, surah_no: int | None = None, limit: int = 5):
        return []

    def _fake_hadith_search(self, *, query_text: str, collection_source_id: str | None = None, limit: int = 5):
        return []

    monkeypatch.setattr('domains.tafsir.service.TafsirService.search_topically', _fake_tafsir_search)
    monkeypatch.setattr('domains.hadith.service.HadithService.search_topically', _fake_hadith_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'What does Islam say about patience?'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is False
    assert payload['route_type'] == 'policy_restricted_request'
