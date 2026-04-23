from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


def _first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None


def _infer_terminal_state_value(values: dict[str, Any]) -> str:
    terminal_state = values.get('terminal_state')
    if isinstance(terminal_state, str) and terminal_state.strip():
        return terminal_state.strip()
    answer_mode = str(values.get('answer_mode') or '').strip()
    error = values.get('error')
    ok = values.get('ok')
    if answer_mode == 'clarify':
        return 'clarify'
    if answer_mode == 'abstain' or error is not None or ok is False:
        return 'abstain'
    return 'answered'


def _ensure_matching_alias(*, nested_value: object, flat_value: object, nested_field: str, flat_field: str) -> None:
    if nested_value is None or flat_value is None:
        return
    if nested_value != flat_value:
        raise ValueError(f"Conflicting request controls supplied for {flat_field} and {nested_field}; provide only one value or make them match exactly")


class AskContextRequest(BaseModel):
    conversation_id: str | None = Field(default=None, description='Opaque conversation/thread identifier accepted and surfaced for follow-up-aware clients. Narrow anchored follow-up can hydrate the latest follow-up-eligible anchors from this conversation when explicit anchor refs are not supplied.')
    parent_turn_id: str | None = Field(default=None, description='Opaque parent turn identifier accepted and surfaced for follow-up anchoring. Narrow anchored follow-up can hydrate anchors from this prior response when supplied.')
    anchor_refs: list[str] = Field(default_factory=list, description='Canonical refs the caller wants to carry forward as explicit anchors. Narrow anchored follow-up resolution over Quran, Tafsir, and explicit Hadith is supported when these refs are supplied.')

    @field_validator('conversation_id', 'parent_turn_id', mode='before')
    @classmethod
    def normalize_optional_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError('conversation context identifiers must be strings or null')
        normalized = value.strip()
        return normalized or None

    @field_validator('anchor_refs', mode='before')
    @classmethod
    def normalize_anchor_refs(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError('anchor_refs must be a list of strings')
        refs: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError('anchor_refs must contain only strings')
            normalized = item.strip()
            if normalized:
                refs.append(normalized)
        return refs


class AskPreferencesRequest(BaseModel):
    language: str | None = Field(default=None, description='Preferred answer language hint. Accepted and surfaced, but currently advisory only for bounded answer rendering.')
    verbosity: Literal['brief', 'standard', 'detailed'] | None = Field(default=None)
    citations: Literal['inline', 'block', 'minimal'] | None = Field(default=None)

    @field_validator('language', mode='before')
    @classmethod
    def normalize_language(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError('language must be a string or null')
        normalized = value.strip()
        return normalized or None


class QuranSourceControlsRequest(BaseModel):
    text_source_id: str | None = None
    translation_source_id: str | None = None

    @field_validator('text_source_id', 'translation_source_id', mode='before')
    @classmethod
    def normalize_source_override(cls, value: object, info) -> str | None:
        if value is None or isinstance(value, str):
            return _reject_placeholder_source_id(value, field_name=info.field_name)
        raise TypeError(f'{info.field_name} must be a string or null')


class TafsirSourceControlsRequest(BaseModel):
    mode: Literal['off', 'auto', 'required'] | None = Field(default=None, description='Whether Tafsir is disabled, planner-driven, or explicitly required.')
    limit: int | None = Field(default=None, ge=1, le=5)
    source_ids: list[str] = Field(
        default_factory=list,
        description='Up to three Tafsir source ids are supported on the public surface for source-separated comparative Quran commentary selection.'
    )

    @field_validator('source_ids', mode='before')
    @classmethod
    def normalize_source_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError('source_ids must be a list of strings')
        normalized_ids: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError('source_ids must contain only strings')
            normalized = _reject_placeholder_source_id(item, field_name='source_ids')
            if normalized:
                normalized_ids.append(normalized)
        if len(normalized_ids) > 3:
            raise ValueError(
                'sources.tafsir.source_ids currently supports up to three Tafsir source ids for source-separated comparative Quran commentary selection.'
            )
        return normalized_ids


class HadithSourceControlsRequest(BaseModel):
    mode: Literal['auto', 'explicit_lookup_only'] | None = Field(default=None, description='Hadith source selection mode for bounded public Hadith lanes. Current runtime supports explicit citation lookup/explain. Public topical Hadith answering is currently disabled by default while corpus-native retrieval is deferred; broader unrestricted or mixed-source Hadith answering remains deferred.')
    collection_ids: list[str] = Field(default_factory=list, description='At most one Hadith collection source id is currently supported on the public surface.')

    @field_validator('collection_ids', mode='before')
    @classmethod
    def normalize_collection_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError('collection_ids must be a list of strings')
        normalized_ids: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError('collection_ids must contain only strings')
            normalized = _reject_placeholder_source_id(item, field_name='collection_ids')
            if normalized:
                normalized_ids.append(normalized)
        if len(normalized_ids) > 1:
            raise ValueError('sources.hadith.collection_ids currently supports at most one source id on the public surface')
        return normalized_ids


class AskSourcesRequest(BaseModel):
    quran: QuranSourceControlsRequest | None = None
    tafsir: TafsirSourceControlsRequest | None = None
    hadith: HadithSourceControlsRequest | None = None


class AskDiagnosticsRequest(BaseModel):
    debug: bool = False


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
                    'query': 'Explain 2:255 with tafsir',
                    'context': {'conversation_id': 'conv_123', 'anchor_refs': ['quran:2:255']},
                    'sources': {'tafsir': {'mode': 'required', 'limit': 3}},
                    'preferences': {'language': 'en', 'verbosity': 'standard', 'citations': 'inline'},
                    'diagnostics': {'debug': False},
                },
                {
                    'query': 'What does 112:1-4 say?',
                    'debug': False,
                },
            ]
        }
    )

    query: str = Field(..., min_length=1, description='Ask query for the canonical Ask surface.')
    context: AskContextRequest | None = Field(default=None, description='Conversation anchors and thread identifiers for follow-up aware clients.')
    preferences: AskPreferencesRequest | None = Field(default=None, description='Answer shaping preferences for the canonical Ask vNext contract. These are currently advisory-only hints in bounded public lanes unless otherwise stated by runtime policy.')
    sources: AskSourcesRequest | None = Field(default=None, description='Nested source controls for Quran, Tafsir, and Hadith.')
    diagnostics: AskDiagnosticsRequest | None = Field(default=None, description='Operational toggles such as debug.')
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
    hadith_source_id: str | None = Field(
        default=None,
        description=(
            'Optional governed Hadith collection source override for explicit Hadith citation lookup. '
            'Omit to use the bounded default collection.'
        ),
    )
    include_tafsir: bool | None = Field(
        default=None,
        description=(
            'Legacy flat control for Tafsir attachment. '
            'Prefer sources.tafsir.mode in the vNext request contract.'
        ),
    )
    tafsir_source_id: str | None = Field(
        default=None,
        description=(
            'Legacy flat source/work identifier for the Tafsir work to use when Tafsir is requested. '
            'Prefer sources.tafsir.source_ids in the vNext request contract.'
        ),
    )
    tafsir_limit: int = Field(
        default=3,
        ge=1,
        le=5,
        description='Legacy flat maximum number of overlapping Tafsir sections to return. Prefer sources.tafsir.limit in the vNext request contract.',
    )
    debug: bool = Field(default=False, description='Legacy debug toggle. Prefer diagnostics.debug in the vNext request contract.')

    @field_validator('quran_text_source_id', 'quran_translation_source_id', 'hadith_source_id', mode='before')
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

    @model_validator(mode='after')
    def validate_vnext_source_controls(self) -> 'AskSurfaceRequestBase':
        quran_controls = self.sources.quran if self.sources else None
        tafsir_controls = self.sources.tafsir if self.sources else None
        hadith_controls = self.sources.hadith if self.sources else None
        supplied_fields = self.model_fields_set

        if tafsir_controls and tafsir_controls.mode == 'off':
            if tafsir_controls.source_ids:
                raise ValueError('sources.tafsir.source_ids cannot be supplied when sources.tafsir.mode=off')
            if tafsir_controls.limit is not None:
                raise ValueError('sources.tafsir.limit cannot be supplied when sources.tafsir.mode=off because no Tafsir retrieval will run')

        _ensure_matching_alias(
            nested_value=(quran_controls.text_source_id if quran_controls else None),
            flat_value=self.quran_text_source_id if 'quran_text_source_id' in supplied_fields else None,
            nested_field='sources.quran.text_source_id',
            flat_field='quran_text_source_id',
        )
        _ensure_matching_alias(
            nested_value=(quran_controls.translation_source_id if quran_controls else None),
            flat_value=self.quran_translation_source_id if 'quran_translation_source_id' in supplied_fields else None,
            nested_field='sources.quran.translation_source_id',
            flat_field='quran_translation_source_id',
        )
        _ensure_matching_alias(
            nested_value=(_first_or_none(tafsir_controls.source_ids) if tafsir_controls else None),
            flat_value=self.tafsir_source_id if 'tafsir_source_id' in supplied_fields else None,
            nested_field='sources.tafsir.source_ids[0]',
            flat_field='tafsir_source_id',
        )
        _ensure_matching_alias(
            nested_value=(tafsir_controls.limit if tafsir_controls else None),
            flat_value=self.tafsir_limit if 'tafsir_limit' in supplied_fields else None,
            nested_field='sources.tafsir.limit',
            flat_field='tafsir_limit',
        )
        _ensure_matching_alias(
            nested_value=(_first_or_none(hadith_controls.collection_ids) if hadith_controls else None),
            flat_value=self.hadith_source_id if 'hadith_source_id' in supplied_fields else None,
            nested_field='sources.hadith.collection_ids[0]',
            flat_field='hadith_source_id',
        )

        nested_include_tafsir = None
        if tafsir_controls and tafsir_controls.mode is not None:
            if tafsir_controls.mode == 'required':
                nested_include_tafsir = True
            elif tafsir_controls.mode == 'off':
                nested_include_tafsir = False
        _ensure_matching_alias(
            nested_value=nested_include_tafsir,
            flat_value=self.include_tafsir if 'include_tafsir' in supplied_fields else None,
            nested_field='sources.tafsir.mode',
            flat_field='include_tafsir',
        )

        nested_debug = self.diagnostics.debug if self.diagnostics is not None else None
        _ensure_matching_alias(
            nested_value=nested_debug,
            flat_value=self.debug if 'debug' in supplied_fields else None,
            nested_field='diagnostics.debug',
            flat_field='debug',
        )
        return self

    @property
    def request_contract_version(self) -> str:
        return 'ask.vnext'

    @property
    def effective_quran_text_source_id(self) -> str | None:
        nested = self.sources.quran.text_source_id if self.sources and self.sources.quran else None
        return nested or self.quran_text_source_id

    @property
    def effective_quran_translation_source_id(self) -> str | None:
        nested = self.sources.quran.translation_source_id if self.sources and self.sources.quran else None
        return nested or self.quran_translation_source_id

    @property
    def effective_hadith_source_id(self) -> str | None:
        nested = None
        if self.sources and self.sources.hadith and self.sources.hadith.collection_ids:
            nested = self.sources.hadith.collection_ids[0]
        return nested or self.hadith_source_id

    @property
    def effective_tafsir_source_id(self) -> str | None:
        nested = None
        if self.sources and self.sources.tafsir and self.sources.tafsir.source_ids:
            nested = self.sources.tafsir.source_ids[0]
        return nested or self.tafsir_source_id
    
    @property
    def effective_tafsir_source_ids(self) -> list[str]:
        nested = list(self.sources.tafsir.source_ids) if self.sources and self.sources.tafsir else []
        if nested:
            return nested
        return [self.tafsir_source_id] if self.tafsir_source_id else []

    @property
    def effective_tafsir_limit(self) -> int:
        nested = self.sources.tafsir.limit if self.sources and self.sources.tafsir and self.sources.tafsir.limit is not None else None
        return nested if nested is not None else self.tafsir_limit

    @property
    def effective_include_tafsir(self) -> bool | None:
        nested_mode = self.sources.tafsir.mode if self.sources and self.sources.tafsir else None
        if nested_mode == 'off':
            return False
        if nested_mode == 'required':
            return True
        if nested_mode == 'auto':
            return None
        return self.include_tafsir

    @property
    def effective_debug(self) -> bool:
        if self.diagnostics is not None:
            return bool(self.diagnostics.debug)
        return bool(self.debug)

    @property
    def request_context_payload(self) -> dict[str, Any]:
        context = self.context or AskContextRequest()
        return {
            'conversation_id': context.conversation_id,
            'parent_turn_id': context.parent_turn_id,
            'anchor_refs': list(context.anchor_refs),
        }

    @property
    def request_preferences_payload(self) -> dict[str, Any]:
        preferences = self.preferences or AskPreferencesRequest()
        return {
            'language': preferences.language,
            'verbosity': preferences.verbosity,
            'citations': preferences.citations,
        }

    @property
    def source_controls_payload(self) -> dict[str, Any]:
        return {
            'quran': {
                'text_source_id': self.effective_quran_text_source_id,
                'translation_source_id': self.effective_quran_translation_source_id,
            },
            'tafsir': {
                'mode': (self.sources.tafsir.mode if self.sources and self.sources.tafsir else None) or ('required' if self.include_tafsir is True else 'off' if self.include_tafsir is False else 'auto'),
                'limit': self.effective_tafsir_limit,
                'source_ids': self.effective_tafsir_source_ids,
            },
            'hadith': {
                'mode': (self.sources.hadith.mode if self.sources and self.sources.hadith else None) or 'auto',
                'collection_ids': [self.effective_hadith_source_id] if self.effective_hadith_source_id else [],
            },
        }


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
                    'sources': {'tafsir': {'mode': 'required', 'limit': 2}},
                    'diagnostics': {'debug': False},
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


