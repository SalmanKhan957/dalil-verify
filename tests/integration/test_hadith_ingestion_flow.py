from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domains.hadith.citations.parser import parse_hadith_citation
from domains.hadith.ingestion.ingest_collection import HadithCollectionIngestionService
from domains.hadith.ingestion.normalizer import HadithCollectionNormalizer
from domains.hadith.retrieval.citation_lookup import HadithCitationLookupService
from infrastructure.db.base import Base


HADITH_PAYLOAD = {
    'id': 1,
    'metadata': {
        'length': 2,
        'arabic': {'title': 'صحيح البخاري', 'author': 'الإمام البخاري'},
        'english': {'title': 'Sahih al-Bukhari', 'author': 'Imam al-Bukhari'},
    },
    'chapters': [
        {'id': 11, 'bookId': 1, 'arabic': 'بدء الوحي', 'english': 'Revelation'},
        {'id': 12, 'bookId': 1, 'arabic': 'الإيمان', 'english': 'Faith'},
    ],
    'hadiths': [
        {
            'id': 1,
            'idInBook': 1,
            'arabic': 'حَدَّثَنَا ...',
            'english': {'narrator': 'Narrated Umar bin Al-Khattab:', 'text': "I heard Allah's Messenger say..."},
            'chapterId': 11,
            'bookId': 1,
        },
        {
            'id': 2,
            'idInBook': 1,
            'arabic': 'حَدَّثَنَا ... ٢',
            'english': {'narrator': 'Narrated Abu Huraira:', 'text': 'Faith has over sixty branches...'},
            'chapterId': 12,
            'bookId': 1,
        },
    ],
}


def test_hadith_ingestion_and_lookup_flow(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.ingestion.ingest_collection.get_session', _fake_get_session)
    monkeypatch.setattr('domains.hadith.retrieval.citation_lookup.get_session', _fake_get_session)
    monkeypatch.setattr('domains.source_registry.db_registry.get_session', _fake_get_session)

    summary = HadithCollectionIngestionService(normalizer=HadithCollectionNormalizer()).ingest_payload(HADITH_PAYLOAD)
    assert summary.status == 'completed'
    assert summary.books_seen == 1
    assert summary.chapters_seen == 2
    assert summary.entries_seen == 2

    citation = parse_hadith_citation('Sahih Bukhari 2')
    lookup = HadithCitationLookupService().lookup(citation)
    assert lookup.resolved is True
    assert lookup.entry is not None
    assert lookup.entry.canonical_ref_collection == 'hadith:sahih-al-bukhari-en:2'
    assert lookup.entry.english_text == 'Faith has over sixty branches...'

    book_citation = parse_hadith_citation('Bukhari book 1 hadith 1')
    book_lookup = HadithCitationLookupService().lookup(book_citation)
    assert book_lookup.resolved is True
    assert 'hadith_bootstrap_numbering_unverified' in book_lookup.warnings
    assert book_lookup.entry is not None
    assert book_lookup.entry.book_number == 1
