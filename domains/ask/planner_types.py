from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from domains.ask.source_policy_types import AskSourcePolicyDecision


class ResponseMode(str, Enum):
    QURAN_TEXT = 'quran_text'
    QURAN_EXPLANATION = 'quran_explanation'
    QURAN_WITH_TAFSIR = 'quran_with_tafsir'
    VERIFICATION_ONLY = 'verification_only'
    VERIFICATION_THEN_EXPLAIN = 'verification_then_explain'
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
    route: dict[str, Any] = field(default_factory=dict)
    debug: bool = False
    tafsir_requested: bool = False
    tafsir_explicit: bool = False
    repository_mode: str | None = None
    database_url: str | None = None
    quran_work_source_id: str | None = None
    translation_work_source_id: str | None = None
    source_resolution_strategy: str | None = None
    requested_quran_work_source_id: str | None = None
    requested_translation_work_source_id: str | None = None
    quran_text_source_origin: str | None = None
    quran_translation_source_origin: str | None = None
    quran_text_source_requested: bool = False
    quran_translation_source_requested: bool = False
    source_policy: AskSourcePolicyDecision | None = None

    @property
    def mode(self) -> ResponseMode:
        return self.response_mode

    @property
    def allow_composition(self) -> bool:
        return self.quran_plan is not None and self.tafsir_plan is not None and self.use_tafsir


# Backwards-compatible aliases for older imports while Phase 2 lands.
AnswerPlan = AskPlan
AnswerMode = ResponseMode
SourceInvocationPlan = DomainInvocation
