from __future__ import annotations

from typing import Any

from .session_state import ActiveScope, ConversationAnchorSet, SessionState


_QURAN_PREFIX = "quran:"
_HADITH_PREFIX = "hadith:"
_TAFSIR_PREFIX = "tafsir:"


def _collect_citation_refs(response_payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in response_payload.get("citations") or []:
        if not isinstance(item, dict):
            continue
        canonical_ref = str(item.get("canonical_ref") or "").strip()
        if canonical_ref:
            refs.append(canonical_ref)
    return refs


def _collect_active_source_ids(response_payload: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []
    for item in response_payload.get("citations") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def _derive_scope(response_payload: dict[str, Any]) -> ActiveScope:
    answer_mode = str(response_payload.get("answer_mode") or "").strip() or None
    route_type = str(response_payload.get("route_type") or "").strip() or None

    domains: list[str] = []
    quran_ref: str | None = None
    quran_span_ref: str | None = None
    tafsir_source_ids: list[str] = []
    hadith_ref: str | None = None
    hadith_source_id: str | None = None

    quran_support = response_payload.get("quran_support")
    if isinstance(quran_support, dict):
        canonical_source_id = str(quran_support.get("canonical_source_id") or "").strip()
        if canonical_source_id:
            quran_ref = canonical_source_id
            quran_span_ref = canonical_source_id
            domains.append("quran")

    hadith_support = response_payload.get("hadith_support")
    if isinstance(hadith_support, dict):
        canonical_ref = str(hadith_support.get("canonical_ref") or "").strip()
        source_id = str(hadith_support.get("collection_source_id") or "").strip()
        if canonical_ref:
            hadith_ref = canonical_ref
            if "hadith" not in domains:
                domains.append("hadith")
        if source_id:
            hadith_source_id = source_id

    for item in response_payload.get("tafsir_support") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        if source_id and source_id not in tafsir_source_ids:
            tafsir_source_ids.append(source_id)
    if tafsir_source_ids and "tafsir" not in domains:
        domains.append("tafsir")

    anchors = response_payload.get("conversation", {}).get("anchors") if isinstance(response_payload.get("conversation"), dict) else []
    for anchor in anchors or []:
        if not isinstance(anchor, dict):
            continue
        canonical_ref = str(anchor.get("canonical_ref") or "").strip()
        if canonical_ref.startswith(_QURAN_PREFIX) and not quran_ref:
            quran_ref = canonical_ref
            quran_span_ref = canonical_ref
            if "quran" not in domains:
                domains.append("quran")
        elif canonical_ref.startswith(_HADITH_PREFIX) and not hadith_ref:
            hadith_ref = canonical_ref
            if "hadith" not in domains:
                domains.append("hadith")
        elif canonical_ref.startswith(_TAFSIR_PREFIX):
            source_id = str(anchor.get("source_domain") or "tafsir").strip()
            # Keep source ids from tafsir_support as the truth layer; anchors only help hydration.
            if "tafsir" not in domains:
                domains.append("tafsir")

    return ActiveScope(
        route_type=route_type,
        answer_mode=answer_mode,
        domains=domains,
        quran_ref=quran_ref,
        quran_span_ref=quran_span_ref,
        tafsir_source_ids=tafsir_source_ids,
        hadith_ref=hadith_ref,
        hadith_source_id=hadith_source_id,
    )


def hydrate_session_state(
    response_payload: dict[str, Any],
    *,
    request_context: dict[str, Any] | None = None,
) -> SessionState:
    """Hydrate bounded /ask conversation state from the latest response payload.

    This function assumes the response payload is the canonical /ask public surface.
    """

    request_context = dict(request_context or {})
    conversation = response_payload.get("conversation") if isinstance(response_payload.get("conversation"), dict) else {}
    anchors = ConversationAnchorSet.from_anchor_payload(conversation.get("anchors") or [])
    scope = _derive_scope(response_payload)

    return SessionState(
        conversation_id=str(request_context.get("conversation_id") or "").strip() or None,
        parent_turn_id=str(request_context.get("parent_turn_id") or "").strip() or None,
        turn_id=str(conversation.get("turn_id") or "").strip() or None,
        route_type=str(response_payload.get("route_type") or "").strip() or None,
        answer_mode=str(response_payload.get("answer_mode") or "").strip() or None,
        terminal_state=str(response_payload.get("terminal_state") or "").strip() or None,
        scope=scope,
        anchors=anchors,
        citations=_collect_citation_refs(response_payload),
        active_source_ids=_collect_active_source_ids(response_payload),
        followup_ready=bool(conversation.get("followup_ready")),
        raw_context=request_context,
    )
