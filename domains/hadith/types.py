from __future__ import annotations

from enum import Enum


class HadithCollectionSlug(str, Enum):
    SAHIH_AL_BUKHARI_EN = 'sahih-al-bukhari-en'


class HadithDomainStatus(str, Enum):
    DESIGN_ONLY = 'design_only'
    READY_FOR_SCHEMA = 'ready_for_schema'
    INGESTED = 'ingested'


class HadithGradeLabel(str, Enum):
    SAHIH = 'sahih'
    HASAN = 'hasan'
    DAIF = 'daif'
    UNKNOWN = 'unknown'


class HadithReferenceType(str, Enum):
    COLLECTION_NUMBER = 'collection_number'
    BOOK_AND_HADITH = 'book_and_hadith'
    BOOK_CHAPTER_AND_HADITH = 'book_chapter_and_hadith'
