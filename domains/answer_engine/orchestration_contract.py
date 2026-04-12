from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from domains.answer_engine.evidence_pack import EvidencePack
from domains.ask.planner_types import AskPlan, TerminalState


def _resolve_hadith_numbering_quality(evidence: EvidencePack) -> str:
    raw = dict((evidence.hadith.raw if evidence.hadith else {}) or {})
    raw_quality = str(raw.get('numbering_quality') or '').strip()
    if raw_quality:
        return raw_quality
    if raw.get('reference_url') and raw.get('public_collection_number') is not None:
        return 'reference_url_linked'
    if 'hadith_bootstrap_numbering_unverified' in (evidence.warnings or []):
        return 'bootstrap_unverified'
    return 'collection_number_stable'
from domains.ask.request_control_honesty import build_request_control_honesty
from domains.ask.response_surface import describe_response_surfaces


@dataclass(slots=True)
class QueryInterpretation:
    primary_intent: str
    secondary_intents: list[str] = field(default_factory=list)
    query_class: str | None = None
    confidence: float | None = None
    signals: list[str] = field(default_factory=list)
    route_reason: str | None = None
    normalized_query: str | None = None
    route_type: str | None = None
    action_type: str | None = None


@dataclass(slots=True)
class DomainPlanDecision:
    domain: str
    eligible: bool
    selected: bool
    requested: bool = False
    policy_reason: str | None = None
    source_id: str | None = None
    request_origin: str | None = None
    selected_capability: str | None = None
    available_capabilities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvidenceItem:
    evidence_type: str
    domain: str
    source_id: str | None = None
    canonical_ref: str | None = None
    citation_text: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnswerBlock:
    block_type: str
    domain: str
    text: str
    title: str | None = None
    citations: list[str] = field(default_factory=list)
    source_id: str | None = None


@dataclass(slots=True)
class ConversationAnchor:
    anchor_type: str
    source_domain: str
    canonical_ref: str
    display_text: str


@dataclass(slots=True)
class CanonicalAnswer:
    mode: str
    terminal_state: str
    summary_text: str | None = None
    blocks: list[AnswerBlock] = field(default_factory=list)


@dataclass(slots=True)
class PolicySurface:
    source_policy: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    partial_success: bool = False


@dataclass(slots=True)
class OrchestrationEnvelope:
    request: dict[str, Any]
    interpretation: QueryInterpretation
    plan: dict[str, Any]
    answer: CanonicalAnswer
    evidence: list[EvidenceItem] = field(default_factory=list)
    conversation: dict[str, Any] = field(default_factory=dict)
    policy: PolicySurface = field(default_factory=PolicySurface)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _intent_from_plan(plan: AskPlan) -> str:
    if plan.should_abstain:
        return 'abstain'
    if plan.route_type == 'anchored_followup_hadith':
        return 'source_grounded_hadith_followup'
    if plan.route_type == 'anchored_followup_tafsir':
        return 'source_grounded_tafsir_followup'
    if plan.route_type == 'anchored_followup_quran':
        return 'source_grounded_quran_followup'
    response_mode = plan.response_mode.value if hasattr(plan.response_mode, 'value') else str(plan.response_mode)
    if response_mode in {'topical_tafsir', 'topical_hadith', 'topical_multi_source'}:
        return 'source_grounded_topical_retrieval'
    if plan.hadith_plan is not None:
        return 'source_grounded_hadith_lookup'
    if plan.requires_quran_verification and plan.use_tafsir:
        return 'source_grounded_quran_verification_with_tafsir'
    if plan.requires_quran_verification:
        return 'source_grounded_quran_verification'
    if plan.use_tafsir:
        return 'source_grounded_quran_explanation_with_tafsir'
    if plan.requires_quran_reference_resolution:
        return 'source_grounded_quran_explanation'
    return 'source_grounded_answer'


