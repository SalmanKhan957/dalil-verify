from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domains.quran.repositories.db_repository import (
    DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
    SqlAlchemyQuranRepository,
    build_arabic_work_seed,
    build_surah_rows_from_arabic_csv,
    build_translation_work_seed,
)
from infrastructure.db.base import Base


ARABIC_ROWS = [
    {
        "surah_no": 112,
        "ayah_no": 1,
        "surah_name_ar": "الإخلاص",
        "text_display": "قُلْ هُوَ اللَّهُ أَحَدٌ",
        "text_normalized_light": "قل هو الله احد",
        "text_normalized_aggressive": "قل هو الله احد",
        "bismillah": "",
        "canonical_source_id": "quran:112:1:ar",
        "citation_string": "Quran 112:1",
    },
    {
        "surah_no": 112,
        "ayah_no": 2,
        "surah_name_ar": "الإخلاص",
        "text_display": "اللَّهُ الصَّمَدُ",
        "text_normalized_light": "الله الصمد",
        "text_normalized_aggressive": "الله الصمد",
        "bismillah": "",
        "canonical_source_id": "quran:112:2:ar",
        "citation_string": "Quran 112:2",
    },
]

TRANSLATION_ROWS = [
    {
        "surah_no": 112,
        "ayah_no": 1,
        "translation_name": "Towards Understanding the Quran",
        "translator": "Abul Ala Maududi",
        "language": "en",
        "source_name": "local_file",
        "text_display": "Say: He is Allah, the One.",
        "text_raw_html": "Say: He is Allah, the One.",
    },
    {
        "surah_no": 112,
        "ayah_no": 2,
        "translation_name": "Towards Understanding the Quran",
        "translator": "Abul Ala Maududi",
        "language": "en",
        "source_name": "local_file",
        "text_display": "Allah, the Eternal Refuge.",
        "text_raw_html": "Allah, the Eternal Refuge.",
    },
]


def test_sqlalchemy_quran_repository_round_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        repo = SqlAlchemyQuranRepository(session)
        surah_counts = repo.upsert_surah_rows(
            [{"surah_no": 112, "surah_name_ar": "الإخلاص", "surah_name_en": "al-ikhlas", "ayah_count": 2}]
        )
        arabic_counts = repo.upsert_quran_ayah_rows(
            work_source_id=DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
            rows=ARABIC_ROWS,
            seed=build_arabic_work_seed(),
        )
        translation_counts = repo.upsert_translation_rows(
            work_source_id=DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
            rows=TRANSLATION_ROWS,
            seed=build_translation_work_seed(
                translation_name="Towards Understanding the Quran",
                translator="Abul Ala Maududi",
                language="en",
                source_name="local_file",
            ),
        )
        session.commit()

        assert surah_counts["inserted"] == 1
        assert arabic_counts["inserted"] == 2
        assert translation_counts["inserted"] == 2

        metadata = repo.load_quran_metadata()
        assert metadata[112]["ayah_count"] == 2
        assert metadata[112]["surah_name_ar"] == "الإخلاص"

        quran_rows = repo.fetch_quran_span(surah_no=112, ayah_start=1, ayah_end=2)
        assert len(quran_rows) == 2
        assert quran_rows[0]["canonical_source_id"] == "quran:112:1:ar"

        translation = repo.fetch_translation_span(surah_no=112, ayah_start=1, ayah_end=2)
        assert translation["translation_name"] == "Towards Understanding the Quran"
        assert translation["source_id"] == DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID
        assert "Allah, the Eternal Refuge." in translation["text"]
