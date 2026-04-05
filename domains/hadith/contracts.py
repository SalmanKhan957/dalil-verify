from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.hadith.types import HadithGradeLabel, HadithReferenceType


@dataclass(slots=True)
class HadithCollectionContract:
    source_id: str
    work_slug: str
    display_name: str
    citation_label: str
    language_code: str
    source_kind: str = 'hadith_collection'
    source_domain: str = 'hadith'
    upstream_provider: str | None = None
    upstream_collection_id: str | None = None
    approved_for_answering: bool = False
    enabled: bool = False
    policy_note: str | None = None


@dataclass(slots=True)
class HadithBookContract:
    collection_source_id: str
    book_number: int
    canonical_book_id: str
    title_en: str
    title_ar: str | None = None
    aliases: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HadithChapterContract:
    canonical_book_id: str
    chapter_number: int
    canonical_chapter_id: str
    title_en: str | None = None
    title_ar: str | None = None


@dataclass(slots=True)
class HadithGradingContract:
    grade_label: HadithGradeLabel
    grade_text: str | None = None
    grader_name: str | None = None
    provenance_note: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HadithEntryContract:
    collection_source_id: str
    canonical_entry_id: str
    hadith_number: str
    reference_type: HadithReferenceType
    canonical_ref: str
    book_number: int | None = None
    chapter_number: int | None = None
    english_text: str | None = None
    arabic_text: str | None = None
    narrator_chain_text: str | None = None
    matn_text: str | None = None
    grading: HadithGradingContract | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HadithCitationReference:
    collection_slug: str
    collection_source_id: str
    reference_type: HadithReferenceType
    canonical_ref: str
    hadith_number: str | None = None
    book_number: int | None = None
    chapter_number: int | None = None
    original_query: str | None = None


@dataclass(slots=True)
class HadithRetrievalQuery:
    citation: HadithCitationReference | None = None
    topical_query: str | None = None
    language_code: str = 'en'
    limit: int = 5


@dataclass(slots=True)
class HadithCitationLookupResult:
    resolved: bool
    citation: HadithCitationReference | None = None
    entry: HadithEntryContract | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class HadithIngestionManifest:
    collection_source_id: str
    work_slug: str
    language_code: str
    expected_books: int | None = None
    expected_entries: int | None = None
    numbering_scheme: str = 'collection_hadith_number'
    notes: list[str] = field(default_factory=list)
