from __future__ import annotations

from fastapi import Request

from domains.ask.classifier import classify_ask_query, looks_like_anchored_followup_candidate
from domains.ask.observability import Timer, attach_observability, make_request_id
from domains.query_intelligence.hosted_normalization import normalize_query_for_routing
from domains.conversation.anchor_store import derive_anchor_session_key, hydrate_request_context, save_response_anchors
from domains.conversation.state_hydrator import hydrate_session_state
from domains.ask.response_surface import build_ask_response_payload
from domains.ask.workflows.explain_answer import explain_answer


def dispatch_ask_query(
    query: str,
    *,
    request: Request | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
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
) -> dict[str, object]:
    overall_timer = Timer()
    explicit_context = dict(request_context or {})
    header_conversation_id = None
    if request is not None:
        header_conversation_id = request.headers.get('x-conversation-id') or request.headers.get('x-dalil-conversation-id')

    has_conversation_handle = bool(
        explicit_context.get('conversation_id')
        or explicit_context.get('parent_turn_id')
        or header_conversation_id
    )

    request_id = make_request_id(request)
    normalization_timer = Timer()
    normalization = normalize_query_for_routing(query)
    normalize_ms = normalization_timer.elapsed_ms()

    session_key = derive_anchor_session_key(request, explicit_context)
    classify_timer = Timer()
    hydrated_request_context = hydrate_request_context(
        request_context=explicit_context,
        session_key=session_key,
        followup_like=looks_like_anchored_followup_candidate(query, normalized_query=normalization.normalized_query) or has_conversation_handle,
    )
    route = classify_ask_query(query, request_context=hydrated_request_context, normalization_result=normalization)
    classify_ms = classify_timer.elapsed_ms()

    answer_timer = Timer()
    result = explain_answer(
        query=query,
        request=request,
        route=route,
        include_tafsir=include_tafsir,
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
        quran_text_source_requested=quran_text_source_requested,
        quran_translation_source_requested=quran_translation_source_requested,
        hadith_source_id=hadith_source_id,
        request_context=hydrated_request_context,
        request_preferences=request_preferences,
        source_controls=source_controls,
        request_contract_version=request_contract_version,
        debug=debug,
    )
    answer_ms = answer_timer.elapsed_ms()

    payload_timer = Timer()
    payload = build_ask_response_payload(
        query=query,
        route=route,
        result=result,
    )
    payload_build_ms = payload_timer.elapsed_ms()

    persist_timer = Timer()
    conversation = payload.get('conversation')
    if isinstance(conversation, dict) and conversation.get('followup_ready'):
        session_state = hydrate_session_state(payload, request_context=hydrated_request_context)
        stored = save_response_anchors(
            session_key=str(hydrated_request_context.get('_anchor_session_key') or session_key or ''),
            anchors=list(conversation.get('anchors') or []),
            session_state_payload=session_state.to_payload(),
        )
        if stored is not None:
            conversation.setdefault('turn_id', stored.turn_id)
    persist_ms = persist_timer.elapsed_ms()

    payload = attach_observability(
        payload=payload,
        request_id=request_id,
        request_contract_version=request_contract_version,
        session_key=str(hydrated_request_context.get('_anchor_session_key') or session_key or ''),
        hydrated_request_context=hydrated_request_context,
        timings_ms={
            'normalize_query': normalize_ms,
            'classify_route': classify_ms,
            'build_answer': answer_ms,
            'build_payload': payload_build_ms,
            'persist_anchors': persist_ms,
            'total': overall_timer.elapsed_ms(),
        },
        debug_requested=debug,
    )
    return payload
