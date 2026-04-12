from __future__ import annotations

from fastapi import Request

from domains.ask.abstention import infer_unsupported_abstention_reason
from domains.ask.classifier import classify_ask_query
from domains.ask.topical_query import detect_topical_query_intent
from domains.ask.heuristics import detect_tafsir_intent
from domains.ask.planner_types import (
    AbstentionReason,
    AskPlan,
    DomainInvocation,
    EvidenceDomain,
    EvidenceRequirement,
    ResponseMode,
    TerminalState,
)
from domains.ask.route_types import AskActionType, AskRouteType
from domains.ask.source_policy_types import AskSourcePolicyDecision, HadithSourcePolicyDecision, TafsirSourcePolicyDecision
from domains.hadith.citations.parser import parse_hadith_citation
from domains.hadith.contracts import HadithCitationReference
from domains.hadith.types import HadithReferenceType
from domains.policies.ask_source_policy import (
    build_not_requested_quran_policy,
    evaluate_ask_source_policy,
    evaluate_topical_hadith_source_policy,
    evaluate_topical_tafsir_source_policy,
)
from domains.quran.citations.resolver import resolve_quran_reference
from domains.quran.repositories.context import (
    resolve_quran_repository_context,
    resolve_requested_quran_repository_source_inputs,
)
from domains.quran.repositories.metadata_repository import load_quran_metadata
from domains.source_registry.registry import get_source_record


_IMPLICIT_DEFAULT = 'implicit_default'
_EXPLICIT_OVERRIDE = 'explicit_override'
_DEFAULT_COMPARATIVE_TAFSIR_SOURCE_IDS = [
    'tafsir:ibn-kathir-en',
    'tafsir:maarif-al-quran-en',
    'tafsir:tafheem-al-quran-en',
]


def _response_mode_for_plan(*, route_type: str, action_type: str, use_tafsir: bool) -> ResponseMode:
    if route_type == AskRouteType.BROAD_SOURCE_GROUNDED_QUERY.value:
        return ResponseMode.CLARIFY
    if route_type in {AskRouteType.POLICY_RESTRICTED_REQUEST.value, AskRouteType.UNSUPPORTED_FOR_NOW.value}:
        return ResponseMode.ABSTAIN
    if route_type in {AskRouteType.EXPLICIT_HADITH_REFERENCE.value, AskRouteType.ANCHORED_FOLLOWUP_HADITH.value}:
        if action_type == AskActionType.EXPLAIN.value:
            return ResponseMode.HADITH_EXPLANATION
        return ResponseMode.HADITH_TEXT
    if route_type == AskRouteType.TOPICAL_TAFSIR_QUERY.value:
        return ResponseMode.TOPICAL_TAFSIR
    if route_type == AskRouteType.TOPICAL_HADITH_QUERY.value:
        return ResponseMode.TOPICAL_HADITH
    if route_type == AskRouteType.TOPICAL_MULTI_SOURCE_QUERY.value:
        return ResponseMode.TOPICAL_MULTI_SOURCE
    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        if action_type == AskActionType.VERIFY_SOURCE.value:
            return ResponseMode.VERIFICATION_ONLY
        return ResponseMode.VERIFICATION_THEN_EXPLAIN
    if use_tafsir:
        return ResponseMode.QURAN_WITH_TAFSIR
    if action_type == AskActionType.FETCH_TEXT.value:
        return ResponseMode.QURAN_TEXT
    return ResponseMode.QURAN_EXPLANATION


def _base_plan(*, query: str, route: dict[str, object], debug: bool, request_context: dict[str, object] | None = None, request_preferences: dict[str, object] | None = None, source_controls: dict[str, object] | None = None, request_contract_version: str = 'ask.vnext') -> AskPlan:
    route_type = str(route['route_type'])
    action_type = str(route.get('action_type', AskActionType.UNKNOWN.value))
    return AskPlan(
        query=query,
        route_type=route_type,
        action_type=action_type,
        response_mode=ResponseMode.ABSTAIN,
        terminal_state=TerminalState.ABSTAIN,
        route=route,
        debug=debug,
        request_context=dict(request_context or {}),
        request_preferences=dict(request_preferences or {}),
        source_controls=dict(source_controls or {}),
        request_contract_version=request_contract_version,
    )


def _build_topical_source_policy(*, hadith_policy: HadithSourcePolicyDecision | None = None, tafsir_policy: TafsirSourcePolicyDecision | None = None) -> AskSourcePolicyDecision:
    return AskSourcePolicyDecision(
        quran=build_not_requested_quran_policy(),
        tafsir=tafsir_policy or TafsirSourcePolicyDecision(policy_reason='not_requested_for_route', selected_capability=None, available_capabilities=[]),
        hadith=hadith_policy or HadithSourcePolicyDecision(policy_reason='not_requested_for_route', available_capabilities=[]),
    )



