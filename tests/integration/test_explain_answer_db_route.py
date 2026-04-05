from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.ask_api.main import app
from infrastructure.db.base import Base
from infrastructure.db.models.quran_ayah import QuranAyahORM
from infrastructure.db.models.quran_surah import QuranSurahORM
from infrastructure.db.models.quran_translation_ayah import QuranTranslationAyahORM
from infrastructure.db.models.source_work import SourceWorkORM


def _seed_quran_db(db_path: Path) -> str:
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url)
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
        translation_work_id = (
            session.query(SourceWorkORM).filter_by(source_id="quran:towards-understanding-en").one().id
        )
        session.add(QuranSurahORM(surah_no=112, surah_name_ar="الإخلاص", surah_name_en="al-ikhlas", ayah_count=2))
        session.add_all(
            [
                QuranAyahORM(
                    work_id=arabic_work_id,
                    surah_no=112,
                    ayah_no=1,
                    text_display="قُلْ هُوَ اللَّهُ أَحَدٌ",
                    text_normalized_light="قل هو الله احد",
                    text_normalized_aggressive="قل هو الله احد",
                    bismillah=None,
                    canonical_source_id="quran:112:1:ar",
                    citation_string="Quran 112:1",
                ),
                QuranAyahORM(
                    work_id=arabic_work_id,
                    surah_no=112,
                    ayah_no=2,
                    text_display="اللَّهُ الصَّمَدُ",
                    text_normalized_light="الله الصمد",
                    text_normalized_aggressive="الله الصمد",
                    bismillah=None,
                    canonical_source_id="quran:112:2:ar",
                    citation_string="Quran 112:2",
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
    return database_url


@pytest.mark.anyio
async def test_explain_route_uses_db_only_repository_from_env(tmp_path, monkeypatch) -> None:
    database_url = _seed_quran_db(tmp_path / "quran.db")
    monkeypatch.setenv("DALIL_DATABASE_URL", database_url)
    monkeypatch.setenv("DALIL_QURAN_REPOSITORY_MODE", "db_only")

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={"query": "112:1-2", "include_tafsir": False},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["resolution"]["canonical_source_id"] == "quran:112:1-2"
    assert body["quran_support"]["surah_no"] == 112
    assert body["quran_support"]["translation_text"] == "Say: He is Allah, the One. Allah, the Eternal Refuge."
    assert body["quran_support"]["arabic_text"] == "قُلْ هُوَ اللَّهُ أَحَدٌ اللَّهُ الصَّمَدُ"
