from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app
from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord


@pytest.mark.anyio
async def test_ask_route_surfaces_hadith_topical_v2_shadow_diagnostics_when_debug_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_hadith_search(self, *, query_text: str, collection_source_id: str | None = None, limit: int = 5):
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

    class _ShadowResult:
        abstain = False
        abstain_reason = None
        warnings = ()
        debug = {'shadow': True}
        selected = [type('Candidate', (), {'canonical_ref': 'hadith:sahih-al-bukhari-en:10'})()]

    def _fake_shadow_search(self, *, raw_query: str, collection_source_id: str | None = None, limit: int = 3, lexical_hits=None, language_hint: str | None = None):
        return _ShadowResult()

    monkeypatch.setattr('domains.hadith_topical.search_service.HadithTopicalSearchService.search', _fake_shadow_search)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'Give me hadith about patience', 'debug': True})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is False
    assert payload['answer_mode'] == 'abstain'
    assert payload['error'] == 'policy_restricted'
    assert payload['hadith_support'] is None
    assert payload['debug']['runtime_diagnostics']['hadith']['topical_v2_shadow']['selected_refs'] == ['hadith:sahih-al-bukhari-en:10']
