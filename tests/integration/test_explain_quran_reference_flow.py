from services.ask_workflows.explain_quran_reference import explain_quran_reference


def test_explain_explicit_reference_flow_returns_structured_quran_span():
    result = explain_quran_reference("Explain 94:5-6")

    assert result["ok"] is True
    assert result["intent"] == "explicit_quran_reference_explain"
    assert result["resolution"]["resolved"] is True
    assert result["resolution"]["canonical_source_id"] == "quran:94:5-6"
    assert result["quran_span"]["citation_string"] == "Quran 94:5-6"
    assert len(result["quran_span"]["ayah_rows"]) == 2
    assert result["quran_span"]["translation"]["translation_name"] == "Towards Understanding the Quran"


def test_explain_explicit_reference_flow_returns_structured_error_for_bad_reference():
    result = explain_quran_reference("Explain 115:1")

    assert result["ok"] is False
    assert result["intent"] == "explicit_quran_reference_explain"
    assert result["quran_span"] is None
    assert result["error"] == "invalid_surah_number"


from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import domains.quran.repositories.db_repository as db_repository_module
from infrastructure.db.base import Base
from infrastructure.db.models.quran_ayah import QuranAyahORM
from infrastructure.db.models.quran_surah import QuranSurahORM
from infrastructure.db.models.quran_translation_ayah import QuranTranslationAyahORM
from infrastructure.db.models.source_work import SourceWorkORM


def test_explain_explicit_reference_flow_db_preferred(monkeypatch):
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

    result = explain_quran_reference(
        "Explain 112:1-2",
        repository_mode="db_preferred",
    )

    assert result["ok"] is True
    assert result["quran_span"]["citation_string"] == "Quran 112:1-2"
    assert result["quran_span"]["translation"]["text"] == "Say: He is Allah, the One. Allah, the Eternal Refuge."
