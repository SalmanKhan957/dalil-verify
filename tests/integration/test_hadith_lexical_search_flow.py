import pytest
sqlalchemy = pytest.importorskip('sqlalchemy')

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domains.hadith.service import HadithService
from domains.hadith.types import HadithCollectionSeed, NormalizedHadithBook, NormalizedHadithChapter, NormalizedHadithEntry
from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
from infrastructure.db.base import Base


def test_hadith_service_topical_search_returns_ranked_hits(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
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
            author_name='Imam al-Bukhari',
            language_code='en',
            source_kind='hadith_collection',
            upstream_provider='bootstrap_mirror',
            upstream_resource_id=None,
            enabled=True,
            approved_for_answering=False,
            metadata_json={},
        ))
        book, _ = repository.upsert_book(work_id=collection.id, book=NormalizedHadithBook(
            collection_source_id=collection.source_id,
            canonical_book_id='hadith:sahih-al-bukhari-en:book:1',
            book_number=1,
            upstream_book_id=1,
            title_en='Revelation',
            title_ar=None,
        ))
        chapter, _ = repository.upsert_chapter(work_id=collection.id, book_id=book.id, chapter=NormalizedHadithChapter(
            collection_source_id=collection.source_id,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id='hadith:sahih-al-bukhari-en:book:1:chapter:1',
            book_number=1,
            chapter_number=1,
            upstream_book_id=1,
            upstream_chapter_id=1,
            title_en='How the Divine Inspiration started',
            title_ar=None,
        ))
        repository.upsert_entry(work_id=collection.id, book_id=book.id, chapter_id=chapter.id, entry=NormalizedHadithEntry(
            collection_source_id=collection.source_id,
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:1',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:1',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:1',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:1',
            collection_slug='sahih-al-bukhari-en',
            collection_hadith_number=1,
            in_book_hadith_number=1,
            book_number=1,
            chapter_number=1,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id=chapter.canonical_chapter_id,
            upstream_entry_id=1,
            upstream_book_id=1,
            upstream_chapter_id=1,
            english_narrator='Narrated Umar bin Al-Khattab:',
            english_text='Actions are judged by intentions.',
            arabic_text=None,
            narrator_chain_text=None,
            matn_text='Every person will get the reward according to what he intended.',
            metadata_json={},
            raw_json={'id': 1},
        ))
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.retrieval.lexical_search.get_session', _fake_get_session)

    service = HadithService()
    hits = service.search_topically(query_text='intention', collection_source_id='hadith:sahih-al-bukhari-en', limit=3)

    assert len(hits) == 1
    assert hits[0].entry.canonical_ref_collection == 'hadith:sahih-al-bukhari-en:1'



