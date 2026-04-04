from __future__ import annotations

from fastapi import Request

from services.ask_router.classifier import classify_ask_query
from services.ask_router.heuristics import detect_tafsir_intent
from services.ask_router.route_types import AskActionType, AskRouteType
from services.answer_engine.plan_types import AbstainReason, AnswerMode, AnswerPlan, EvidenceDomain, SourceInvocationPlan
from services.source_registry.policies import can_mix_sources
from services.source_registry.registry import get_source_record, resolve_tafsir_source_for_explain


def _mode_from_action(action_type: str) -> AnswerMode:
    if action_type == AskActionType.FETCH_TEXT.value:
        return AnswerMode.FETCH_TEXT
    if action_type == AskActionType.VERIFY_SOURCE.value:
        return AnswerMode.VERIFY
    if action_type == AskActionType.VERIFY_THEN_EXPLAIN.value:
        return AnswerMode.VERIFY_THEN_EXPLAIN
    if action_type == AskActionType.EXPLAIN.value:
        return AnswerMode.EXPLAIN
    return AnswerMode.ABSTAIN


def _should_default_to_tafsir(route_type: str, mode: AnswerMode) -> bool:
    del route_type, mode
    return False


def build_answer_plan(
    query: str,
    *,
    request: Request | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
    database_url: str | None = None,
    debug: bool = False,
) -> AnswerPlan:
    route = classify_ask_query(query)
    route_type = route["route_type"]
    action_type = route.get("action_type", AskActionType.UNKNOWN.value)
    mode = _mode_from_action(action_type)

    if route_type == AskRouteType.UNSUPPORTED_FOR_NOW.value:
        return AnswerPlan(
            mode=AnswerMode.ABSTAIN,
            query=query,
            route_type=route_type,
            action_type=action_type,
            debug=debug,
            abstain_reason=AbstainReason.UNSUPPORTED_QUERY.value,
            route=route,
        )


    quran_plan = SourceInvocationPlan(domain=EvidenceDomain.QURAN, params={})

    tafsir_signal = detect_tafsir_intent(query)
    explicit_tafsir = bool(include_tafsir is True or tafsir_signal["matched"])
    default_tafsir = include_tafsir is None and _should_default_to_tafsir(route_type, mode)
    use_tafsir = explicit_tafsir or default_tafsir

    tafsir_plan = None
    allow_composition = False

    if route_type == AskRouteType.EXPLICIT_QURAN_REFERENCE.value and use_tafsir:
        quran_source = get_source_record("quran:tanzil-simple", database_url=database_url)
        selected_tafsir = resolve_tafsir_source_for_explain(
            tafsir_source_id if include_tafsir is True or tafsir_signal["matched"] else None,
            database_url=database_url,
        )
        if quran_source and selected_tafsir and can_mix_sources(quran_source, selected_tafsir):
            tafsir_plan = SourceInvocationPlan(
                domain=EvidenceDomain.TAFSIR,
                params={"source_id": selected_tafsir.source_id, "limit": int(tafsir_limit)},
            )
            allow_composition = True
        else:
            return AnswerPlan(
                mode=AnswerMode.ABSTAIN,
                query=query,
                route_type=route_type,
                action_type=action_type,
                debug=debug,
                quran_plan=quran_plan,
                tafsir_requested=use_tafsir,
                tafsir_explicit=explicit_tafsir,
                abstain_reason=AbstainReason.SOURCE_POLICY_BLOCKED.value,
                route=route,
            )

    return AnswerPlan(
        mode=mode,
        query=query,
        route_type=route_type,
        action_type=action_type,
        quran_plan=quran_plan,
        tafsir_plan=tafsir_plan,
        allow_composition=allow_composition,
        tafsir_requested=use_tafsir,
        tafsir_explicit=explicit_tafsir,
        debug=debug,
        route=route,
    )