class SupportingHadith(BaseModel):
    """A supporting hadith surfaced alongside a primary topical-hadith answer.

    Phase 3 multi-hadith bundle. When the primary hadith is accompanied by
    additional topically-aligned records (because the query benefits from
    multi-source synthesis — e.g. "how did the prophet do ghusl?" draws on
    multiple narrations), this shape carries the secondary entries.

    Subset of the full HadithSupport projection — enough to display and cite.
    """
    citation_string: str | None = None
    canonical_ref: str | None = None
    collection_source_id: str | None = None
    collection_slug: str | None = None
    collection_hadith_number: int | None = None
    book_number: int | None = None
    chapter_number: int | None = None
    in_book_hadith_number: int | None = None
    reference_url: str | None = None
    in_book_reference_text: str | None = None
    book_title_en: str | None = None
    english_narrator: str | None = None
    english_text: str | None = None
    arabic_text: str | None = None
    grading_label: str | None = None
    grading_text: str | None = None
    snippet: str | None = None
    matched_topics: list[str] = []
    central_topic_score: float | None = None
    answerability_score: float | None = None
    guidance_role: str | None = None
    role: str = 'supporting'


class HadithSupport(BaseModel):
    citation_string: str
    canonical_ref: str
    canonical_ref_book_hadith: str | None = None
    canonical_ref_book_chapter_hadith: str | None = None
    collection_source_id: str
    collection_slug: str
    collection_hadith_number: int
    book_number: int
    chapter_number: int | None = None
    in_book_hadith_number: int | None = None
    reference_url: str | None = None
    in_book_reference_text: str | None = None
    public_collection_number: int | None = None
    book_title_en: str | None = None
    book_title_ar: str | None = None
    english_narrator: str | None = None
    english_text: str | None = None
    arabic_text: str | None = None
    grading_label: str | None = None
    grading_text: str | None = None
    numbering_quality: str | None = None
    # Phase 3: multi-hadith bundle — supporting hadiths surfaced alongside primary.
    supporting_hadiths: list[SupportingHadith] = []
    evidence_bundle_size: int | None = None
    role: str = 'primary'
    model_config = {'extra': 'allow'}


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
    selected_capability: str | None = None
    available_capabilities: list[str] = Field(default_factory=list)
    requested_text_source_id: str | None = None
    requested_translation_source_id: str | None = None
    selected_text_source_id: str | None = None
    selected_translation_source_id: str | None = None
    text_source_origin: str | None = None
    translation_source_origin: str | None = None


