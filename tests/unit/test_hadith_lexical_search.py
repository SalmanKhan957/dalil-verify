import pytest
sqlalchemy = pytest.importorskip('sqlalchemy')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domains.hadith.contracts import HadithLexicalQuery
from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
from domains.hadith.repositories.lexical_search_repository import SqlAlchemyHadithLexicalSearchRepository
from domains.hadith.types import HadithCollectionSeed, NormalizedHadithBook, NormalizedHadithChapter, NormalizedHadithEntry
from infrastructure.db.base import Base


def _seed_hadith(session):
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
    book1, _ = repository.upsert_book(work_id=collection.id, book=NormalizedHadithBook(
        collection_source_id=collection.source_id,
        canonical_book_id='hadith:sahih-al-bukhari-en:book:1',
        book_number=1,
        upstream_book_id=1,
        title_en='Revelation',
        title_ar=None,
    ))
    chapter1, _ = repository.upsert_chapter(work_id=collection.id, book_id=book1.id, chapter=NormalizedHadithChapter(
        collection_source_id=collection.source_id,
        canonical_book_id=book1.canonical_book_id,
        canonical_chapter_id='hadith:sahih-al-bukhari-en:book:1:chapter:1',
        book_number=1,
        chapter_number=1,
        upstream_book_id=1,
        upstream_chapter_id=1,
        title_en='How the Divine Inspiration started',
        title_ar=None,
    ))
    repository.upsert_entry(work_id=collection.id, book_id=book1.id, chapter_id=chapter1.id, entry=NormalizedHadithEntry(
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
        canonical_book_id=book1.canonical_book_id,
        canonical_chapter_id=chapter1.canonical_chapter_id,
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
    book2, _ = repository.upsert_book(work_id=collection.id, book=NormalizedHadithBook(
        collection_source_id=collection.source_id,
        canonical_book_id='hadith:sahih-al-bukhari-en:book:2',
        book_number=2,
        upstream_book_id=2,
        title_en='Faith',
        title_ar=None,
    ))
    chapter2, _ = repository.upsert_chapter(work_id=collection.id, book_id=book2.id, chapter=NormalizedHadithChapter(
        collection_source_id=collection.source_id,
        canonical_book_id=book2.canonical_book_id,
        canonical_chapter_id='hadith:sahih-al-bukhari-en:book:2:chapter:1',
        book_number=2,
        chapter_number=1,
        upstream_book_id=2,
        upstream_chapter_id=2,
        title_en='Faith has many branches',
        title_ar=None,
    ))
    repository.upsert_entry(work_id=collection.id, book_id=book2.id, chapter_id=chapter2.id, entry=NormalizedHadithEntry(
        collection_source_id=collection.source_id,
        canonical_entry_id='hadith:sahih-al-bukhari-en:entry:2',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:2',
        canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:2:hadith:1',
        canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:2:chapter:1:hadith:1',
        collection_slug='sahih-al-bukhari-en',
        collection_hadith_number=2,
        in_book_hadith_number=1,
        book_number=2,
        chapter_number=1,
        canonical_book_id=book2.canonical_book_id,
        canonical_chapter_id=chapter2.canonical_chapter_id,
        upstream_entry_id=2,
        upstream_book_id=2,
        upstream_chapter_id=2,
        english_narrator='Narrated Abu Huraira:',
        english_text='Faith has over sixty branches.',
        arabic_text=None,
        narrator_chain_text=None,
        matn_text=None,
        metadata_json={},
        raw_json={'id': 2},
    ))
    session.commit()


def test_hadith_lexical_search_ranks_intentions_hadith_first() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        _seed_hadith(session)
        repository = SqlAlchemyHadithLexicalSearchRepository(session)
        hits = repository.search(HadithLexicalQuery(topical_query='intention', limit=3))

    assert hits
    assert hits[0].entry.canonical_ref_collection == 'hadith:sahih-al-bukhari-en:1'
    assert 'intention' in hits[0].matched_terms or 'intentions' in hits[0].matched_terms
    assert hits[0].snippet


def test_hadith_lexical_search_supports_fuzzy_book_title_matching() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        _seed_hadith(session)
        repository = SqlAlchemyHadithLexicalSearchRepository(session)
        hits = repository.search(HadithLexicalQuery(topical_query='revalation', limit=3))

    assert hits
    assert hits[0].entry.book_number == 1
    assert hits[0].book_title == 'Revelation'