def test_hadith_service_topical_search_prefers_direct_patience_hadith_over_broad_match(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
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
            author_name='Imam al-Bukhari',
            language_code='en',
            source_kind='hadith_collection',
            upstream_provider='bootstrap_mirror',
            upstream_resource_id=None,
            enabled=True,
            approved_for_answering=False,
            metadata_json={},
        ))
        book, _ = repository.upsert_book(work_id=collection.id, book=NormalizedHadithBook(
            collection_source_id=collection.source_id,
            canonical_book_id='hadith:sahih-al-bukhari-en:book:1',
            book_number=1,
            upstream_book_id=1,
            title_en='Sample Book',
            title_ar=None,
        ))
        chapter, _ = repository.upsert_chapter(work_id=collection.id, book_id=book.id, chapter=NormalizedHadithChapter(
            collection_source_id=collection.source_id,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id='hadith:sahih-al-bukhari-en:book:1:chapter:1',
            book_number=1,
            chapter_number=1,
            upstream_book_id=1,
            upstream_chapter_id=1,
            title_en='Patience',
            title_ar=None,
        ))
        repository.upsert_entry(work_id=collection.id, book_id=book.id, chapter_id=chapter.id, entry=NormalizedHadithEntry(
            collection_source_id=collection.source_id,
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:1260',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:1260',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:1260',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:1260',
            collection_slug='sahih-al-bukhari-en',
            collection_hadith_number=1260,
            in_book_hadith_number=1260,
            book_number=1,
            chapter_number=1,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id=chapter.canonical_chapter_id,
            upstream_entry_id=1260,
            upstream_book_id=1,
            upstream_chapter_id=1,
            english_narrator='Narrated Anas:',
            english_text='The real patience is at the first stroke of a calamity.',
            arabic_text=None,
            narrator_chain_text=None,
            matn_text=None,
            metadata_json={},
            raw_json={'id': 1260},
        ))
        repository.upsert_entry(work_id=collection.id, book_id=book.id, chapter_id=chapter.id, entry=NormalizedHadithEntry(
            collection_source_id=collection.source_id,
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:901',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:901',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:901',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:901',
            collection_slug='sahih-al-bukhari-en',
            collection_hadith_number=901,
            in_book_hadith_number=901,
            book_number=1,
            chapter_number=1,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id=chapter.canonical_chapter_id,
            upstream_entry_id=901,
            upstream_book_id=1,
            upstream_chapter_id=1,
            english_narrator='Narrated `Amr bin Taghlib:',
            english_text="Some property was brought to Allah's Messenger and he distributed it. He said that he gives to some people because they have no patience and leaves those who are patient and self-content with the goodness Allah has put into their hearts.",
            arabic_text=None,
            narrator_chain_text=None,
            matn_text=None,
            metadata_json={},
            raw_json={'id': 901},
        ))
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.retrieval.lexical_search.get_session', _fake_get_session)

    service = HadithService()
    hits = service.search_topically(query_text='patience', collection_source_id='hadith:sahih-al-bukhari-en', limit=3)

    assert len(hits) >= 2
    assert hits[0].entry.canonical_ref_collection == 'hadith:sahih-al-bukhari-en:1260'
    assert hits[0].score > hits[1].score


def test_hadith_service_topical_search_falls_back_when_no_postgres_fts_candidates(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
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
            author_name='Imam al-Bukhari',
            language_code='en',
            source_kind='hadith_collection',
            upstream_provider='bootstrap_mirror',
            upstream_resource_id=None,
            enabled=True,
            approved_for_answering=False,
            metadata_json={},
        ))
        book, _ = repository.upsert_book(work_id=collection.id, book=NormalizedHadithBook(
            collection_source_id=collection.source_id,
            canonical_book_id='hadith:sahih-al-bukhari-en:book:1',
            book_number=1,
            upstream_book_id=1,
            title_en='Good Manners',
            title_ar=None,
        ))
        chapter, _ = repository.upsert_chapter(work_id=collection.id, book_id=book.id, chapter=NormalizedHadithChapter(
            collection_source_id=collection.source_id,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id='hadith:sahih-al-bukhari-en:book:1:chapter:1',
            book_number=1,
            chapter_number=1,
            upstream_book_id=1,
            upstream_chapter_id=1,
            title_en='Keeping ties',
            title_ar=None,
        ))
        repository.upsert_entry(work_id=collection.id, book_id=book.id, chapter_id=chapter.id, entry=NormalizedHadithEntry(
            collection_source_id=collection.source_id,
            canonical_entry_id='hadith:sahih-al-bukhari-en:entry:1992',
            canonical_ref_collection='hadith:sahih-al-bukhari-en:1992',
            canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:1992',
            canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:1992',
            collection_slug='sahih-al-bukhari-en',
            collection_hadith_number=1992,
            in_book_hadith_number=1992,
            book_number=1,
            chapter_number=1,
            canonical_book_id=book.canonical_book_id,
            canonical_chapter_id=chapter.canonical_chapter_id,
            upstream_entry_id=1992,
            upstream_book_id=1,
            upstream_chapter_id=1,
            english_narrator='Narrated Anas:',
            english_text='Whoever desires an expansion in his sustenance and age should keep good relations with his kith and kin.',
            arabic_text=None,
            narrator_chain_text=None,
            matn_text=None,
            metadata_json={},
            raw_json={'id': 1992},
        ))
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.hadith.retrieval.lexical_search.get_session', _fake_get_session)

    service = HadithService()
    hits = service.search_topically(query_text='rizq', collection_source_id='hadith:sahih-al-bukhari-en', limit=3)

    assert hits
    assert hits[0].entry.canonical_ref_collection == 'hadith:sahih-al-bukhari-en:1992'