def _query_class(plan: AskPlan) -> str:
    if plan.route_type == 'anchored_followup_quran':
        return 'anchored_followup_quran'
    if plan.route_type == 'anchored_followup_tafsir':
        return 'anchored_followup_tafsir'
    if plan.route_type == 'anchored_followup_hadith':
        return 'anchored_followup_hadith'
    if plan.route_type == 'topical_tafsir_query':
        return 'topical_tafsir_query'
    if plan.route_type == 'topical_hadith_query':
        return 'topical_hadith_query'
    if plan.route_type == 'topical_multi_source_query':
        return 'topical_multi_source_query'
    if plan.hadith_plan is not None:
        return 'explicit_hadith_reference'
    if plan.requires_quran_verification and plan.tafsir_requested:
        return 'quoted_text_with_modifier'
    if plan.requires_quran_verification:
        return 'quoted_text'
    if plan.requires_quran_reference_resolution and plan.use_tafsir:
        return 'explicit_reference_with_modifier'
    if plan.requires_quran_reference_resolution:
        return 'explicit_reference'
    return 'unsupported'


def _build_interpretation(plan: AskPlan) -> QueryInterpretation:
    route = plan.route or {}
    secondary_intents: list[str] = []
    if plan.requires_quran_verification:
        secondary_intents.append('quote_verification')
    if plan.requires_quran_reference_resolution:
        secondary_intents.append('reference_resolution')
    if plan.tafsir_requested:
        secondary_intents.append('tafsir_request')
    if plan.hadith_requested:
        secondary_intents.append('hadith_citation_lookup' if plan.route_type in {'explicit_hadith_reference', 'anchored_followup_hadith'} else 'hadith_topic_request')
    if plan.route_type in {'anchored_followup_quran', 'anchored_followup_tafsir', 'anchored_followup_hadith'}:
        secondary_intents.append('anchored_followup')
    if plan.route_type in {'topical_tafsir_query', 'topical_hadith_query', 'topical_multi_source_query'}:
        secondary_intents.append('topical_retrieval')
    return QueryInterpretation(
        primary_intent=_intent_from_plan(plan),
        secondary_intents=secondary_intents,
        query_class=_query_class(plan),
        confidence=route.get('confidence'),
        signals=list(route.get('signals') or []),
        route_reason=route.get('reason'),
        normalized_query=route.get('normalized_query'),
        route_type=plan.route_type,
        action_type=plan.action_type,
    )


def _build_plan(plan: AskPlan) -> dict[str, Any]:
    decisions: list[DomainPlanDecision] = []
    if plan.source_policy is not None:
        decisions.append(DomainPlanDecision(domain='quran', eligible=bool(plan.source_policy.quran.allowed), selected=bool(plan.source_policy.quran.included), requested=bool(plan.quran_plan is not None), policy_reason=plan.source_policy.quran.policy_reason, source_id=plan.source_policy.quran.selected_text_source_id, request_origin=plan.source_policy.quran.text_source_origin, selected_capability=plan.source_policy.quran.selected_capability, available_capabilities=list(plan.source_policy.quran.available_capabilities)))
        decisions.append(DomainPlanDecision(domain='tafsir', eligible=bool(plan.source_policy.tafsir.allowed) or bool(plan.source_policy.tafsir.requested), selected=bool(plan.source_policy.tafsir.included), requested=bool(plan.source_policy.tafsir.requested), policy_reason=plan.source_policy.tafsir.policy_reason, source_id=plan.source_policy.tafsir.selected_source_id, request_origin=plan.source_policy.tafsir.request_origin, selected_capability=plan.source_policy.tafsir.selected_capability, available_capabilities=list(plan.source_policy.tafsir.available_capabilities)))
        if plan.source_policy.hadith is not None:
            decisions.append(DomainPlanDecision(domain='hadith', eligible=bool(plan.source_policy.hadith.allowed) or bool(plan.source_policy.hadith.requested), selected=bool(plan.source_policy.hadith.included), requested=bool(plan.source_policy.hadith.requested), policy_reason=plan.source_policy.hadith.policy_reason, source_id=plan.source_policy.hadith.selected_source_id, request_origin=plan.source_policy.hadith.request_origin, selected_capability=plan.source_policy.hadith.selected_capability, available_capabilities=list(plan.source_policy.hadith.available_capabilities)))
    return {
        'plan_type': plan.response_mode.value if hasattr(plan.response_mode, 'value') else str(plan.response_mode),
        'eligible_domains': [d.value if hasattr(d, 'value') else str(d) for d in plan.eligible_domains],
        'selected_domains': [d.value if hasattr(d, 'value') else str(d) for d in plan.selected_domains],
        'domain_decisions': [serialize_contract(x) for x in decisions],
        'abstain_reason': plan.abstain_reason.value if plan.abstain_reason else None,
        'notes': list(plan.notes),
        'planner_version': 'v1.6',
    }


