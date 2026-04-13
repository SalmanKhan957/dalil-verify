from __future__ import annotations

from typing import Any

from .quran_followup import contains_ref, parse_quran_ref
from .session_state import ActiveScope, ConversationAnchorSet, SessionState


_QURAN_PREFIX = "quran:"
_HADITH_PREFIX = "hadith:"
_TAFSIR_PREFIX = "tafsir:"


def _clean(value: Any) -> str | None:
    text = str(value or '').strip()
    return text or None


def _dedup(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or '').strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _collect_citation_refs(response_payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in response_payload.get("citations") or []:
        if not isinstance(item, dict):
            continue
        canonical_ref = _clean(item.get("canonical_ref"))
        if canonical_ref and canonical_ref not in refs:
            refs.append(canonical_ref)
    return refs


def _collect_active_source_ids(response_payload: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []
    for item in response_payload.get("citations") or []:
        if not isinstance(item, dict):
            continue
        source_id = _clean(item.get("source_id"))
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def _previous_scope_from_request_context(request_context: dict[str, Any] | None) -> ActiveScope | None:
    if not isinstance(request_context, dict):
        return None
    snapshot = request_context.get('_hydrated_session_state') if isinstance(request_context.get('_hydrated_session_state'), dict) else None
    if snapshot:
        return SessionState.from_payload(snapshot, raw_context=request_context).scope
    return None


def _derive_quran_span_ref(*, quran_ref: str | None, previous_scope: ActiveScope | None) -> str | None:
    if quran_ref is None:
        return previous_scope.quran_span_ref if previous_scope is not None else None
    if previous_scope is None:
        return quran_ref
    previous_span_ref = previous_scope.quran_span_ref or previous_scope.quran_ref
    if contains_ref(previous_span_ref, quran_ref):
        return previous_span_ref
    current = parse_quran_ref(quran_ref)
    previous = parse_quran_ref(previous_span_ref)
    if current is not None and previous is not None and current.canonical_ref == previous.canonical_ref:
        return previous.canonical_ref
    return quran_ref


def _derive_scope(response_payload: dict[str, Any], *, previous_scope: ActiveScope | None = None) -> ActiveScope:
    answer_mode = _clean(response_payload.get("answer_mode"))
    route_type = _clean(response_payload.get("route_type"))

    domains: list[str] = []
    quran_ref: str | None = None
    displayed_tafsir_source_ids: list[str] = []
    hadith_ref: str | None = None
    hadith_source_id: str | None = None

    quran_support = response_payload.get("quran_support")
    if isinstance(quran_support, dict):
        canonical_source_id = _clean(quran_support.get("canonical_source_id"))
        if canonical_source_id:
            quran_ref = canonical_source_id
            domains.append("quran")

    hadith_support = response_payload.get("hadith_support")
    if isinstance(hadith_support, dict):
        canonical_ref = _clean(hadith_support.get("canonical_ref"))
        source_id = _clean(hadith_support.get("collection_source_id"))
        if canonical_ref:
            hadith_ref = canonical_ref
            if "hadith" not in domains:
                domains.append("hadith")
        if source_id:
            hadith_source_id = source_id

    for item in response_payload.get("tafsir_support") or []:
        if not isinstance(item, dict):
            continue
        source_id = _clean(item.get("source_id"))
        if source_id and source_id not in displayed_tafsir_source_ids:
            displayed_tafsir_source_ids.append(source_id)
    if displayed_tafsir_source_ids and "tafsir" not in domains:
        domains.append("tafsir")

    anchors = response_payload.get("conversation", {}).get("anchors") if isinstance(response_payload.get("conversation"), dict) else []
    for anchor in anchors or []:
        if not isinstance(anchor, dict):
            continue
        canonical_ref = _clean(anchor.get("canonical_ref"))
        if not canonical_ref:
            continue
        if canonical_ref.startswith(_QURAN_PREFIX):
            quran_ref = quran_ref or canonical_ref
            if "quran" not in domains:
                domains.append("quran")
        elif canonical_ref.startswith(_HADITH_PREFIX):
            hadith_ref = hadith_ref or canonical_ref
            if "hadith" not in domains:
                domains.append("hadith")
        elif canonical_ref.startswith(_TAFSIR_PREFIX):
            source_prefix = ':'.join(canonical_ref.split(':', 2)[:2])
            if source_prefix and source_prefix not in displayed_tafsir_source_ids:
                displayed_tafsir_source_ids.append(source_prefix)
            if "tafsir" not in domains:
                domains.append("tafsir")

    comparative_tafsir_source_ids = _dedup(
        displayed_tafsir_source_ids
        + list((previous_scope.comparative_tafsir_source_ids if previous_scope is not None else []) or [])
        + list((previous_scope.tafsir_source_ids if previous_scope is not None else []) or [])
    )
    current_tafsir_source_id = displayed_tafsir_source_ids[0] if len(displayed_tafsir_source_ids) == 1 else None
    quran_span_ref = _derive_quran_span_ref(quran_ref=quran_ref, previous_scope=previous_scope)

    return ActiveScope(
        route_type=route_type,
        answer_mode=answer_mode,
        domains=_dedup(domains),
        quran_ref=quran_ref,
        quran_span_ref=quran_span_ref,
        tafsir_source_ids=displayed_tafsir_source_ids,
        comparative_tafsir_source_ids=comparative_tafsir_source_ids,
        current_tafsir_source_id=current_tafsir_source_id,
        hadith_ref=hadith_ref,
        hadith_source_id=hadith_source_id,
    )


def hydrate_session_state(
    response_payload: dict[str, Any],
    *,
    request_context: dict[str, Any] | None = None,
) -> SessionState:
    request_context = dict(request_context or {})
    conversation = response_payload.get("conversation") if isinstance(response_payload.get("conversation"), dict) else {}
    anchors = ConversationAnchorSet.from_anchor_payload(conversation.get("anchors") or [])
    previous_scope = _previous_scope_from_request_context(request_context)
    scope = _derive_scope(response_payload, previous_scope=previous_scope)

    return SessionState(
        conversation_id=_clean(request_context.get("conversation_id")),
        parent_turn_id=_clean(request_context.get("parent_turn_id")),
        turn_id=_clean(conversation.get("turn_id")),
        route_type=_clean(response_payload.get("route_type")),
        answer_mode=_clean(response_payload.get("answer_mode")),
        terminal_state=_clean(response_payload.get("terminal_state")),
        scope=scope,
        anchors=anchors,
        citations=_collect_citation_refs(response_payload),
        active_source_ids=_collect_active_source_ids(response_payload),
        followup_ready=bool(conversation.get("followup_ready")),
        raw_context=request_context,
    )


def _state_from_anchor_refs(context: dict[str, Any]) -> SessionState:
    anchor_refs = [str(item).strip() for item in list(context.get('anchor_refs') or []) if str(item).strip()]
    domains: list[str] = []
    quran_ref: str | None = None
    quran_span_ref: str | None = None
    hadith_ref: str | None = None
    hadith_source_id: str | None = None
    tafsir_source_ids: list[str] = []

    for ref in anchor_refs:
        if ref.startswith(_QURAN_PREFIX):
            quran_ref = quran_ref or ref
            quran_span_ref = quran_span_ref or ref
            if 'quran' not in domains:
                domains.append('quran')
        elif ref.startswith(_HADITH_PREFIX):
            hadith_ref = hadith_ref or ref
            parts = ref.split(':')
            if len(parts) >= 3:
                hadith_source_id = hadith_source_id or ':'.join(parts[:2])
            if 'hadith' not in domains:
                domains.append('hadith')
        elif ref.startswith(_TAFSIR_PREFIX):
            source_prefix = ':'.join(ref.split(':', 2)[:2])
            if source_prefix and source_prefix not in tafsir_source_ids:
                tafsir_source_ids.append(source_prefix)
            if 'tafsir' not in domains:
                domains.append('tafsir')

    comparative_tafsir_source_ids = list(tafsir_source_ids)
    current_tafsir_source_id = tafsir_source_ids[0] if len(tafsir_source_ids) == 1 else None

    return SessionState(
        conversation_id=_clean(context.get('conversation_id')),
        parent_turn_id=_clean(context.get('parent_turn_id')),
        route_type=None,
        answer_mode=None,
        terminal_state=None,
        scope=ActiveScope(
            domains=domains,
            quran_ref=quran_ref,
            quran_span_ref=quran_span_ref,
            tafsir_source_ids=tafsir_source_ids,
            comparative_tafsir_source_ids=comparative_tafsir_source_ids,
            current_tafsir_source_id=current_tafsir_source_id,
            hadith_ref=hadith_ref,
            hadith_source_id=hadith_source_id,
        ),
        anchors=ConversationAnchorSet(refs=anchor_refs, domains=domains),
        citations=[],
        active_source_ids=[],
        followup_ready=bool(anchor_refs),
        raw_context=context,
    )


def _merge_snapshot_with_context(snapshot: SessionState, context: dict[str, Any]) -> SessionState:
    merged = SessionState.from_payload(snapshot.to_payload(), raw_context=context)
    anchor_refs = [str(item).strip() for item in list(context.get('anchor_refs') or []) if str(item).strip()]
    if anchor_refs:
        merged.anchors = ConversationAnchorSet(refs=anchor_refs, domains=list(merged.anchors.domains or []))
        for ref in anchor_refs:
            prefix = ref.split(':', 1)[0]
            if prefix and prefix not in merged.anchors.domains:
                merged.anchors.domains.append(prefix)
    merged.conversation_id = _clean(context.get('conversation_id')) or merged.conversation_id
    merged.parent_turn_id = _clean(context.get('parent_turn_id')) or merged.parent_turn_id
    merged.followup_ready = bool(context.get('anchor_refs') or merged.followup_ready)
    return merged


def hydrate_session_state_from_request_context(request_context: dict[str, Any] | None) -> SessionState:
    context = dict(request_context or {})
    snapshot = context.get('_hydrated_session_state') if isinstance(context.get('_hydrated_session_state'), dict) else None
    if snapshot:
        return _merge_snapshot_with_context(SessionState.from_payload(snapshot, raw_context=context), context)
    return _state_from_anchor_refs(context)
