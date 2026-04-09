from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from tests.support.sqlite_shared import create_shared_sqlite_memory_engine

from apps.ask_api.main import app
from domains.hadith.ingestion.ingest_collection import HadithCollectionIngestionService
from domains.hadith.ingestion.normalizer_meeatif import MeeAtifHadithCollectionNormalizer
from infrastructure.db.base import Base


@pytest.mark.anyio
async def test_ask_route_resolves_collection_number_from_meeatif_reference_url(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_shared_sqlite_memory_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    payload = [
        {
            'Book': 'Sahih al-Bukhari',
            'Chapter_Number': 64,
            'Chapter_Title_Arabic': 'كتاب المغازي',
            'Chapter_Title_English': 'Military Expeditions led by the Prophet (pbuh) (Al-Maghaazi)',
            'Arabic_Text': 'حَدَّثَنَا ...',
            'English_Text': 'Narrated Example: Example matn for explicit lookup.',
            'Grade': '',
            'Reference': 'https://sunnah.com/bukhari:4161',
            'In-book reference': 'Book 64, Hadith 188',
        }
    ]

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.ingestion.ingest_collection.get_session', _fake_get_session)
    monkeypatch.setattr('domains.hadith.retrieval.citation_lookup.get_session', _fake_get_session)
    monkeypatch.setattr('domains.source_registry.db_registry.get_session', _fake_get_session)

    service = HadithCollectionIngestionService(
        normalizer=MeeAtifHadithCollectionNormalizer(),
        replace_existing_work_data=False,
    )
    service.ingest_payload(payload, source_root='test_payload')

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'Bukhari 4161'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['route_type'] == 'explicit_hadith_reference'
    assert payload['answer_mode'] == 'hadith_text'
    assert payload['hadith_support']['collection_hadith_number'] == 4161
    assert payload['hadith_support']['reference_url'] == 'https://sunnah.com/bukhari:4161'
    assert payload['hadith_support']['in_book_reference_text'] == 'Book 64, Hadith 188'
    assert payload['hadith_support']['book_number'] == 64
    assert payload['hadith_support']['chapter_number'] is None
    assert payload['hadith_support']['numbering_quality'] == 'collection_number_stable'