def _build_answer(plan: AskPlan, evidence: EvidencePack, *, answer_text: str | None, tafsir_support: list[dict[str, Any]]) -> CanonicalAnswer:
    blocks: list[AnswerBlock] = []
    if evidence.quran is not None:
        blocks.append(AnswerBlock(block_type='quran_quote', domain='quran', title=evidence.quran.citation_string, text=evidence.quran.translation_text or evidence.quran.arabic_text or '', citations=[evidence.quran.canonical_source_id], source_id=evidence.quran.quran_source_id))
    if evidence.hadith is not None:
        mode_value = getattr(plan.response_mode, 'value', None) or str(plan.response_mode)
        hadith_block_type = 'hadith_explanation' if mode_value == 'hadith_explanation' else ('hadith_topic_support' if mode_value in {'topical_hadith', 'topical_multi_source'} else 'hadith_text')
        hadith_text = ' '.join(x for x in [evidence.hadith.english_narrator or '', evidence.hadith.english_text or ''] if x).strip()
        blocks.append(AnswerBlock(block_type=hadith_block_type, domain='hadith', title=evidence.hadith.citation_string, text=hadith_text, citations=[evidence.hadith.canonical_ref], source_id=evidence.hadith.source_id))
    for item in tafsir_support:
        block_type = 'tafsir_topic_support' if str(plan.route_type).startswith('topical_') else 'tafsir_support'
        blocks.append(AnswerBlock(block_type=block_type, domain='tafsir', title=item.get('display_text'), text=str(item.get('excerpt') or ''), citations=[str(item.get('canonical_section_id') or '')], source_id=item.get('source_id')))
    terminal_state = plan.terminal_state.value if hasattr(plan.terminal_state, 'value') else str(plan.terminal_state or TerminalState.ABSTAIN.value)
    return CanonicalAnswer(mode=plan.response_mode.value if hasattr(plan.response_mode, 'value') else str(plan.response_mode), terminal_state=terminal_state, summary_text=answer_text, blocks=blocks)


