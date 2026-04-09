from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app
from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord
from domains.tafsir.types import TafsirLexicalHit


@pytest.mark.anyio
async def test_ask_route_returns_bounded_public_topical_hadith_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_hadith_search(self, *, query_text: str, collection_source_id: str | None = None, limit: int = 5):
        assert query_text == 'patience'
        entry = HadithEntryRecord(
            id=1,
            work_id=1,
            book_id=1,
            chapter_id=1,
            collection_source_id='hadith:sahih-al-bukhari-en',
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:10',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:10',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:10',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:10',
            collection_hadith_number=10,
            in_book_hadith_number=10,
            book_number=1,
            chapter_number=1,
            english_narrator='Narrated Abu Saeed:',
            english_text='No one is given a gift better and more comprehensive than patience.',
            arabic_text=None,
            narrator_chain_text=None,
            matn_text=None,
            metadata_json={},
            raw_json={'id': 10},
            grading=None,
        )
        return [
            HadithLexicalHit(
                entry=entry,
                display_name='Sahih al-Bukhari (English)',
                citation_label='Sahih al-Bukhari',
                book_title='Book of Patience',
                chapter_title='Patience',
                score=0.87,
                matched_terms=('patience',),
                snippet='No one is given a gift better and more comprehensive than patience.',
                retrieval_method='python_fallback',
            )
        ]

    monkeypatch.setattr('domains.hadith.service.HadithService.search_topically', _fake_hadith_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'Give me hadith about patience'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['route_type'] == 'topical_hadith_query'
    assert payload['answer_mode'] == 'topical_hadith'
    assert payload['hadith_support'] is not None
    assert payload['source_policy']['hadith']['selected_capability'] == 'topical_retrieval'


@pytest.mark.anyio
async def test_ask_route_returns_bounded_public_topical_tafsir_answer(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert payload['route_type'] == 'unsupported_for_now'


@pytest.mark.anyio
async def test_ask_route_abstains_on_weak_public_topical_hadith_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_hadith_search(self, *, query_text: str, collection_source_id: str | None = None, limit: int = 5):
        entry = HadithEntryRecord(
            id=1, work_id=1, book_id=1, chapter_id=1,
            collection_source_id='hadith:sahih-al-bukhari-en',
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:99',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:99',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:99',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:99',
            collection_hadith_number=99, in_book_hadith_number=99, book_number=1, chapter_number=1,
            english_narrator='Narrated Someone:', english_text='A weak lexical match.', arabic_text=None,
            narrator_chain_text=None, matn_text=None, metadata_json={}, raw_json={'id': 99}, grading=None,
        )
        return [HadithLexicalHit(entry=entry, display_name='Sahih al-Bukhari (English)', citation_label='Sahih al-Bukhari', book_title='Misc', chapter_title='Misc', score=0.2, matched_terms=('patience',), snippet='A weak lexical match.', retrieval_method='python_fallback')]

    class _ShadowAbstain:
        abstain = True
        abstain_reason = 'insufficient_ranked_evidence'
        warnings = ('no_ranked_candidate_passed_thresholds',)
        debug = {'shadow': True}
        selected = []

    def _fake_shadow_search(self, *, raw_query: str, collection_source_id: str | None = None, limit: int = 3, lexical_hits=None, language_hint: str | None = None):
        return _ShadowAbstain()

    monkeypatch.setattr('domains.hadith.service.HadithService.search_topically', _fake_hadith_search)
    monkeypatch.setattr('domains.hadith_topical.search_service.HadithTopicalSearchService.search', _fake_shadow_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'Give me hadith about patience'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is False
    assert payload['route_type'] == 'topical_hadith_query'
    assert payload['answer_mode'] == 'topical_hadith'
    assert payload['error'] == 'insufficient_evidence'
