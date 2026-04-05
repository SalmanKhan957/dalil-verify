from __future__ import annotations

from fastapi import Request

from domains.ask.abstention import infer_unsupported_abstention_reason
from domains.ask.classifier import classify_ask_query
from domains.ask.heuristics import detect_tafsir_intent
from domains.ask.planner_types import (
    AbstentionReason,
    AskPlan,
    DomainInvocation,
    EvidenceDomain,
    EvidenceRequirement,
    ResponseMode,
)
from domains.ask.route_types import AskActionType, AskRouteType
from domains.policies.ask_source_policy import evaluate_ask_source_policy
from domains.quran.citations.resolver import resolve_quran_reference
from domains.quran.repositories.context import (
    resolve_quran_repository_context,
    resolve_requested_quran_repository_source_inputs,
)
from domains.quran.repositories.metadata_repository import load_quran_metadata
from domains.source_registry.registry import get_source_record


_IMPLICIT_DEFAULT = 'implicit_default'
_EXPLICIT_OVERRIDE = 'explicit_override'


def _response_mode_for_plan(
    *,
    route_type: str,
    action_type: str,
    use_tafsir: bool,
) -> ResponseMode:
    if route_type == AskRouteType.UNSUPPORTED_FOR_NOW.value:
        return ResponseMode.ABSTAIN

    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        if action_type == AskActionType.VERIFY_SOURCE.value:
            return ResponseMode.VERIFICATION_ONLY
        return ResponseMode.VERIFICATION_THEN_EXPLAIN

    if use_tafsir:
        return ResponseMode.QURAN_WITH_TAFSIR
    if action_type == AskActionType.FETCH_TEXT.value:
        return ResponseMode.QURAN_TEXT
    return ResponseMode.QURAN_EXPLANATION


def _base_plan(
    *,
    query: str,
    route: dict[str, object],
    debug: bool,
) -> AskPlan:
    route_type = str(route['route_type'])
    action_type = str(route.get('action_type', AskActionType.UNKNOWN.value))
    return AskPlan(
        query=query,
        route_type=route_type,
        action_type=action_type,
        response_mode=ResponseMode.ABSTAIN,
        route=route,
        debug=debug,
    )


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
    debug: bool = False,
) -> AskPlan:
    del request
    route = route or classify_ask_query(query)
    plan = _base_plan(query=query, route=route, debug=debug)
    route_type = plan.route_type
    action_type = plan.action_type

    if route_type == AskRouteType.UNSUPPORTED_FOR_NOW.value:
        plan.should_abstain = True
        plan.abstain_reason = infer_unsupported_abstention_reason(query, route)
        plan.response_mode = ResponseMode.ABSTAIN
        plan.notes.append(str(route.get('reason') or 'unsupported_query_type_for_now'))
        return plan

    requested_quran_source_id, requested_translation_source_id = resolve_requested_quran_repository_source_inputs(
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
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
    plan.quran_translation_source_origin = (
        _EXPLICIT_OVERRIDE if quran_translation_source_requested else _IMPLICIT_DEFAULT
    )
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

    if route_type == AskRouteType.EXPLICIT_QURAN_REFERENCE.value:
        plan.requires_quran_reference_resolution = True
        plan.evidence_requirements.extend(
            [EvidenceRequirement.QURAN_REFERENCE_RESOLUTION, EvidenceRequirement.QURAN_SPAN]
        )

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
        if not resolution.get('resolved'):
            plan.should_abstain = True
            plan.abstain_reason = AbstentionReason.NO_RESOLVED_REFERENCE
            plan.response_mode = ResponseMode.ABSTAIN
            plan.notes.append(str(resolution.get('error') or 'could_not_resolve_reference'))
            plan.source_policy = evaluate_ask_source_policy(
                route_type=route_type,
                include_tafsir=include_tafsir,
                tafsir_intent_detected=False,
                requested_tafsir_source_id=tafsir_source_id,
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

        tafsir_signal = detect_tafsir_intent(query)
        plan.source_policy = evaluate_ask_source_policy(
            route_type=route_type,
            include_tafsir=include_tafsir,
            tafsir_intent_detected=bool(tafsir_signal['matched']),
            requested_tafsir_source_id=tafsir_source_id,
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
            plan.tafsir_plan = DomainInvocation(
                domain=EvidenceDomain.TAFSIR,
                source_id=plan.source_policy.tafsir.selected_source_id,
                params={'source_id': plan.source_policy.tafsir.selected_source_id, 'limit': int(tafsir_limit)},
            )
            plan.notes.append(f"tafsir_source:{plan.source_policy.tafsir.selected_source_id}")
        elif plan.tafsir_requested:
            reason = plan.source_policy.tafsir.policy_reason
            if reason == 'tafsir_source_not_enabled':
                plan.should_abstain = True
                plan.abstain_reason = AbstentionReason.SOURCE_NOT_ENABLED
                plan.response_mode = ResponseMode.ABSTAIN
                plan.notes.append('tafsir_source_not_enabled')
                return plan
            if reason == 'quran_tafsir_composition_blocked':
                plan.should_abstain = True
                plan.abstain_reason = AbstentionReason.POLICY_RESTRICTED
                plan.response_mode = ResponseMode.ABSTAIN
                plan.notes.append('quran_tafsir_composition_blocked')
                return plan

    elif route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        plan.requires_quran_verification = True
        plan.evidence_requirements.append(EvidenceRequirement.QURAN_VERIFICATION)
        if action_type != AskActionType.VERIFY_SOURCE.value:
            plan.evidence_requirements.append(EvidenceRequirement.QURAN_SPAN)
        plan.source_policy = evaluate_ask_source_policy(
            route_type=route_type,
            include_tafsir=include_tafsir,
            tafsir_intent_detected=False,
            requested_tafsir_source_id=tafsir_source_id,
            quran_source=quran_source,
            requested_quran_text_source_id=requested_quran_source_id,
            requested_quran_translation_source_id=requested_translation_source_id,
            selected_quran_text_source_id=repository_context.quran_work_source_id,
            selected_quran_translation_source_id=repository_context.translation_work_source_id,
            quran_text_source_origin=plan.quran_text_source_origin,
            quran_translation_source_origin=plan.quran_translation_source_origin,
            database_url=repository_context.database_url,
        )
    else:
        plan.source_policy = evaluate_ask_source_policy(
            route_type=route_type,
            include_tafsir=include_tafsir,
            tafsir_intent_detected=False,
            requested_tafsir_source_id=tafsir_source_id,
            quran_source=quran_source,
            requested_quran_text_source_id=requested_quran_source_id,
            requested_quran_translation_source_id=requested_translation_source_id,
            selected_quran_text_source_id=repository_context.quran_work_source_id,
            selected_quran_translation_source_id=repository_context.translation_work_source_id,
            quran_text_source_origin=plan.quran_text_source_origin,
            quran_translation_source_origin=plan.quran_translation_source_origin,
            database_url=repository_context.database_url,
        )

    plan.response_mode = _response_mode_for_plan(
        route_type=route_type,
        action_type=action_type,
        use_tafsir=plan.use_tafsir,
    )
    return plan