class TafsirDomainPolicyView(BaseModel):
    domain: str
    selected_capability: str | None = None
    available_capabilities: list[str] = Field(default_factory=list)
    requested: bool
    request_origin: str | None = None
    requested_source_id: str | None = None
    requested_source_ids: list[str] = Field(default_factory=list)
    selected_source_id: str | None = None
    selected_source_ids: list[str] = Field(default_factory=list)
    request_mode: str | None = None
    mode_enforced: bool = False
    allowed: bool
    included: bool
    policy_reason: str | None = None


class HadithDomainPolicyView(BaseModel):
    domain: str
    selected_capability: str | None = None
    available_capabilities: list[str] = Field(default_factory=list)
    requested: bool
    request_origin: str | None = None
    requested_source_id: str | None = None
    selected_source_id: str | None = None
    request_mode: str | None = None
    mode_enforced: bool = False
    allowed: bool
    included: bool
    approved_for_answering: bool = False
    answer_capability: str | None = None
    public_response_scope: str | None = None
    policy_reason: str | None = None


class SourcePolicyView(BaseModel):
    quran: QuranDomainPolicyView
    tafsir: TafsirDomainPolicyView
    hadith: HadithDomainPolicyView | None = None


class ConversationView(BaseModel):
    followup_ready: bool = False
    turn_id: str | None = None
    anchors: list[dict[str, Any]] = Field(default_factory=list)


