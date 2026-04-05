from __future__ import annotations

from infrastructure.db.models.hadith_book import HadithBookORM
from infrastructure.db.models.hadith_chapter import HadithChapterORM
from infrastructure.db.models.hadith_entry import HadithEntryORM
from infrastructure.db.models.hadith_grading import HadithGradingORM
from infrastructure.db.models.hadith_ingestion_run import HadithIngestionRunORM
from infrastructure.db.models.quran_ayah import QuranAyahORM
from infrastructure.db.models.quran_surah import QuranSurahORM
from infrastructure.db.models.quran_translation_ayah import QuranTranslationAyahORM
from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.models.tafsir_ingestion_run import TafsirIngestionRunORM
from infrastructure.db.models.tafsir_section import TafsirSectionORM

__all__ = [
    "SourceWorkORM",
    "QuranSurahORM",
    "QuranAyahORM",
    "QuranTranslationAyahORM",
    "TafsirSectionORM",
    "TafsirIngestionRunORM",
    "HadithBookORM",
    "HadithChapterORM",
    "HadithEntryORM",
    "HadithGradingORM",
    "HadithIngestionRunORM",
]
