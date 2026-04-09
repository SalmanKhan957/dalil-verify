import pytest
sqlalchemy = pytest.importorskip('sqlalchemy')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domains.tafsir.repositories.lexical_search_repository import SqlAlchemyTafsirLexicalSearchRepository
from domains.tafsir.types import NormalizedTafsirSection, SourceWorkSeed, TafsirLexicalQuery
from infrastructure.db.base import Base
from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.models.tafsir_section import TafsirSectionORM
from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository


def _seed_tafsir(session):
    repo = SqlAlchemyTafsirRepository(session)
    work = repo.upsert_source_work(
        SourceWorkSeed(
            source_domain='tafsir',
            work_slug='ibn-kathir-en',
            source_id='tafsir:ibn-kathir-en',
            display_name='Tafsir Ibn Kathir (English)',
            citation_label='Tafsir Ibn Kathir',
            author_name='Ibn Kathir',
            language_code='en',
            source_kind='commentary',
            upstream_provider='quran_foundation',
            upstream_resource_id=169,
            enabled=True,
            approved_for_answering=True,
            supports_quran_composition=True,
            metadata_json={},
        )
    )
    repo.upsert_tafsir_section(
        work_id=work.id,
        section=NormalizedTafsirSection(
            canonical_section_id='tafsir:ibn-kathir-en:94:5-6:1',
            source_id='tafsir:ibn-kathir-en',
            upstream_provider='quran_foundation',
            upstream_resource_id=169,
            upstream_entry_id=1,
            language_code='en',
            slug='ash-sharh-94-5-6',
            language_id=38,
            surah_no=94,
            ayah_start=5,
            ayah_end=6,
            anchor_verse_key='94:5',
            quran_span_ref='94:5-6',
            coverage_mode='explicit_range',
            coverage_confidence=1.0,
            text_html='<p>Indeed with hardship comes ease. Relief follows difficulty.</p>',
            text_plain='Indeed with hardship comes ease. Relief follows difficulty.',
            text_plain_normalized='indeed with hardship comes ease relief follows difficulty',
            text_hash='hash-1',
            source_file_path=None,
            source_manifest_path=None,
            raw_json={'id': 1},
        ),
    )
    repo.upsert_tafsir_section(
        work_id=work.id,
        section=NormalizedTafsirSection(
            canonical_section_id='tafsir:ibn-kathir-en:2:45:2',
            source_id='tafsir:ibn-kathir-en',
            upstream_provider='quran_foundation',
            upstream_resource_id=169,
            upstream_entry_id=2,
            language_code='en',
            slug='al-baqarah-2-45',
            language_id=38,
            surah_no=2,
            ayah_start=45,
            ayah_end=45,
            anchor_verse_key='2:45',
            quran_span_ref='2:45',
            coverage_mode='anchor_only',
            coverage_confidence=0.8,
            text_html='<p>Seek help through patience and prayer.</p>',
            text_plain='Seek help through patience and prayer.',
            text_plain_normalized='seek help through patience and prayer',
            text_hash='hash-2',
            source_file_path=None,
            source_manifest_path=None,
            raw_json={'id': 2},
        ),
    )
    session.commit()


def test_tafsir_lexical_search_ranks_relevant_section_first() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        _seed_tafsir(session)
        repository = SqlAlchemyTafsirLexicalSearchRepository(session)
        hits = repository.search(TafsirLexicalQuery(topical_query='ease after hardship', limit=3))

    assert hits
    assert hits[0].canonical_section_id == 'tafsir:ibn-kathir-en:94:5-6:1'
    assert 'hardship' in hits[0].matched_terms
    assert hits[0].snippet


def test_tafsir_lexical_search_supports_surah_filter() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        _seed_tafsir(session)
        repository = SqlAlchemyTafsirLexicalSearchRepository(session)
        hits = repository.search(TafsirLexicalQuery(topical_query='patience', surah_no=2, limit=3))

    assert len(hits) == 1
    assert hits[0].surah_no == 2
    assert hits[0].canonical_section_id == 'tafsir:ibn-kathir-en:2:45:2'
