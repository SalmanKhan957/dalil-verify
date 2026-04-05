from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_PLACEHOLDER_SOURCE_ID = 'string'



def _reject_placeholder_source_id(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.lower() == _PLACEHOLDER_SOURCE_ID:
        raise ValueError(
            f"{field_name}='string' looks like an OpenAPI placeholder; omit this field unless intentionally overriding"
        )
    return normalized


class AskSurfaceRequestBase(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'query': 'Tafsir of Surah Ikhlas',
                    'include_tafsir': True,
                    'tafsir_limit': 3,
                    'debug': False,
                },
                {
                    'query': 'What does 112:1-4 say?',
                    'debug': False,
                },
            ]
        }
    )

    query: str = Field(..., min_length=1, description='Ask query for the canonical Ask surface.')
    quran_text_source_id: str | None = Field(
        default=None,
        description=(
            'Optional governed Quran canonical text source override. '
            'Omit unless intentionally overriding to an approved source id.'
        ),
    )
    quran_translation_source_id: str | None = Field(
        default=None,
        description=(
            'Optional governed Quran translation source override. '
            'Omit unless intentionally overriding to an approved source id.'
        ),
    )
    include_tafsir: bool | None = Field(
        default=None,
        description=(
            'Whether to attach approved Tafsir overlap results. '
            'When omitted, the canonical Ask surface follows route-specific defaults.'
        ),
    )
    tafsir_source_id: str | None = Field(
        default=None,
        description=(
            'Stable source/work identifier for the Tafsir work to use when Tafsir is requested. '
            'Omit to use the governed default.'
        ),
    )
    tafsir_limit: int = Field(
        default=3,
        ge=1,
        le=5,
        description='Maximum number of overlapping Tafsir sections to return.',
    )
    debug: bool = Field(default=False, description='Whether to include raw retrieval detail under debug.')

    @field_validator('quran_text_source_id', 'quran_translation_source_id', mode='before')
    @classmethod
    def validate_optional_quran_source_override(cls, value: object, info) -> str | None:
        if value is None or isinstance(value, str):
            return _reject_placeholder_source_id(value, field_name=info.field_name)
        raise TypeError(f'{info.field_name} must be a string or null')

    @field_validator('tafsir_source_id', mode='before')
    @classmethod
    def validate_tafsir_source_id(cls, value: object, info) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f'{info.field_name} must be a string or null')
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.lower() == _PLACEHOLDER_SOURCE_ID:
            raise ValueError(
                "tafsir_source_id='string' looks like an OpenAPI placeholder; omit this field unless intentionally overriding"
            )
        return normalized


class ExplainQuranReferenceRequest(AskSurfaceRequestBase):
    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'query': 'Tafsir of Surah Ikhlas',
                    'include_tafsir': True,
                    'tafsir_limit': 3,
                    'debug': False,
                },
                {
                    'query': 'Explain Surah Al-Rahman',
                    'include_tafsir': True,
                    'debug': False,
                },
            ]
        }
    )

    query: str = Field(..., min_length=1, description='Explicit Quran reference or Arabic Quran quote to explain.')


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


class QuranDomainPolicyView(BaseModel):
    domain: str
    allowed: bool
    included: bool
    policy_reason: str | None = None
    requested_text_source_id: str | None = None
    requested_translation_source_id: str | None = None
    selected_text_source_id: str | None = None
    selected_translation_source_id: str | None = None
    text_source_origin: str | None = None
    translation_source_origin: str | None = None


class TafsirDomainPolicyView(BaseModel):
    domain: str
    requested: bool
    request_origin: str | None = None
    requested_source_id: str | None = None
    selected_source_id: str | None = None
    allowed: bool
    included: bool
    policy_reason: str | None = None


class SourcePolicyView(BaseModel):
    quran: QuranDomainPolicyView
    tafsir: TafsirDomainPolicyView


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
    source_policy: SourcePolicyView | None = None
    debug: dict[str, Any] | None = None
    error: str | None = None


class AskRequest(AskSurfaceRequestBase):
    query: str = Field(..., min_length=1, description='Ask query to classify and route via the canonical Ask surface.')


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
    source_policy: SourcePolicyView | None = None
    debug: dict[str, Any] | None = None
    result: dict[str, Any] | None = Field(
        default=None,
        description=(
            'Legacy compatibility envelope carrying the explain-style result payload. '
            'It mostly mirrors the top-level answer surface but may still include legacy internal '
            'compatibility fields retained for older clients until the later deprecation tranche.'
        ),
    )
    error: str | None = None
