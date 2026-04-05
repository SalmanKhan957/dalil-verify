from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExplainQuranReferenceRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Explicit Quran reference to explain.")
    quran_text_source_id: str | None = Field(
        default=None,
        description="Optional governed Quran canonical text source override.",
    )
    quran_translation_source_id: str | None = Field(
        default=None,
        description="Optional governed Quran translation source override.",
    )
    include_tafsir: bool | None = Field(
        default=None,
        description=(
            "Whether to attach approved Tafsir overlap results. "
            "When omitted, explain-mode requests default to Quran + approved Tafsir if available."
        ),
    )
    tafsir_source_id: str = Field(
        default="tafsir:ibn-kathir-en",
        description="Stable source/work identifier for the Tafsir work to use.",
    )
    tafsir_limit: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of overlapping Tafsir sections to return.",
    )
    debug: bool = Field(default=False, description="Whether to include raw retrieval detail under debug.")


class SourceCitationView(BaseModel):
    source_id: str
    citation_text: str
    canonical_ref: str | None = None
    source_domain: str


class QuranSupport(BaseModel):
    citation_string: str
    surah_no: int
    ayah_start: int
    ayah_end: int
    surah_name_en: str | None = None
    surah_name_ar: str | None = None
    arabic_text: str | None = None
    translation_text: str | None = None
    canonical_source_id: str | None = None
    quran_source_id: str | None = None
    translation_source_id: str | None = None


class QuranSourceSelection(BaseModel):
    repository_mode: str | None = None
    source_resolution_strategy: str | None = None
    requested_quran_text_source_id: str | None = None
    requested_quran_translation_source_id: str | None = None
    selected_quran_text_source_id: str | None = None
    selected_quran_translation_source_id: str | None = None


class TafsirSupportItem(BaseModel):
    source_id: str
    canonical_section_id: str
    display_text: str
    excerpt: str
    text_html: str | None = None
    surah_no: int
    ayah_start: int
    ayah_end: int
    coverage_mode: str
    coverage_confidence: float
    anchor_verse_key: str
    quran_span_ref: str
    excerpt_was_trimmed: bool = False


class ExplainAnswerResponse(BaseModel):
    ok: bool
    query: str
    answer_mode: str
    route_type: str
    action_type: str
    answer_text: str | None = None
    citations: list[SourceCitationView] = Field(default_factory=list)
    quran_support: QuranSupport | None = None
    tafsir_support: list[TafsirSupportItem] = Field(default_factory=list)
    resolution: dict[str, Any] | None = None
    partial_success: bool = False
    warnings: list[str] = Field(default_factory=list)
    quran_source_selection: QuranSourceSelection | None = None
    debug: dict[str, Any] | None = None
    error: str | None = None


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Ask query to classify and route.")
    quran_text_source_id: str | None = Field(
        default=None,
        description="Optional governed Quran canonical text source override.",
    )
    quran_translation_source_id: str | None = Field(
        default=None,
        description="Optional governed Quran translation source override.",
    )
    debug: bool = Field(default=False, description="Whether to include verifier debug output where available.")


class AskResponse(BaseModel):
    ok: bool
    query: str
    route_type: str
    action_type: str
    route: dict[str, Any]
    answer_mode: str | None = None
    answer_text: str | None = None
    citations: list[SourceCitationView] = Field(default_factory=list)
    quran_support: QuranSupport | None = None
    tafsir_support: list[TafsirSupportItem] = Field(default_factory=list)
    resolution: dict[str, Any] | None = None
    partial_success: bool = False
    warnings: list[str] = Field(default_factory=list)
    quran_source_selection: QuranSourceSelection | None = None
    debug: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