def _build_evidence(evidence: EvidencePack) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    if evidence.quran is not None:
        items.append(EvidenceItem(evidence_type='quran_span', domain='quran', source_id=evidence.quran.quran_source_id, canonical_ref=evidence.quran.canonical_source_id, citation_text=evidence.quran.citation_string, payload={'surah_no': evidence.quran.surah_no, 'ayah_start': evidence.quran.ayah_start, 'ayah_end': evidence.quran.ayah_end, 'surah_name_en': evidence.quran.surah_name_en, 'surah_name_ar': evidence.quran.surah_name_ar, 'translation_source_id': evidence.quran.translation_source_id}))
    if evidence.verifier_result is not None:
        best = (evidence.verifier_result or {}).get('best_match') or {}
        items.append(EvidenceItem(evidence_type='quran_verification', domain='quran', source_id=best.get('source_id'), canonical_ref=best.get('canonical_source_id'), citation_text=best.get('citation'), payload={'match_status': evidence.verifier_result.get('match_status'), 'confidence': evidence.verifier_result.get('confidence'), 'quote_payload': evidence.quote_payload, 'exact_match_count': len(evidence.verifier_result.get('exact_matches') or [])}))
    for item in evidence.tafsir:
        hit = item.hit
        items.append(EvidenceItem(evidence_type='tafsir_section', domain='tafsir', source_id=getattr(hit, 'source_id', None), canonical_ref=getattr(hit, 'canonical_section_id', None), citation_text=f"{getattr(hit, 'citation_label', 'Tafsir')} on Quran {getattr(hit, 'quran_span_ref', '')}", payload={'surah_no': getattr(hit, 'surah_no', None), 'ayah_start': getattr(hit, 'ayah_start', None), 'ayah_end': getattr(hit, 'ayah_end', None), 'coverage_mode': getattr(hit, 'coverage_mode', 'lexical_topic_match'), 'coverage_confidence': float(getattr(hit, 'coverage_confidence', getattr(hit, 'score', 0.0)) or 0.0), 'anchor_verse_key': getattr(hit, 'anchor_verse_key', None), 'quran_span_ref': getattr(hit, 'quran_span_ref', None), 'retrieval_method': getattr(hit, 'retrieval_method', None), 'matched_terms': list(getattr(hit, 'matched_terms', ()) or ())}))
    if evidence.hadith is not None:
        items.append(EvidenceItem(evidence_type='hadith_entry', domain='hadith', source_id=evidence.hadith.source_id, canonical_ref=evidence.hadith.canonical_ref, citation_text=evidence.hadith.citation_string, payload={'collection_hadith_number': evidence.hadith.collection_hadith_number, 'book_number': evidence.hadith.book_number, 'chapter_number': evidence.hadith.chapter_number, 'in_book_hadith_number': evidence.hadith.in_book_hadith_number, 'grading_label': evidence.hadith.grading_label, 'numbering_quality': _resolve_hadith_numbering_quality(evidence)}))
    return items


def _build_conversation(evidence: EvidencePack) -> dict[str, Any]:
    anchors: list[ConversationAnchor] = []
    if evidence.quran is not None:
        anchors.append(ConversationAnchor(anchor_type='quran_ref', source_domain='quran', canonical_ref=evidence.quran.canonical_source_id, display_text=evidence.quran.citation_string))
    for item in evidence.tafsir:
        anchors.append(ConversationAnchor(anchor_type='tafsir_section', source_domain='tafsir', canonical_ref=item.hit.canonical_section_id, display_text=f'{item.hit.citation_label} on Quran {item.hit.quran_span_ref}'))
    if evidence.hadith is not None:
        anchors.append(ConversationAnchor(anchor_type='hadith_ref', source_domain='hadith', canonical_ref=evidence.hadith.canonical_ref, display_text=evidence.hadith.citation_string))
    return {'followup_ready': bool(anchors), 'anchors': [serialize_contract(x) for x in anchors]}


def build_orchestration_envelope(*, plan: AskPlan, evidence: EvidencePack, answer_text: str | None, tafsir_support: list[dict[str, Any]], source_policy: dict[str, Any] | None, partial_success: bool) -> OrchestrationEnvelope:
    request_payload = {
        'contract_version': plan.request_contract_version,
        'query': plan.query,
        'route_type': plan.route_type,
        'action_type': plan.action_type,
        'context': dict(plan.request_context or {}),
        'preferences': dict(plan.request_preferences or {}),
        'sources': dict(plan.source_controls or {}),
        'control_honesty': build_request_control_honesty(plan),
    }
    return OrchestrationEnvelope(request=request_payload, interpretation=_build_interpretation(plan), plan=_build_plan(plan), answer=_build_answer(plan, evidence, answer_text=answer_text, tafsir_support=tafsir_support), evidence=_build_evidence(evidence), conversation=_build_conversation(evidence), policy=PolicySurface(source_policy=source_policy, warnings=list(evidence.warnings), errors=list(evidence.errors), partial_success=partial_success), diagnostics={'selected_domains': list(evidence.selected_domains), 'response_mode': evidence.response_mode, 'has_resolution': evidence.resolution is not None, 'has_verifier_result': evidence.verifier_result is not None, 'has_hadith': evidence.hadith is not None, 'response_surface_contract': describe_response_surfaces()})


def serialize_contract(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {k: serialize_contract(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): serialize_contract(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize_contract(v) for v in value]
    return value
