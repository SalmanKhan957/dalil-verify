from __future__ import annotations

from contextlib import contextmanager

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db.base import Base
import services.ask_workflows.explain_quran_with_tafsir as workflow_module
from services.tafsir.repository import SqlAlchemyTafsirRepository
from services.tafsir.types import NormalizedTafsirSection, SourceWorkSeed
import services.tafsir.service as tafsir_service_module


def test_explain_quran_with_tafsir_flow(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        repository = SqlAlchemyTafsirRepository(session)
        work = repository.upsert_source_work(
            SourceWorkSeed(
                source_domain="tafsir",
                work_slug="ibn-kathir-en",
                source_id="tafsir:ibn-kathir-en",
                display_name="Tafsir Ibn Kathir (English)",
                citation_label="Tafsir Ibn Kathir",
                author_name="Ibn Kathir",
                language_code="en",
                source_kind="commentary",
                upstream_provider="quran_foundation",
                upstream_resource_id=169,
                enabled=True,
                approved_for_answering=True,
                version_label=None,
                metadata_json={},
            )
        )
        repository.upsert_tafsir_section(
            work_id=work.id,
            section=NormalizedTafsirSection(
                canonical_section_id="tafsir:ibn-kathir-en:84552",
                source_id="tafsir:ibn-kathir-en",
                upstream_provider="quran_foundation",
                upstream_resource_id=169,
                upstream_entry_id=84552,
                language_code="en",
                slug="en-tafisr-ibn-kathir",
                language_id=38,
                surah_no=112,
                ayah_start=1,
                ayah_end=4,
                anchor_verse_key="112:1",
                quran_span_ref="112:1-4",
                coverage_mode="inferred_from_empty_followers",
                coverage_confidence=0.95,
                text_html="<p>Allah is One and Unique.</p>",
                text_plain="Allah is One and Unique.",
                text_plain_normalized="Allah is One and Unique.",
                text_hash="abc123",
                source_file_path=None,
                source_manifest_path=None,
                raw_json={"id": 84552, "verse_key": "112:1"},
            ),
        )
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr(tafsir_service_module, "get_session", _fake_get_session)
    monkeypatch.setattr(tafsir_service_module, "is_source_enabled", lambda source_id: True)

    monkeypatch.setattr(
        workflow_module,
        "explain_quran_reference",
        lambda query, **kwargs: {
            "ok": True,
            "intent": "explicit_quran_reference_explain",
            "query": query,
            "resolution": {
                "resolved": True,
                "surah_no": 112,
                "ayah_start": 1,
                "ayah_end": 4,
            },
            "quran_span": {
                "source_type": "quran_span",
                "canonical_source_id": "quran:112:1-4",
                "citation_string": "Quran 112:1-4",
                "surah_no": 112,
                "ayah_start": 1,
                "ayah_end": 4,
                "surah_name_ar": "الإخلاص",
                "surah_name_en": "Al-Ikhlas",
                "ayah_count_in_surah": 4,
                "arabic_text": "قُلْ هُوَ اللَّهُ أَحَدٌ",
                "translation": {
                    "language": "en",
                    "translation_name": "Towards Understanding the Quran",
                    "translator": "",
                    "source_id": "quran:towards-understanding-en",
                    "source_name": "Towards Understanding the Quran",
                    "text": "Say: He is Allah, the One.",
                },
                "ayah_rows": [],
            },
            "error": None,
        },
    )

    result = workflow_module.explain_quran_with_tafsir(
        query="Tafsir of Surah Ikhlas",
        include_tafsir=True,
        tafsir_source_id="tafsir:ibn-kathir-en",
        tafsir_limit=3,
    )

    assert result["ok"] is True
    assert result["tafsir_error"] is None
    assert len(result["tafsir"]) == 1
    assert result["tafsir"][0]["citation"]["display_text"] == "Tafsir Ibn Kathir on Quran 112:1-4"
    assert result["tafsir"][0]["text_plain"] == "Allah is One and Unique."