def _requested_tafsir_source_ids(source_controls: dict[str, object] | None, legacy_tafsir_source_id: str | None) -> list[str]:
    values: list[str] = []
    tafsir_controls = source_controls.get('tafsir') if isinstance(source_controls, dict) else None
    if isinstance(tafsir_controls, dict):
        for item in list(tafsir_controls.get('source_ids') or []):
            cleaned = str(item or '').strip()
            if cleaned:
                values.append(cleaned)
    if legacy_tafsir_source_id:
        values = [legacy_tafsir_source_id, *values]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized

def _requested_hadith_mode(source_controls: dict[str, object] | None) -> str:
    hadith_controls = source_controls.get('hadith') if isinstance(source_controls, dict) else None
    if isinstance(hadith_controls, dict):
        mode = hadith_controls.get('mode')
        if isinstance(mode, str) and mode.strip():
            return mode.strip()
    return 'auto'



def _normalize_followup_quran_resolution(value: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    try:
        surah_no = int(value.get('surah_no'))
        ayah_start = int(value.get('ayah_start'))
        ayah_end = int(value.get('ayah_end') or ayah_start)
    except (TypeError, ValueError):
        return None
    canonical_ref = str(value.get('canonical_ref') or f'quran:{surah_no}:{ayah_start}-{ayah_end}' if ayah_end != ayah_start else f'quran:{surah_no}:{ayah_start}').strip()
    return {
        'resolved': True,
        'canonical_source_id': canonical_ref,
        'surah_no': surah_no,
        'ayah_start': ayah_start,
        'ayah_end': ayah_end,
        'parse_type': 'anchored_followup',
    }


def _anchored_tafsir_source_ids(route: dict[str, object], source_controls: dict[str, object] | None, legacy_tafsir_source_id: str | None) -> list[str]:
    route_ids = [str(item).strip() for item in list(route.get('requested_tafsir_source_ids') or []) if str(item).strip()]
    requested = _requested_tafsir_source_ids(source_controls, legacy_tafsir_source_id)
    merged: list[str] = []
    seen: set[str] = set()
    for value in route_ids + requested:
        if not value or value in seen:
            continue
        seen.add(value)
        merged.append(value)
    if merged:
        return merged
    return list(_DEFAULT_COMPARATIVE_TAFSIR_SOURCE_IDS)


def _configure_hadith_plan(
    plan: AskPlan,
    *,
    query: str,
    route: dict[str, object],
    action_type: str,
    database_url: str | None,
    policy_route_type: str | None = None,
) -> AskPlan:
    parsed_citation = route.get('parsed_hadith_citation') if isinstance(route, dict) else None
    citation = None
    if isinstance(parsed_citation, dict) and parsed_citation.get('reference_type'):
        citation = HadithCitationReference(
            collection_slug=str(parsed_citation.get('collection_slug') or '').strip(),
            collection_source_id=str(parsed_citation.get('collection_source_id') or 'hadith:sahih-al-bukhari-en').strip(),
            reference_type=HadithReferenceType(str(parsed_citation.get('reference_type'))),
            canonical_ref=str(parsed_citation.get('canonical_ref') or ''),
            hadith_number=(str(parsed_citation.get('hadith_number')) if parsed_citation.get('hadith_number') is not None else None),
            book_number=(int(parsed_citation['book_number']) if parsed_citation.get('book_number') is not None else None),
            chapter_number=(int(parsed_citation['chapter_number']) if parsed_citation.get('chapter_number') is not None else None),
            original_query=query,
        )
    if citation is None:
        citation = parse_hadith_citation(query)
    if citation is None:
        plan.should_abstain = True
        plan.abstain_reason = AbstentionReason.NEEDS_CLARIFICATION
        plan.response_mode = ResponseMode.ABSTAIN
        plan.terminal_state = TerminalState.ABSTAIN
        plan.notes.append('hadith_citation_parse_failed')
        plan.source_policy = evaluate_ask_source_policy(
            route_type=policy_route_type or plan.route_type,
            action_type=action_type,
            include_tafsir=None,
            tafsir_intent_detected=False,
            requested_tafsir_source_id=None,
            quran_source=None,
            requested_quran_text_source_id=None,
            requested_quran_translation_source_id=None,
            selected_quran_text_source_id=None,
            selected_quran_translation_source_id=None,
            quran_text_source_origin=None,
            quran_translation_source_origin=None,
            requested_hadith_source_id=None,
            requested_hadith_mode=_requested_hadith_mode(plan.source_controls),
            database_url=database_url,
        )
        return plan

    plan.database_url = database_url
    plan.resolved_hadith_citation = citation
    plan.hadith_requested = True
    plan.requested_hadith_source_id = citation.collection_source_id
    plan.evidence_requirements.append(EvidenceRequirement.HADITH_CITATION_LOOKUP)
    plan.source_policy = evaluate_ask_source_policy(
        route_type=policy_route_type or plan.route_type,
        action_type=action_type,
        include_tafsir=None,
        tafsir_intent_detected=False,
        requested_tafsir_source_id=None,
        quran_source=None,
        requested_quran_text_source_id=None,
        requested_quran_translation_source_id=None,
        selected_quran_text_source_id=None,
        selected_quran_translation_source_id=None,
        quran_text_source_origin=None,
        quran_translation_source_origin=None,
        requested_hadith_source_id=citation.collection_source_id,
        requested_hadith_mode=_requested_hadith_mode(plan.source_controls),
        database_url=database_url,
    )
    hadith_policy = plan.source_policy.hadith
    if hadith_policy is None or not hadith_policy.included or not hadith_policy.selected_source_id:
        plan.should_abstain = True
        plan.abstain_reason = AbstentionReason.SOURCE_NOT_ENABLED
        plan.response_mode = ResponseMode.ABSTAIN
        plan.terminal_state = TerminalState.ABSTAIN
        plan.notes.append(str((hadith_policy.policy_reason if hadith_policy else None) or 'hadith_collection_not_available'))
        return plan

    plan.eligible_domains.append(EvidenceDomain.HADITH)
    plan.selected_domains.append(EvidenceDomain.HADITH)
    plan.hadith_plan = DomainInvocation(
        domain=EvidenceDomain.HADITH,
        source_id=hadith_policy.selected_source_id,
        params={
            'source_id': hadith_policy.selected_source_id,
            'citation': citation,
            'answer_capability': hadith_policy.answer_capability,
            'retrieval_mode': 'citation',
        },
    )
    plan.notes.append(f'hadith_source:{hadith_policy.selected_source_id}')
    plan.response_mode = _response_mode_for_plan(route_type=plan.route_type, action_type=action_type, use_tafsir=False)
    plan.terminal_state = TerminalState.ANSWERED
    return plan


def _configure_topical_tafsir_plan(
    plan: AskPlan,
    *,
    route: dict[str, object],
    tafsir_source_id: str | None,
    tafsir_limit: int,
    database_url: str | None,
) -> AskPlan:
    topic_query = str(route.get('topic_query') or plan.query).strip()
    plan.topical_query = topic_query
    tafsir_policy = evaluate_topical_tafsir_source_policy(requested_tafsir_source_id=tafsir_source_id, database_url=database_url)
    plan.source_policy = _build_topical_source_policy(tafsir_policy=tafsir_policy)
    plan.tafsir_requested = True
    if tafsir_policy.included and tafsir_policy.selected_source_id:
        plan.eligible_domains.append(EvidenceDomain.TAFSIR)
        plan.selected_domains.append(EvidenceDomain.TAFSIR)
        plan.evidence_requirements.append(EvidenceRequirement.TAFSIR_LEXICAL_RETRIEVAL)
        plan.tafsir_plan = DomainInvocation(
            domain=EvidenceDomain.TAFSIR,
            source_id=tafsir_policy.selected_source_id,
            params={'source_id': tafsir_policy.selected_source_id, 'limit': int(tafsir_limit), 'query_text': topic_query, 'retrieval_mode': 'lexical', 'minimum_score': 0.6},
        )
        plan.response_mode = ResponseMode.TOPICAL_TAFSIR
        plan.terminal_state = TerminalState.ANSWERED
        plan.notes.append(f'tafsir_topic_source:{tafsir_policy.selected_source_id}')
        return plan
    plan.should_abstain = True
    plan.abstain_reason = AbstentionReason.SOURCE_NOT_ENABLED if tafsir_policy.policy_reason == 'tafsir_source_not_enabled' else AbstentionReason.POLICY_RESTRICTED
    plan.response_mode = ResponseMode.ABSTAIN
    plan.terminal_state = TerminalState.ABSTAIN
    plan.notes.append(str(tafsir_policy.policy_reason or 'topical_tafsir_not_available'))
    return plan


def _configure_topical_hadith_plan(
    plan: AskPlan,
    *,
    route: dict[str, object],
    hadith_source_id: str | None,
    tafsir_limit: int,
    database_url: str | None,
) -> AskPlan:
    topic_query = str(route.get('topic_query') or plan.query).strip()
    plan.topical_query = topic_query
    requested_hadith_mode = _requested_hadith_mode(plan.source_controls)
    hadith_policy = evaluate_topical_hadith_source_policy(requested_hadith_source_id=hadith_source_id, requested_hadith_mode=requested_hadith_mode, database_url=database_url)
    plan.source_policy = _build_topical_source_policy(hadith_policy=hadith_policy)
    plan.hadith_requested = True
    if hadith_policy.included and hadith_policy.selected_source_id:
        plan.eligible_domains.append(EvidenceDomain.HADITH)
        plan.selected_domains.append(EvidenceDomain.HADITH)
        plan.evidence_requirements.append(EvidenceRequirement.HADITH_LEXICAL_RETRIEVAL)
        plan.evidence_requirements.append(EvidenceRequirement.HADITH_TOPICAL_V2_CANDIDATE_GENERATION)
        plan.hadith_plan = DomainInvocation(
            domain=EvidenceDomain.HADITH,
            source_id=hadith_policy.selected_source_id,
            params={
                'source_id': hadith_policy.selected_source_id,
                'limit': max(5, int(tafsir_limit)),
                'query_text': topic_query,
                'retrieval_mode': 'topical_v2_shadow',
                'minimum_score': 0.6,
            },
        )
        plan.response_mode = ResponseMode.TOPICAL_HADITH
        plan.terminal_state = TerminalState.ANSWERED
        plan.notes.append(f'hadith_topic_source:{hadith_policy.selected_source_id}')
        plan.notes.append('hadith_topical_v2:shadow_runtime_enabled')
        return plan
    if plan.debug and hadith_policy.selected_source_id and hadith_policy.policy_reason == 'topical_hadith_temporarily_disabled':
        plan.hadith_plan = DomainInvocation(
            domain=EvidenceDomain.HADITH,
            source_id=hadith_policy.selected_source_id,
            params={
                'source_id': hadith_policy.selected_source_id,
                'limit': max(5, int(tafsir_limit)),
                'query_text': topic_query,
                'retrieval_mode': 'topical_v2_shadow',
                'minimum_score': 0.6,
                'shadow_only': True,
            },
        )
        plan.evidence_requirements.append(EvidenceRequirement.HADITH_LEXICAL_RETRIEVAL)
        plan.evidence_requirements.append(EvidenceRequirement.HADITH_TOPICAL_V2_CANDIDATE_GENERATION)
        plan.notes.append(f'hadith_topic_source:{hadith_policy.selected_source_id}')
        plan.notes.append('hadith_topical_v2:shadow_only_debug')

    plan.should_abstain = True
    plan.abstain_reason = AbstentionReason.POLICY_RESTRICTED
    plan.response_mode = ResponseMode.ABSTAIN
    plan.terminal_state = TerminalState.ABSTAIN
    plan.notes.append(str(hadith_policy.policy_reason or 'topical_hadith_not_available'))
    return plan


def _configure_topical_multisource_plan(
    plan: AskPlan,
    *,
    route: dict[str, object],
    tafsir_source_id: str | None,
    tafsir_limit: int,
    hadith_source_id: str | None,
    database_url: str | None,
) -> AskPlan:
    topic_query = str(route.get('topic_query') or plan.query).strip()
    plan.topical_query = topic_query
    tafsir_policy = evaluate_topical_tafsir_source_policy(requested_tafsir_source_id=tafsir_source_id, database_url=database_url)
    requested_hadith_mode = _requested_hadith_mode(plan.source_controls)
    hadith_policy = evaluate_topical_hadith_source_policy(requested_hadith_source_id=hadith_source_id, requested_hadith_mode=requested_hadith_mode, database_url=database_url)
    plan.source_policy = _build_topical_source_policy(hadith_policy=hadith_policy, tafsir_policy=tafsir_policy)

    if tafsir_policy.included and tafsir_policy.selected_source_id:
        plan.tafsir_requested = True
        plan.eligible_domains.append(EvidenceDomain.TAFSIR)
        plan.selected_domains.append(EvidenceDomain.TAFSIR)
        plan.evidence_requirements.append(EvidenceRequirement.TAFSIR_LEXICAL_RETRIEVAL)
        plan.tafsir_plan = DomainInvocation(
            domain=EvidenceDomain.TAFSIR,
            source_id=tafsir_policy.selected_source_id,
            params={'source_id': tafsir_policy.selected_source_id, 'limit': int(tafsir_limit), 'query_text': topic_query, 'retrieval_mode': 'lexical', 'minimum_score': 0.6},
        )
        plan.notes.append(f'tafsir_topic_source:{tafsir_policy.selected_source_id}')

    if hadith_policy.included and hadith_policy.selected_source_id:
        plan.hadith_requested = True
        plan.eligible_domains.append(EvidenceDomain.HADITH)
        plan.selected_domains.append(EvidenceDomain.HADITH)
        plan.evidence_requirements.append(EvidenceRequirement.HADITH_LEXICAL_RETRIEVAL)
        plan.hadith_plan = DomainInvocation(
            domain=EvidenceDomain.HADITH,
            source_id=hadith_policy.selected_source_id,
            params={'source_id': hadith_policy.selected_source_id, 'limit': int(tafsir_limit), 'query_text': topic_query, 'retrieval_mode': 'lexical', 'minimum_score': 0.6},
        )
        plan.notes.append(f'hadith_topic_source:{hadith_policy.selected_source_id}')

    if not plan.selected_domains:
        plan.should_abstain = True
        plan.abstain_reason = AbstentionReason.POLICY_RESTRICTED
        plan.response_mode = ResponseMode.ABSTAIN
        plan.terminal_state = TerminalState.ABSTAIN
        plan.notes.append('no_topical_domains_selected')
        return plan

    if plan.tafsir_plan is None:
        plan.notes.append(str(tafsir_policy.policy_reason or 'topical_tafsir_not_available'))
    if plan.hadith_plan is None:
        plan.notes.append(str(hadith_policy.policy_reason or 'topical_hadith_not_available'))

    if plan.tafsir_plan is not None and plan.hadith_plan is not None:
        plan.response_mode = ResponseMode.TOPICAL_MULTI_SOURCE
    elif plan.tafsir_plan is not None:
        plan.response_mode = ResponseMode.TOPICAL_TAFSIR
    else:
        plan.response_mode = ResponseMode.TOPICAL_HADITH
    plan.terminal_state = TerminalState.ANSWERED if not plan.should_abstain else TerminalState.ABSTAIN
    return plan


def build_ask_plan(
    query: str,
    *,
    route: dict[str, object] | None = None,
    request: Request | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = None,
    tafsir_limit: int = 3,
    database_url: str | None = None,
    repository_mode: str | None = None,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
    quran_text_source_requested: bool = False,
    quran_translation_source_requested: bool = False,
    hadith_source_id: str | None = None,
    request_context: dict[str, object] | None = None,
    request_preferences: dict[str, object] | None = None,
    source_controls: dict[str, object] | None = None,
    request_contract_version: str = 'ask.vnext',
    debug: bool = False,
) -> AskPlan:
    del request
    route_was_supplied = route is not None
    route = route or classify_ask_query(query, request_context=request_context)
    if not route_was_supplied and str(route.get('route_type')) == AskRouteType.UNSUPPORTED_FOR_NOW.value:
        topical_route = detect_topical_query_intent(query, allow_multi_source=True)
        if topical_route.get('matched'):
            route = topical_route
    plan = _base_plan(query=query, route=route, debug=debug, request_context=request_context, request_preferences=request_preferences, source_controls=source_controls, request_contract_version=request_contract_version)
    route_type = plan.route_type
    action_type = plan.action_type

    if route_type == AskRouteType.BROAD_SOURCE_GROUNDED_QUERY.value:
        clarify = route.get('clarify') if isinstance(route.get('clarify'), dict) else {}
        plan.response_mode = ResponseMode.CLARIFY
        plan.terminal_state = TerminalState.CLARIFY
        plan.clarify_prompt = str(clarify.get('prompt') or 'This request is too broad and needs clarification.').strip()
        plan.clarify_topics = [str(value) for value in list(clarify.get('suggested_topics') or []) if str(value).strip()]
        plan.notes.append(str(route.get('reason') or 'needs_clarification'))
        return plan

    if route_type in {AskRouteType.POLICY_RESTRICTED_REQUEST.value, AskRouteType.UNSUPPORTED_FOR_NOW.value}:
        plan.should_abstain = True
        if route_type == AskRouteType.POLICY_RESTRICTED_REQUEST.value:
            plan.abstain_reason = AbstentionReason.POLICY_RESTRICTED
        else:
            plan.abstain_reason = infer_unsupported_abstention_reason(query, route)
        plan.response_mode = ResponseMode.ABSTAIN
        plan.terminal_state = TerminalState.ABSTAIN
        plan.notes.append(str(route.get('reason') or 'unsupported_query_type_for_now'))
        return plan

    if route_type in {AskRouteType.EXPLICIT_HADITH_REFERENCE.value, AskRouteType.ANCHORED_FOLLOWUP_HADITH.value}:
        if hadith_source_id and isinstance(plan.route.get('parsed_hadith_citation'), dict):
            plan.route['parsed_hadith_citation']['collection_source_id'] = hadith_source_id
        if route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value:
            plan.notes.append('anchored_followup_hadith')
        return _configure_hadith_plan(
            plan,
            query=query,
            route=route,
            action_type=AskActionType.EXPLAIN.value if route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value else action_type,
            database_url=database_url,
            policy_route_type=AskRouteType.EXPLICIT_HADITH_REFERENCE.value if route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value else None,
        )

    if route_type == AskRouteType.TOPICAL_TAFSIR_QUERY.value:
        return _configure_topical_tafsir_plan(plan, route=route, tafsir_source_id=tafsir_source_id, tafsir_limit=tafsir_limit, database_url=database_url)

    if route_type == AskRouteType.TOPICAL_HADITH_QUERY.value:
        return _configure_topical_hadith_plan(plan, route=route, hadith_source_id=hadith_source_id, tafsir_limit=tafsir_limit, database_url=database_url)

    if route_type == AskRouteType.TOPICAL_MULTI_SOURCE_QUERY.value:
        return _configure_topical_multisource_plan(plan, route=route, tafsir_source_id=tafsir_source_id, tafsir_limit=tafsir_limit, hadith_source_id=hadith_source_id, database_url=database_url)

    requested_quran_source_id, requested_translation_source_id = resolve_requested_quran_repository_source_inputs(
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
    requested_tafsir_source_ids = _requested_tafsir_source_ids(source_controls, tafsir_source_id)

    repository_context = resolve_quran_repository_context(
        repository_mode=repository_mode,
        database_url=database_url,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
    plan.repository_mode = repository_context.repository_mode
    plan.database_url = repository_context.database_url
    plan.quran_work_source_id = repository_context.quran_work_source_id
    plan.translation_work_source_id = repository_context.translation_work_source_id
    plan.source_resolution_strategy = repository_context.source_resolution_strategy
    plan.requested_quran_work_source_id = requested_quran_source_id
    plan.requested_translation_work_source_id = requested_translation_source_id
    plan.quran_text_source_requested = quran_text_source_requested
    plan.quran_translation_source_requested = quran_translation_source_requested
    plan.quran_text_source_origin = _EXPLICIT_OVERRIDE if quran_text_source_requested else _IMPLICIT_DEFAULT
    plan.quran_translation_source_origin = _EXPLICIT_OVERRIDE if quran_translation_source_requested else _IMPLICIT_DEFAULT
    plan.quran_plan = DomainInvocation(
        domain=EvidenceDomain.QURAN,
        source_id=repository_context.quran_work_source_id,
        params={
            'repository_mode': repository_context.repository_mode,
            'database_url': repository_context.database_url,
            'quran_work_source_id': repository_context.quran_work_source_id,
            'translation_work_source_id': repository_context.translation_work_source_id,
        },
    )
    plan.eligible_domains.append(EvidenceDomain.QURAN)
    plan.selected_domains.append(EvidenceDomain.QURAN)

    quran_source = get_source_record(repository_context.quran_work_source_id, database_url=repository_context.database_url)

    if route_type in {AskRouteType.EXPLICIT_QURAN_REFERENCE.value, AskRouteType.ANCHORED_FOLLOWUP_QURAN.value, AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value}:
        plan.requires_quran_reference_resolution = True
        plan.evidence_requirements.extend([EvidenceRequirement.QURAN_REFERENCE_RESOLUTION, EvidenceRequirement.QURAN_SPAN])
        policy_route_type = route_type
        policy_action_type = action_type

        if route_type == AskRouteType.ANCHORED_FOLLOWUP_QURAN.value:
            policy_route_type = AskRouteType.EXPLICIT_QURAN_REFERENCE.value
            policy_action_type = AskActionType.EXPLAIN.value
        followup_resolution = _normalize_followup_quran_resolution(route.get('followup_quran_ref') if isinstance(route, dict) else None)
        if followup_resolution is not None:
            resolution = followup_resolution
            plan.notes.append('anchored_followup_quran')
        else:
            reference_text = str(route.get('reference_text') or query)
            resolution = resolve_quran_reference(
                reference_text,
                quran_metadata=load_quran_metadata(
                    repository_mode=repository_context.repository_mode,
                    database_url=repository_context.database_url,
                    work_source_id=repository_context.quran_work_source_id,
                ),
            )
        plan.resolved_quran_ref = resolution
        tafsir_signal = detect_tafsir_intent(query)
        tafsir_intent_detected = bool(tafsir_signal['matched']) or route_type == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value
        # Product rule: whenever Quran explanation is requested, Tafsir is included by default
        # unless the caller explicitly suppresses it (sources.tafsir.mode = off / include_tafsir=False).
        # Preserve query-driven tafsir intent semantics when the user explicitly asked for tafsir.
        effective_include_tafsir = include_tafsir
        if include_tafsir is None:
            if route_type == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value:
                effective_include_tafsir = True
            elif route_type == AskRouteType.ANCHORED_FOLLOWUP_QURAN.value:
                effective_include_tafsir = True
            elif action_type == AskActionType.EXPLAIN.value and not tafsir_intent_detected:
                effective_include_tafsir = True
        effective_requested_tafsir_source_ids = requested_tafsir_source_ids
        if route_type == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value:
            effective_requested_tafsir_source_ids = _anchored_tafsir_source_ids(route, source_controls, tafsir_source_id)
            plan.notes.append('anchored_followup_tafsir')
        if not resolution.get('resolved'):
            plan.should_abstain = True
            plan.abstain_reason = AbstentionReason.NO_RESOLVED_REFERENCE
            plan.response_mode = ResponseMode.ABSTAIN
            plan.terminal_state = TerminalState.ABSTAIN
            plan.notes.append(str(resolution.get('error') or 'could_not_resolve_reference'))
            plan.source_policy = evaluate_ask_source_policy(
                route_type=policy_route_type,
                action_type=policy_action_type,
                include_tafsir=effective_include_tafsir,
                tafsir_intent_detected=tafsir_intent_detected,
                requested_tafsir_source_id=tafsir_source_id,
                requested_tafsir_source_ids=effective_requested_tafsir_source_ids,
                quran_source=quran_source,
                requested_quran_text_source_id=requested_quran_source_id,
                requested_quran_translation_source_id=requested_translation_source_id,
                selected_quran_text_source_id=repository_context.quran_work_source_id,
                selected_quran_translation_source_id=repository_context.translation_work_source_id,
                quran_text_source_origin=plan.quran_text_source_origin,
                quran_translation_source_origin=plan.quran_translation_source_origin,
                database_url=repository_context.database_url,
            )
            return plan

        plan.source_policy = evaluate_ask_source_policy(
            route_type=policy_route_type,
            action_type=policy_action_type,
            include_tafsir=effective_include_tafsir,
            tafsir_intent_detected=tafsir_intent_detected,
            requested_tafsir_source_id=tafsir_source_id,
            requested_tafsir_source_ids=effective_requested_tafsir_source_ids,
            quran_source=quran_source,
            requested_quran_text_source_id=requested_quran_source_id,
            requested_quran_translation_source_id=requested_translation_source_id,
            selected_quran_text_source_id=repository_context.quran_work_source_id,
            selected_quran_translation_source_id=repository_context.translation_work_source_id,
            quran_text_source_origin=plan.quran_text_source_origin,
            quran_translation_source_origin=plan.quran_translation_source_origin,
            database_url=repository_context.database_url,
        )

        plan.use_tafsir = bool(plan.source_policy.tafsir.included)
        plan.tafsir_requested = bool(plan.source_policy.tafsir.requested)
        plan.tafsir_explicit = plan.source_policy.tafsir.request_origin == 'explicit_flag'

        if plan.source_policy.tafsir.policy_reason == 'suppressed_by_request':
            plan.notes.append('tafsir_suppressed_by_request')
        elif plan.source_policy.tafsir.policy_reason == 'route_not_eligible_for_tafsir':
            plan.notes.append('tafsir_route_not_eligible')

        if plan.use_tafsir:
            plan.eligible_domains.append(EvidenceDomain.TAFSIR)
            plan.selected_domains.append(EvidenceDomain.TAFSIR)
            plan.evidence_requirements.append(EvidenceRequirement.TAFSIR_OVERLAP)
            selected_tafsir_source_ids = list(getattr(plan.source_policy.tafsir, 'selected_source_ids', []) or [])
            if not selected_tafsir_source_ids and plan.source_policy.tafsir.selected_source_id:
                selected_tafsir_source_ids = [plan.source_policy.tafsir.selected_source_id]
            plan.tafsir_plan = DomainInvocation(
                domain=EvidenceDomain.TAFSIR,
                source_id=plan.source_policy.tafsir.selected_source_id,
                params={'source_id': plan.source_policy.tafsir.selected_source_id, 'source_ids': selected_tafsir_source_ids, 'limit': int(tafsir_limit), 'retrieval_mode': 'overlap'},
            )
            for source_id in selected_tafsir_source_ids:
                plan.notes.append(f"tafsir_source:{source_id}")
        elif plan.tafsir_requested:
            reason = plan.source_policy.tafsir.policy_reason
            if reason == 'tafsir_source_not_enabled':
                plan.should_abstain = True
                plan.abstain_reason = AbstentionReason.SOURCE_NOT_ENABLED
                plan.response_mode = ResponseMode.ABSTAIN
                plan.terminal_state = TerminalState.ABSTAIN
                plan.notes.append('tafsir_source_not_enabled')
                return plan
            if reason == 'quran_tafsir_composition_blocked':
                plan.should_abstain = True
                plan.abstain_reason = AbstentionReason.POLICY_RESTRICTED
                plan.response_mode = ResponseMode.ABSTAIN
                plan.terminal_state = TerminalState.ABSTAIN
                plan.notes.append('quran_tafsir_composition_blocked')
                return plan

    elif route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        plan.requires_quran_verification = True
        plan.evidence_requirements.append(EvidenceRequirement.QURAN_VERIFICATION)
        if action_type != AskActionType.VERIFY_SOURCE.value:
            plan.evidence_requirements.append(EvidenceRequirement.QURAN_SPAN)
        tafsir_signal = detect_tafsir_intent(query)
        plan.source_policy = evaluate_ask_source_policy(
            route_type=route_type,
            action_type=action_type,
            include_tafsir=include_tafsir,
            tafsir_intent_detected=bool(tafsir_signal['matched']),
            requested_tafsir_source_id=tafsir_source_id,
            requested_tafsir_source_ids=requested_tafsir_source_ids,
            quran_source=quran_source,
            requested_quran_text_source_id=requested_quran_source_id,
            requested_quran_translation_source_id=requested_translation_source_id,
            selected_quran_text_source_id=repository_context.quran_work_source_id,
            selected_quran_translation_source_id=repository_context.translation_work_source_id,
            quran_text_source_origin=plan.quran_text_source_origin,
            quran_translation_source_origin=plan.quran_translation_source_origin,
            database_url=repository_context.database_url,
        )
        plan.use_tafsir = bool(plan.source_policy.tafsir.included)
        plan.tafsir_requested = bool(plan.source_policy.tafsir.requested)
        plan.tafsir_explicit = plan.source_policy.tafsir.request_origin == 'explicit_flag'
        if plan.use_tafsir:
            plan.eligible_domains.append(EvidenceDomain.TAFSIR)
            plan.selected_domains.append(EvidenceDomain.TAFSIR)
            plan.evidence_requirements.append(EvidenceRequirement.TAFSIR_OVERLAP)
            selected_tafsir_source_ids = list(getattr(plan.source_policy.tafsir, 'selected_source_ids', []) or [])
            if not selected_tafsir_source_ids and plan.source_policy.tafsir.selected_source_id:
                selected_tafsir_source_ids = [plan.source_policy.tafsir.selected_source_id]
            plan.tafsir_plan = DomainInvocation(
                domain=EvidenceDomain.TAFSIR,
                source_id=plan.source_policy.tafsir.selected_source_id,
                params={'source_id': plan.source_policy.tafsir.selected_source_id, 'source_ids': selected_tafsir_source_ids, 'limit': int(tafsir_limit), 'retrieval_mode': 'overlap'},
            )
            for source_id in selected_tafsir_source_ids:
                plan.notes.append(f"tafsir_source:{source_id}")
        elif plan.source_policy.tafsir.policy_reason == 'suppressed_by_request':
            plan.notes.append('tafsir_suppressed_by_request')
    else:
        plan.source_policy = evaluate_ask_source_policy(
            route_type=route_type,
            action_type=action_type,
            include_tafsir=include_tafsir,
            tafsir_intent_detected=bool(tafsir_signal['matched']),
            requested_tafsir_source_id=tafsir_source_id,
            requested_tafsir_source_ids=requested_tafsir_source_ids,
            quran_source=quran_source,
            requested_quran_text_source_id=requested_quran_source_id,
            requested_quran_translation_source_id=requested_translation_source_id,
            selected_quran_text_source_id=repository_context.quran_work_source_id,
            selected_quran_translation_source_id=repository_context.translation_work_source_id,
            quran_text_source_origin=plan.quran_text_source_origin,
            quran_translation_source_origin=plan.quran_translation_source_origin,
            database_url=repository_context.database_url,
        )

    plan.response_mode = _response_mode_for_plan(route_type=route_type, action_type=action_type, use_tafsir=plan.use_tafsir)
    plan.terminal_state = TerminalState.ANSWERED
    return plan
