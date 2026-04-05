from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


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


@dataclass(frozen=True)
class HadithCollectionSeed:
    source_domain: str
    work_slug: str
    source_id: str
    display_name: str
    citation_label: str
    author_name: str | None
    language_code: str
    source_kind: str
    upstream_provider: str
    upstream_resource_id: int | None
    enabled: bool
    approved_for_answering: bool
    default_for_explain: bool = False
    supports_quran_composition: bool = False
    priority_rank: int = 1000
    version_label: str | None = None
    policy_note: str | None = None
    metadata_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class HadithCollectionRecord:
    id: int
    source_domain: str
    work_slug: str
    source_id: str
    display_name: str
    citation_label: str
    author_name: str | None
    language_code: str
    source_kind: str
    upstream_provider: str
    upstream_resource_id: int | None
    enabled: bool
    approved_for_answering: bool
    default_for_explain: bool
    supports_quran_composition: bool
    priority_rank: int
    version_label: str | None
    policy_note: str | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class NormalizedHadithBook:
    collection_source_id: str
    canonical_book_id: str
    book_number: int
    upstream_book_id: int
    title_en: str
    title_ar: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedHadithChapter:
    collection_source_id: str
    canonical_book_id: str
    canonical_chapter_id: str
    book_number: int
    chapter_number: int
    upstream_book_id: int
    upstream_chapter_id: int
    title_en: str | None = None
    title_ar: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedHadithGrading:
    grade_label: HadithGradeLabel
    grade_text: str | None = None
    grader_name: str = 'collection_default'
    provenance_note: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedHadithEntry:
    collection_source_id: str
    canonical_entry_id: str
    canonical_ref_collection: str
    canonical_ref_book_hadith: str | None
    canonical_ref_book_chapter_hadith: str | None
    collection_slug: str
    collection_hadith_number: int
    in_book_hadith_number: int | None
    book_number: int
    chapter_number: int | None
    canonical_book_id: str
    canonical_chapter_id: str | None
    upstream_entry_id: int
    upstream_book_id: int
    upstream_chapter_id: int | None
    english_narrator: str | None
    english_text: str | None
    arabic_text: str | None
    narrator_chain_text: str | None
    matn_text: str | None
    grading: NormalizedHadithGrading | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)
    raw_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HadithBookRecord:
    id: int
    work_id: int
    canonical_book_id: str
    book_number: int
    upstream_book_id: int
    title_en: str
    title_ar: str | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class HadithChapterRecord:
    id: int
    work_id: int
    book_id: int
    canonical_chapter_id: str
    chapter_number: int
    upstream_chapter_id: int
    title_en: str | None
    title_ar: str | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class HadithGradingRecord:
    id: int
    entry_id: int
    grade_label: HadithGradeLabel
    grade_text: str | None
    grader_name: str
    provenance_note: str | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class HadithEntryRecord:
    id: int
    work_id: int
    book_id: int
    chapter_id: int | None
    collection_source_id: str
    canonical_entry_id: str
    canonical_ref_collection: str
    canonical_ref_book_hadith: str | None
    canonical_ref_book_chapter_hadith: str | None
    collection_hadith_number: int
    in_book_hadith_number: int | None
    book_number: int
    chapter_number: int | None
    english_narrator: str | None
    english_text: str | None
    arabic_text: str | None
    narrator_chain_text: str | None
    matn_text: str | None
    metadata_json: dict[str, Any]
    raw_json: dict[str, Any]
    grading: HadithGradingRecord | None = None


@dataclass(frozen=True)
class HadithIngestionManifest:
    collection_source_id: str
    work_slug: str
    language_code: str
    expected_books: int | None = None
    expected_entries: int | None = None
    numbering_scheme: str = 'collection_hadith_number'
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HadithCollectionBatch:
    collection_seed: HadithCollectionSeed
    books: list[NormalizedHadithBook]
    chapters: list[NormalizedHadithChapter]
    entries: list[NormalizedHadithEntry]
    manifest: HadithIngestionManifest
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HadithIngestionRunOpened:
    run_id: int
    work_id: int
    source_root: str
    upstream_provider: str


@dataclass(frozen=True)
class HadithIngestionRunSummary:
    run_id: int
    status: Literal['completed', 'completed_with_warnings', 'failed']
    collections_seen: int
    books_seen: int
    chapters_seen: int
    entries_seen: int
    gradings_seen: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    notes_json: dict[str, Any]
