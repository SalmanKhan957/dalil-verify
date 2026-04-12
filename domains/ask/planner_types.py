from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from domains.ask.source_policy_types import AskSourcePolicyDecision
from domains.hadith.contracts import HadithCitationReference


class ResponseMode(str, Enum):
    QURAN_TEXT = 'quran_text'
    QURAN_EXPLANATION = 'quran_explanation'
    QURAN_WITH_TAFSIR = 'quran_with_tafsir'
    VERIFICATION_ONLY = 'verification_only'
    VERIFICATION_THEN_EXPLAIN = 'verification_then_explain'
    HADITH_TEXT = 'hadith_text'
    HADITH_EXPLANATION = 'hadith_explanation'
    TOPICAL_TAFSIR = 'topical_tafsir'
    TOPICAL_HADITH = 'topical_hadith'
    TOPICAL_MULTI_SOURCE = 'topical_multi_source'
    CLARIFY = 'clarify'
    ABSTAIN = 'abstain'


class TerminalState(str, Enum):
    ANSWERED = 'answered'
    CLARIFY = 'clarify'
    ABSTAIN = 'abstain'


class EvidenceDomain(str, Enum):
    QURAN = 'quran'
    TAFSIR = 'tafsir'
    HADITH = 'hadith'


class EvidenceRequirement(str, Enum):
    QURAN_REFERENCE_RESOLUTION = 'quran_reference_resolution'
    QURAN_SPAN = 'quran_span'
    QURAN_VERIFICATION = 'quran_verification'
    TAFSIR_OVERLAP = 'tafsir_overlap'
    TAFSIR_LEXICAL_RETRIEVAL = 'tafsir_lexical_retrieval'
    HADITH_CITATION_LOOKUP = 'hadith_citation_lookup'
    HADITH_LEXICAL_RETRIEVAL = 'hadith_lexical_retrieval'
    HADITH_TOPICAL_V2_CANDIDATE_GENERATION = 'hadith_topical_v2_candidate_generation'


class AbstentionReason(str, Enum):
    UNSUPPORTED_DOMAIN = 'unsupported_domain'
    UNSUPPORTED_CAPABILITY = 'unsupported_capability'
    NO_RESOLVED_REFERENCE = 'no_resolved_reference'
    SOURCE_NOT_ENABLED = 'source_not_enabled'
    INSUFFICIENT_EVIDENCE = 'insufficient_evidence'
    HADITH_NOT_SUPPORTED_YET = 'hadith_not_supported_yet'
    NEEDS_CLARIFICATION = 'needs_clarification'
    POLICY_RESTRICTED = 'policy_restricted'


@dataclass(slots=True)
class DomainInvocation:
    domain: EvidenceDomain
    enabled: bool = True
    source_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AskPlan:
    query: str
    route_type: str
    action_type: str
    response_mode: ResponseMode
    terminal_state: TerminalState = TerminalState.ABSTAIN
    eligible_domains: list[EvidenceDomain] = field(default_factory=list)
    selected_domains: list[EvidenceDomain] = field(default_factory=list)
    requires_quran_verification: bool = False
    requires_quran_reference_resolution: bool = False
    resolved_quran_ref: dict[str, Any] | None = None
    use_tafsir: bool = False
    evidence_requirements: list[EvidenceRequirement] = field(default_factory=list)
    should_abstain: bool = False
    abstain_reason: AbstentionReason | None = None
    notes: list[str] = field(default_factory=list)
    quran_plan: DomainInvocation | None = None
    tafsir_plan: DomainInvocation | None = None
    hadith_plan: DomainInvocation | None = None
    resolved_hadith_citation: HadithCitationReference | None = None
    route: dict[str, Any] = field(default_factory=dict)
    debug: bool = False
    tafsir_requested: bool = False
    tafsir_explicit: bool = False
    hadith_requested: bool = False
    repository_mode: str | None = None
    database_url: str | None = None
    quran_work_source_id: str | None = None
    translation_work_source_id: str | None = None
    source_resolution_strategy: str | None = None
    requested_quran_work_source_id: str | None = None
    requested_translation_work_source_id: str | None = None
    requested_hadith_source_id: str | None = None
    quran_text_source_origin: str | None = None
    quran_translation_source_origin: str | None = None
    quran_text_source_requested: bool = False
    quran_translation_source_requested: bool = False
    source_policy: AskSourcePolicyDecision | None = None
    request_context: dict[str, Any] = field(default_factory=dict)
    request_preferences: dict[str, Any] = field(default_factory=dict)
    source_controls: dict[str, Any] = field(default_factory=dict)
    request_contract_version: str = 'ask.vnext'
    topical_query: str | None = None
    clarify_prompt: str | None = None
    clarify_topics: list[str] = field(default_factory=list)

    @property
    def mode(self) -> ResponseMode:
        return self.response_mode

    @property
    def allow_composition(self) -> bool:
        return self.quran_plan is not None and self.tafsir_plan is not None and self.use_tafsir


AnswerPlan = AskPlan
AnswerMode = ResponseMode
SourceInvocationPlan = DomainInvocation
