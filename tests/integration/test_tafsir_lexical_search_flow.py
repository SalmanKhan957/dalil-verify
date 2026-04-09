import pytest
sqlalchemy = pytest.importorskip('sqlalchemy')

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository
from domains.tafsir.service import TafsirService
from domains.tafsir.types import NormalizedTafsirSection, SourceWorkSeed
from infrastructure.db.base import Base


def test_tafsir_service_topical_search_respects_source_filter(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        repository = SqlAlchemyTafsirRepository(session)
        work = repository.upsert_source_work(SourceWorkSeed(
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
        ))
        repository.upsert_tafsir_section(work_id=work.id, section=NormalizedTafsirSection(
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
            text_html='<p>With hardship comes ease.</p>',
            text_plain='With hardship comes ease.',
            text_plain_normalized='with hardship comes ease',
            text_hash='hash',
            source_file_path=None,
            source_manifest_path=None,
            raw_json={'id': 1},
        ))
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr('domains.tafsir.service.get_session', _fake_get_session)
    monkeypatch.setattr('domains.source_registry.db_registry.get_session', _fake_get_session)

    service = TafsirService()
    hits = service.search_topically(query_text='hardship', source_id='tafsir:ibn-kathir-en', limit=3)

    assert len(hits) == 1
    assert hits[0].source_id == 'tafsir:ibn-kathir-en'
