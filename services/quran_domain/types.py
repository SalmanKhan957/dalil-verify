from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuranSurahMeta:
    surah_no: int
    ayah_count: int
    surah_name_ar: str
    surah_name_en: str
    source_type: str = "quran"


@dataclass(frozen=True)
class QuranAyahRecord:
    surah_no: int
    ayah_no: int
    citation_string: str
    canonical_source_id: str
    text_display: str
    surah_name_ar: str = ""


@dataclass(frozen=True)
class QuranTranslationWorkMeta:
    language: str
    translation_name: str
    translator: str
    source_id: str
    source_name: str


@dataclass(frozen=True)
class QuranTranslationAyahRecord:
    surah_no: int
    ayah_no: int
    text_display: str
    source_id: str
    translation_name: str = ""
    translator: str = ""
    source_name: str = ""
    language: str = "en"
