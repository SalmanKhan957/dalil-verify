from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from tests.support.sqlite_shared import create_shared_sqlite_memory_engine

from apps.ask_api.main import app
from domains.hadith.types import HadithCollectionSeed, NormalizedHadithBook, NormalizedHadithChapter, NormalizedHadithEntry
from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
from infrastructure.db.base import Base


@pytest.mark.anyio
async def test_ask_route_returns_explicit_hadith_reference_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_shared_sqlite_memory_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        repository = SqlAlchemyHadithRepository(session)
        collection = repository.upsert_collection(HadithCollectionSeed(
            source_domain='hadith',
            work_slug='sahih-al-bukhari-en',
            source_id='hadith:sahih-al-bukhari-en',
            display_name='Sahih al-Bukhari',
            citation_label='Sahih al-Bukhari',
            author_name='Imam Muhammad ibn Ismail al-Bukhari',
            language_code='en',
            source_kind='hadith_collection',
            upstream_provider='bootstrap_mirror',
            upstream_resource_id=None,
            enabled=True,
            approved_for_answering=False,
            metadata_json={'citation_quality': {'book_hadith': 'bootstrap_unverified'}},
        ))
        book, _ = repository.upsert_book(work_id=collection.id, book=NormalizedHadithBook(
            collection_source_id='hadith:sahih-al-bukhari-en',
            canonical_book_id='hadith:sahih-al-bukhari-en:book:1',
            book_number=1,
            upstream_book_id=1,
            title_en='Revelation',
            title_ar='كتاب بدء الوحى',
        ))
        chapter, _ = repository.upsert_chapter(work_id=collection.id, book_id=book.id, chapter=NormalizedHadithChapter(
            collection_source_id='hadith:sahih-al-bukhari-en',
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id='hadith:sahih-al-bukhari-en:book:1:chapter:1',
            book_number=1,
            chapter_number=1,
            upstream_book_id=1,
            upstream_chapter_id=1,
            title_en='How the Divine Inspiration started',
            title_ar='بدء الوحي',
        ))
        repository.upsert_entry(work_id=collection.id, book_id=book.id, chapter_id=chapter.id, entry=NormalizedHadithEntry(
            collection_source_id='hadith:sahih-al-bukhari-en',
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:2',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:2',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:1',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:1',
            collection_slug='sahih-al-bukhari-en',
            collection_hadith_number=2,
            in_book_hadith_number=1,
            book_number=1,
            chapter_number=1,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id=chapter.canonical_chapter_id,
            upstream_entry_id=2,
            upstream_book_id=1,
            upstream_chapter_id=1,
            english_narrator="Narrated Abu Huraira:",
            english_text="Faith has over sixty branches...",
            arabic_text="الإيمان بضع وستون شعبة",
            narrator_chain_text=None,
            matn_text=None,
            metadata_json={},
            raw_json={'id': 2},
        ))
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.retrieval.citation_lookup.get_session', _fake_get_session)
    monkeypatch.setattr('domains.source_registry.db_registry.get_session', _fake_get_session)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post('/ask', json={'query': 'Bukhari 2'})
            explain_response = await client.post('/ask', json={'query': 'Explain Bukhari 2'})
            book_response = await client.post('/ask', json={'query': 'Bukhari book 1 hadith 1'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['route_type'] == 'explicit_hadith_reference'
    assert payload['answer_mode'] == 'hadith_text'
    assert payload['hadith_support']['canonical_ref'] == 'hadith:sahih-al-bukhari-en:2'
    assert payload['hadith_support']['numbering_quality'] == 'collection_number_stable'
    assert payload['source_policy']['hadith']['answer_capability'] == 'explicit_lookup_and_explain'
    assert payload['source_policy']['hadith']['public_response_scope'] == 'bounded_public_explicit_and_topical'
    assert payload['source_policy']['hadith']['selected_capability'] == 'explicit_lookup'
    assert payload['source_policy']['hadith']['request_mode'] == 'auto'
    assert payload['source_policy']['hadith']['mode_enforced'] is True
    assert payload['citations'][0]['source_domain'] == 'hadith'
    assert payload['orchestration'] is not None
    assert payload['orchestration']['plan']['domain_decisions'][2]['selected_capability'] == 'explicit_lookup'

    assert explain_response.status_code == 200
    explain_payload = explain_response.json()
    assert explain_payload['ok'] is True
    assert explain_payload['answer_mode'] == 'hadith_explanation'
    assert explain_payload['source_policy']['hadith']['selected_capability'] == 'explain_from_source'
    assert explain_payload['orchestration'] is not None
    assert explain_payload['orchestration']['answer']['blocks'][0]['block_type'] == 'hadith_explanation'

    assert book_response.status_code == 200
    book_payload = book_response.json()
    assert book_payload['ok'] is True
    assert 'hadith_bootstrap_numbering_unverified' in book_payload['warnings']


@pytest.mark.anyio
async def test_ask_route_wires_nested_hadith_mode_into_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_shared_sqlite_memory_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        repository = SqlAlchemyHadithRepository(session)
        repository.upsert_collection(HadithCollectionSeed(
            source_domain='hadith',
            work_slug='sahih-al-bukhari-en',
            source_id='hadith:sahih-al-bukhari-en',
            display_name='Sahih al-Bukhari',
            citation_label='Sahih al-Bukhari',
            author_name='Imam Muhammad ibn Ismail al-Bukhari',
            language_code='en',
            source_kind='hadith_collection',
            upstream_provider='bootstrap_mirror',
            upstream_resource_id=None,
            enabled=True,
            approved_for_answering=False,
            metadata_json={'citation_quality': {'book_hadith': 'bootstrap_unverified'}},
        ))
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.retrieval.citation_lookup.get_session', _fake_get_session)
    monkeypatch.setattr('domains.source_registry.db_registry.get_session', _fake_get_session)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post('/ask', json={
                'query': 'Explain Bukhari 2',
                'sources': {'hadith': {'mode': 'explicit_lookup_only', 'collection_ids': ['hadith:sahih-al-bukhari-en']}},
            })

    assert response.status_code == 200
    payload = response.json()
    assert payload['source_policy']['hadith']['request_mode'] == 'explicit_lookup_only'
    assert payload['source_policy']['hadith']['mode_enforced'] is True
    assert payload['orchestration']['request']['control_honesty']['sources']['hadith']['mode']['status'] == 'enforced'
