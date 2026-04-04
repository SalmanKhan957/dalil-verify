from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


CoverageMode = Literal[
    "explicit_range",
    "inferred_from_empty_followers",
    "anchor_only",
]


@dataclass(frozen=True)
class RawTafsirRow:
    entry_id: int
    resource_id: int
    surah_no: int
    ayah_no: int
    verse_key: str
    language_id: int | None
    slug: str | None
    text_html: str
    text_plain: str
    text_plain_normalized: str
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class NormalizedTafsirSection:
    canonical_section_id: str
    source_id: str
    upstream_provider: str
    upstream_resource_id: int
    upstream_entry_id: int

    language_code: str
    slug: str | None
    language_id: int | None

    surah_no: int
    ayah_start: int
    ayah_end: int
    anchor_verse_key: str
    quran_span_ref: str

    coverage_mode: CoverageMode
    coverage_confidence: float

    text_html: str
    text_plain: str
    text_plain_normalized: str
    text_hash: str

    source_file_path: str | None
    source_manifest_path: str | None
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class SourceWorkSeed:
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
class TafsirSourceWork:
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
class TafsirIngestionRunOpened:
    run_id: int
    work_id: int
    resource_id: int
    source_root: str


@dataclass(frozen=True)
class TafsirIngestionChapterResult:
    chapter_number: int
    raw_rows_seen: int
    sections_built: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    warnings: list[str]


@dataclass(frozen=True)
class TafsirIngestionRunSummary:
    run_id: int
    status: Literal["completed", "completed_with_warnings", "failed"]
    chapters_seen: int
    raw_rows_seen: int
    sections_built: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    notes_json: dict[str, Any]


@dataclass(frozen=True)
class TafsirOverlapQuery:
    work_id: int
    surah_no: int
    ayah_start: int
    ayah_end: int
    limit: int = 5


@dataclass(frozen=True)
class TafsirOverlapHit:
    section_id: int
    canonical_section_id: str
    work_id: int
    source_id: str
    display_name: str
    citation_label: str

    surah_no: int
    ayah_start: int
    ayah_end: int
    anchor_verse_key: str
    quran_span_ref: str

    coverage_mode: CoverageMode
    coverage_confidence: float

    text_plain: str
    text_html: str

    overlap_ayah_count: int
    exact_span_match: bool
    contains_query_span: bool
    query_contains_section: bool
    span_width: int
    anchor_distance: int


@dataclass(frozen=True)
class TafsirCitationBlock:
    source_id: str
    canonical_section_id: str
    citation_label: str
    quran_span_ref: str
    display_text: str