class ExplainAnswerResponse(BaseModel):
    ok: bool
    query: str
    answer_mode: str
    terminal_state: str | None = None

    @model_validator(mode='before')
    @classmethod
    def ensure_terminal_state(cls, value: object) -> object:
        if isinstance(value, dict):
            data = dict(value)
            data['terminal_state'] = _infer_terminal_state_value(data)
            return data
        return value
    route_type: str
    action_type: str
    answer_text: str | None = None
    citations: list[SourceCitationView] = Field(default_factory=list)
    quran_support: QuranSupport | None = None
    hadith_support: HadithSupport | None = None
    tafsir_support: list[TafsirSupportItem] = Field(default_factory=list)
    resolution: dict[str, Any] | None = None
    partial_success: bool = False
    warnings: list[str] = Field(default_factory=list)
    quran_source_selection: QuranSourceSelection | None = None
    source_policy: SourcePolicyView | None = None
    orchestration: dict[str, Any] | None = Field(default=None, description='Internal canonical orchestration contract for planner/evidence introspection.')
    conversation: ConversationView | None = Field(default=None, description='Conversation anchors surfaced for follow-up capable clients.')
    composition: dict[str, Any] | None = Field(default=None, description='Canonical LLM-facing composition packet for bounded source-grounded answer rendering.')
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
    terminal_state: str | None = None

    @model_validator(mode='before')
    @classmethod
    def populate_terminal_state(cls, value: object) -> object:
        if isinstance(value, dict):
            data = dict(value)
            data['terminal_state'] = _infer_terminal_state_value(data)
            return data
        return value
    answer_text: str | None = None
    citations: list[SourceCitationView] = Field(default_factory=list)
    quran_support: QuranSupport | None = None
    hadith_support: HadithSupport | None = None
    tafsir_support: list[TafsirSupportItem] = Field(default_factory=list)
    resolution: dict[str, Any] | None = None
    partial_success: bool = False
    warnings: list[str] = Field(default_factory=list)
    quran_source_selection: QuranSourceSelection | None = None
    source_policy: SourcePolicyView | None = None
    orchestration: dict[str, Any] | None = Field(default=None, description='Internal canonical orchestration contract for planner/evidence introspection.')
    conversation: ConversationView | None = Field(default=None, description='Conversation anchors surfaced for follow-up capable clients.')
    composition: dict[str, Any] | None = Field(default=None, description='Canonical LLM-facing composition packet for bounded source-grounded answer rendering.')
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
