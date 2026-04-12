from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import domains.quran.repositories.db_repository as db_repository_module
from domains.quran.retrieval.fetcher import fetch_quran_span
from domains.quran.retrieval.metadata_loader import load_quran_metadata
from infrastructure.db.base import Base
from infrastructure.db.models.quran_ayah import QuranAyahORM
from infrastructure.db.models.quran_surah import QuranSurahORM
from infrastructure.db.models.quran_translation_ayah import QuranTranslationAyahORM
from infrastructure.db.models.source_work import SourceWorkORM


def test_load_quran_metadata_from_corpus():
    metadata = load_quran_metadata()
    assert metadata[1]["ayah_count"] == 7
    assert metadata[94]["ayah_count"] == 8
    assert metadata[112]["ayah_count"] == 4
    assert metadata[94]["surah_name_ar"] == "الشرح"
    assert metadata[94]["surah_name_en"] == "ash-sharh"


def test_fetch_single_ayah_quran_span():
    result = fetch_quran_span(surah_no=94, ayah_start=5, ayah_end=5)
    assert result["canonical_source_id"] == "quran:94:5"
    assert result["citation_string"] == "Quran 94:5"
    assert result["arabic_text"] == "فَإِنَّ مَعَ الْعُسْرِ يُسْرًا"
    assert result["translation"]["translation_name"] == "Towards Understanding the Quran"
    assert result["translation"]["text"] == "Indeed, there is ease with hardship."
    assert len(result["ayah_rows"]) == 1
    assert result["ayah_rows"][0]["arabic_canonical_source_id"] == "quran:94:5:ar"


def test_fetch_multi_ayah_quran_span():
    result = fetch_quran_span(surah_no=94, ayah_start=5, ayah_end=6)
    assert result["canonical_source_id"] == "quran:94:5-6"
    assert result["citation_string"] == "Quran 94:5-6"
    assert len(result["ayah_rows"]) == 2
    assert [row["ayah_no"] for row in result["ayah_rows"]] == [5, 6]
    assert "فَإِنَّ مَعَ الْعُسْرِ يُسْرًا" in result["arabic_text"]
    assert "إِنَّ مَعَ الْعُسْرِ يُسْرًا" in result["arabic_text"]
    assert "Indeed, there is ease with hardship." in result["translation"]["text"]
    assert "Most certainly, there is ease with hardship." in result["translation"]["text"]


def test_fetch_whole_surah_span():
    result = fetch_quran_span(surah_no=112, ayah_start=1, ayah_end=4)
    assert result["canonical_source_id"] == "quran:112:1-4"
    assert len(result["ayah_rows"]) == 4
    assert result["ayah_rows"][0]["citation_string"] == "Quran 112:1"
    assert result["ayah_rows"][-1]["citation_string"] == "Quran 112:4"


def test_fetch_quran_span_db_preferred(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        session.add(
            SourceWorkORM(
                source_domain="quran",
                work_slug="tanzil-simple",
                source_id="quran:tanzil-simple",
                display_name="Quran Arabic Canonical Text (Simple)",
                citation_label="Quran",
                author_name=None,
                language_code="ar",
                source_kind="canonical_text",
                upstream_provider="dalil_bootstrap",
                upstream_resource_id=None,
                enabled=True,
                approved_for_answering=True,
                default_for_explain=False,
                supports_quran_composition=False,
                priority_rank=10,
                version_label=None,
                policy_note=None,
                metadata_json={},
            )
        )
        session.add(
            SourceWorkORM(
                source_domain="quran",
                work_slug="towards-understanding-en",
                source_id="quran:towards-understanding-en",
                display_name="Towards Understanding the Quran",
                citation_label="Towards Understanding the Quran",
                author_name="Abul Ala Maududi",
                language_code="en",
                source_kind="translation",
                upstream_provider="dalil_bootstrap",
                upstream_resource_id=None,
                enabled=True,
                approved_for_answering=True,
                default_for_explain=False,
                supports_quran_composition=False,
                priority_rank=20,
                version_label=None,
                policy_note=None,
                metadata_json={"source_name": "local_file"},
            )
        )
        session.flush()
        arabic_work_id = session.query(SourceWorkORM).filter_by(source_id="quran:tanzil-simple").one().id
        translation_work_id = session.query(SourceWorkORM).filter_by(source_id="quran:towards-understanding-en").one().id
        session.add(QuranSurahORM(surah_no=112, surah_name_ar="الإخلاص", surah_name_en="al-ikhlas", ayah_count=2))
        session.add_all(
            [
                QuranAyahORM(
                    work_id=arabic_work_id,
                    surah_no=112,
                    ayah_no=1,
                    canonical_source_id="quran:112:1:ar",
                    citation_string="Quran 112:1",
                    text_display="قُلْ هُوَ اللَّهُ أَحَدٌ",
                    text_normalized_light="قل هو الله احد",
                    text_normalized_aggressive="قل هو الله احد",
                    bismillah=None,
                ),
                QuranAyahORM(
                    work_id=arabic_work_id,
                    surah_no=112,
                    ayah_no=2,
                    canonical_source_id="quran:112:2:ar",
                    citation_string="Quran 112:2",
                    text_display="اللَّهُ الصَّمَدُ",
                    text_normalized_light="الله الصمد",
                    text_normalized_aggressive="الله الصمد",
                    bismillah=None,
                ),
                QuranTranslationAyahORM(
                    work_id=translation_work_id,
                    surah_no=112,
                    ayah_no=1,
                    text_display="Say: He is Allah, the One.",
                    text_raw_html="Say: He is Allah, the One.",
                    translation_name="Towards Understanding the Quran",
                    translator="Abul Ala Maududi",
                    language_code="en",
                ),
                QuranTranslationAyahORM(
                    work_id=translation_work_id,
                    surah_no=112,
                    ayah_no=2,
                    text_display="Allah, the Eternal Refuge.",
                    text_raw_html="Allah, the Eternal Refuge.",
                    translation_name="Towards Understanding the Quran",
                    translator="Abul Ala Maududi",
                    language_code="en",
                ),
            ]
        )
        session.commit()

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        del database_url, echo
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr(db_repository_module, "get_session", _fake_get_session)

    result = fetch_quran_span(
        surah_no=112,
        ayah_start=1,
        ayah_end=2,
        repository_mode="db_preferred",
    )

    assert result["surah_no"] == 112
    assert result["translation"]["source_id"] == "quran:towards-understanding-en"
    assert result["ayah_rows"][0]["translation_source_id"] == "quran:towards-understanding-en"
    assert result["translation"]["text"] == "Say: He is Allah, the One. Allah, the Eternal Refuge."


def test_fetch_single_ayah_quran_span_surfaces_requested_translation_work_source_id():
    result = fetch_quran_span(
        surah_no=94,
        ayah_start=5,
        ayah_end=5,
        translation_work_source_id='quran:towards-understanding-en',
    )
    assert result['translation']['source_id'] == 'quran:towards-understanding-en'
    assert result['ayah_rows'][0]['translation_source_id'] == 'quran:towards-understanding-en'
