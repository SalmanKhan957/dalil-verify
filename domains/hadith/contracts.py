from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.hadith.types import HadithGradeLabel, HadithReferenceType, HadithEntryRecord


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
    entry: HadithEntryRecord | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class HadithGradingContract:
    grade_label: HadithGradeLabel
    grade_text: str | None = None
    grader_name: str | None = None
    provenance_note: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)
