from __future__ import annotations

from infrastructure.config.settings import settings
from domains.ask.route_types import AskActionType, AskRouteType
from domains.ask.source_policy_types import (
    AskSourcePolicyDecision,
    HadithSourcePolicyDecision,
    QuranSourcePolicyDecision,
    TafsirSourcePolicyDecision,
)
from domains.source_registry.capabilities import (
    SourceCapability,
    describe_hadith_answer_capability,
    describe_hadith_public_response_scope,
    list_enabled_capabilities,
    source_supports_capability,
)
from domains.source_registry.policies import can_mix_sources
from domains.source_registry.registry import get_source_record, resolve_hadith_collection_source, resolve_tafsir_source_for_explain
from shared.schemas.source_record import SourceRecord

_TAFSIR_ELIGIBLE_ROUTE_TYPES = {
    AskRouteType.EXPLICIT_QURAN_REFERENCE.value,
    AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value,
    AskRouteType.ARABIC_QURAN_QUOTE.value,
}


def _normalize_requested_tafsir_source_ids(*, requested_tafsir_source_id: str | None, requested_tafsir_source_ids: list[str] | None) -> list[str]:
    values = list(requested_tafsir_source_ids or [])
    if requested_tafsir_source_id:
        values = [requested_tafsir_source_id, *values]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or '').strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _resolve_requested_tafsir_sources(*, requested_source_ids: list[str], database_url: str | None) -> list[SourceRecord] | None:
    if not requested_source_ids:
        requested_source_ids = [
            'tafsir:ibn-kathir-en',
            'tafsir:maarif-al-quran-en',
            'tafsir:tafheem-al-quran-en',
        ]

    resolved: list[SourceRecord] = []
    seen: set[str] = set()
    for source_id in requested_source_ids:
        source = resolve_tafsir_source_for_explain(source_id, database_url=database_url)
        if source is None:
            return None
        if source.source_id in seen:
            continue
        seen.add(source.source_id)
        resolved.append(source)
    return resolved


def _quran_selected_capability(*, route_type: str, action_type: str) -> str:
    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        if action_type == AskActionType.VERIFY_SOURCE.value:
            return SourceCapability.QUOTE_VERIFICATION.value
        return SourceCapability.EXPLAIN_FROM_SOURCE.value
    if action_type == AskActionType.FETCH_TEXT.value:
        return SourceCapability.EXPLICIT_LOOKUP.value
    return SourceCapability.EXPLAIN_FROM_SOURCE.value


def build_quran_source_policy(*, requested_text_source_id: str | None, requested_translation_source_id: str | None, selected_text_source_id: str | None, selected_translation_source_id: str | None, text_source_origin: str | None, translation_source_origin: str | None, allowed: bool = True, included: bool = True, policy_reason: str | None = 'selected', selected_capability: str | None = None, available_capabilities: list[str] | None = None) -> QuranSourcePolicyDecision:
    return QuranSourcePolicyDecision(
        allowed=allowed,
        included=included,
        policy_reason=policy_reason,
        selected_capability=selected_capability,
        available_capabilities=list(available_capabilities or []),
        requested_text_source_id=requested_text_source_id,
        requested_translation_source_id=requested_translation_source_id,
        selected_text_source_id=selected_text_source_id,
        selected_translation_source_id=selected_translation_source_id,
        text_source_origin=text_source_origin,
        translation_source_origin=translation_source_origin,
    )


def build_not_requested_quran_policy(*, requested_quran_text_source_id: str | None = None, requested_quran_translation_source_id: str | None = None, quran_text_source_origin: str | None = None, quran_translation_source_origin: str | None = None, quran_source: SourceRecord | None = None) -> QuranSourcePolicyDecision:
    return build_quran_source_policy(
        requested_text_source_id=requested_quran_text_source_id,
        requested_translation_source_id=requested_quran_translation_source_id,
        selected_text_source_id=None,
        selected_translation_source_id=None,
        text_source_origin=quran_text_source_origin,
        translation_source_origin=quran_translation_source_origin,
        allowed=False,
        included=False,
        policy_reason='not_requested_for_route',
        selected_capability=None,
        available_capabilities=list_enabled_capabilities(quran_source),
    )


def _is_tafsir_route_eligible(*, route_type: str, action_type: str) -> bool:
    if route_type not in _TAFSIR_ELIGIBLE_ROUTE_TYPES:
        return False
    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        return action_type != AskActionType.VERIFY_SOURCE.value
    return True


def _evaluate_hadith_source_policy(*, requested_hadith_source_id: str | None, requested_hadith_mode: str = 'auto', action_type: str, database_url: str | None = None) -> HadithSourcePolicyDecision:
    selected_capability = SourceCapability.EXPLAIN_FROM_SOURCE.value if action_type == AskActionType.EXPLAIN.value else SourceCapability.EXPLICIT_LOOKUP.value
    policy = HadithSourcePolicyDecision(
        requested=True,
        request_origin='query_citation',
        requested_source_id=requested_hadith_source_id or 'hadith:sahih-al-bukhari-en',
        selected_capability=selected_capability,
        request_mode=requested_hadith_mode or 'auto',
        mode_enforced=True,
    )
    requested_mode = (requested_hadith_mode or 'auto').strip()
    if requested_mode not in {'auto', 'explicit_lookup_only'}:
        policy.policy_reason = 'unsupported_hadith_mode'
        return policy
    source = resolve_hadith_collection_source(requested_hadith_source_id, database_url=database_url, require_answer_approval=False)
    if source is None:
        policy.policy_reason = 'hadith_collection_not_registered_or_disabled'
        return policy
    policy.selected_source_id = source.source_id
    policy.available_capabilities = list_enabled_capabilities(source)
    policy.approved_for_answering = bool(source.approved_for_answering)
    policy.answer_capability = describe_hadith_answer_capability(source)
    policy.public_response_scope = describe_hadith_public_response_scope(source)
    if not source_supports_capability(source, selected_capability):
        policy.policy_reason = 'requested_hadith_capability_not_allowed'
        return policy
    policy.allowed = True
    policy.included = True
    policy.policy_reason = 'explicit_hadith_explain_selected' if selected_capability == SourceCapability.EXPLAIN_FROM_SOURCE.value else 'explicit_citation_lookup_selected'
    return policy


def evaluate_topical_tafsir_source_policy(*, requested_tafsir_source_id: str | None, database_url: str | None = None) -> TafsirSourcePolicyDecision:
    policy = TafsirSourcePolicyDecision(
        requested=True,
        request_origin='topic_query',
        requested_source_id=requested_tafsir_source_id,
        selected_capability=SourceCapability.TOPICAL_RETRIEVAL.value,
    )
    resolved_tafsir_source = resolve_tafsir_source_for_explain(requested_tafsir_source_id, database_url=database_url)
    if resolved_tafsir_source is None:
        policy.policy_reason = 'tafsir_source_not_enabled'
        return policy
    policy.selected_source_id = resolved_tafsir_source.source_id
    policy.available_capabilities = list_enabled_capabilities(resolved_tafsir_source)
    if not source_supports_capability(resolved_tafsir_source, SourceCapability.TOPICAL_RETRIEVAL.value):
        policy.policy_reason = 'requested_tafsir_capability_not_allowed'
        return policy
    policy.allowed = True
    policy.included = True
    policy.policy_reason = 'topical_tafsir_selected'
    return policy


def evaluate_topical_hadith_source_policy(*, requested_hadith_source_id: str | None, requested_hadith_mode: str = 'auto', database_url: str | None = None) -> HadithSourcePolicyDecision:
    policy = HadithSourcePolicyDecision(
        requested=True,
        request_origin='topic_query',
        requested_source_id=requested_hadith_source_id or 'hadith:sahih-al-bukhari-en',
        selected_capability=SourceCapability.TOPICAL_RETRIEVAL.value,
        request_mode=requested_hadith_mode or 'auto',
        mode_enforced=True,
    )
    requested_mode = (requested_hadith_mode or 'auto').strip()
    if requested_mode not in {'auto', 'explicit_lookup_only'}:
        policy.policy_reason = 'unsupported_hadith_mode'
        return policy
    if requested_mode == 'explicit_lookup_only':
        policy.policy_reason = 'hadith_mode_blocks_topical_retrieval'
        return policy
    source = resolve_hadith_collection_source(requested_hadith_source_id, database_url=database_url, require_answer_approval=False)
    if source is None:
        policy.policy_reason = 'hadith_collection_not_registered_or_disabled'
        return policy
    policy.selected_source_id = source.source_id
    policy.available_capabilities = list_enabled_capabilities(source)
    policy.approved_for_answering = bool(source.approved_for_answering)
    policy.answer_capability = 'topical_retrieval_bounded' if source_supports_capability(source, SourceCapability.TOPICAL_RETRIEVAL.value) else describe_hadith_answer_capability(source)
    policy.public_response_scope = describe_hadith_public_response_scope(source)
    if not source_supports_capability(source, SourceCapability.TOPICAL_RETRIEVAL.value):
        policy.policy_reason = 'requested_hadith_capability_not_allowed'
        return policy
    if not bool(getattr(settings, 'public_topical_hadith_enabled', False)):
        policy.policy_reason = 'topical_hadith_temporarily_disabled'
        return policy
    policy.allowed = True
    policy.included = True
    policy.policy_reason = 'topical_hadith_selected'
    return policy


def evaluate_ask_source_policy(*, route_type: str, action_type: str, include_tafsir: bool | None, tafsir_intent_detected: bool, requested_tafsir_source_id: str | None, requested_tafsir_source_ids: list[str] | None = None, quran_source: SourceRecord | None, requested_quran_text_source_id: str | None, requested_quran_translation_source_id: str | None, selected_quran_text_source_id: str | None, selected_quran_translation_source_id: str | None, quran_text_source_origin: str | None, quran_translation_source_origin: str | None, requested_hadith_source_id: str | None = None, requested_hadith_mode: str = 'auto', database_url: str | None = None) -> AskSourcePolicyDecision:
    quran_capabilities = list_enabled_capabilities(quran_source)
    quran_selected_capability = _quran_selected_capability(route_type=route_type, action_type=action_type)

    if route_type == AskRouteType.EXPLICIT_HADITH_REFERENCE.value:
        quran_policy = build_not_requested_quran_policy(
            requested_quran_text_source_id=requested_quran_text_source_id,
            requested_quran_translation_source_id=requested_quran_translation_source_id,
            quran_text_source_origin=quran_text_source_origin,
            quran_translation_source_origin=quran_translation_source_origin,
            quran_source=quran_source,
        )
        tafsir_policy = TafsirSourcePolicyDecision(policy_reason='not_requested_for_route', selected_capability=None, available_capabilities=[])
        hadith_policy = _evaluate_hadith_source_policy(requested_hadith_source_id=requested_hadith_source_id, requested_hadith_mode=requested_hadith_mode, action_type=action_type, database_url=database_url)
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    quran_policy = build_quran_source_policy(
        requested_text_source_id=requested_quran_text_source_id,
        requested_translation_source_id=requested_quran_translation_source_id,
        selected_text_source_id=selected_quran_text_source_id,
        selected_translation_source_id=selected_quran_translation_source_id,
        text_source_origin=quran_text_source_origin,
        translation_source_origin=quran_translation_source_origin,
        selected_capability=quran_selected_capability,
        available_capabilities=quran_capabilities,
    )
    tafsir_policy = TafsirSourcePolicyDecision(selected_capability=SourceCapability.EXPLAIN_FROM_SOURCE.value, available_capabilities=[])
    hadith_policy = HadithSourcePolicyDecision(policy_reason='not_requested_for_route', available_capabilities=[])
    requested_tafsir_ids = _normalize_requested_tafsir_source_ids(
        requested_tafsir_source_id=requested_tafsir_source_id,
        requested_tafsir_source_ids=requested_tafsir_source_ids,
    )

    if not _is_tafsir_route_eligible(route_type=route_type, action_type=action_type):
        tafsir_policy.policy_reason = 'route_not_eligible_for_tafsir'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)
    if include_tafsir is False:
        tafsir_policy.request_origin = 'explicit_suppression'
        tafsir_policy.policy_reason = 'suppressed_by_request'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)
    if include_tafsir is True:
        tafsir_policy.requested = True
        tafsir_policy.request_origin = 'explicit_flag'
        tafsir_policy.requested_source_ids = list(requested_tafsir_ids)
        tafsir_policy.requested_source_id = requested_tafsir_ids[0] if requested_tafsir_ids else requested_tafsir_source_id
    elif tafsir_intent_detected:
        tafsir_policy.requested = True
        tafsir_policy.request_origin = 'query_intent'
        tafsir_policy.requested_source_ids = list(requested_tafsir_ids)
        tafsir_policy.requested_source_id = requested_tafsir_ids[0] if requested_tafsir_ids else requested_tafsir_source_id
    else:
        tafsir_policy.policy_reason = 'not_requested'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    resolved_tafsir_sources = _resolve_requested_tafsir_sources(
        requested_source_ids=tafsir_policy.requested_source_ids,
        database_url=database_url,
    )
    if resolved_tafsir_sources is None:
        tafsir_policy.allowed = False
        tafsir_policy.included = False
        tafsir_policy.policy_reason = 'tafsir_source_not_enabled'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    tafsir_policy.available_capabilities = sorted({cap for source in resolved_tafsir_sources for cap in list_enabled_capabilities(source)})
    for resolved_tafsir_source in resolved_tafsir_sources:
        if not source_supports_capability(resolved_tafsir_source, SourceCapability.EXPLAIN_FROM_SOURCE.value):
            tafsir_policy.allowed = False
            tafsir_policy.included = False
            tafsir_policy.selected_source_id = resolved_tafsir_source.source_id
            tafsir_policy.selected_source_ids = [source.source_id for source in resolved_tafsir_sources]
            tafsir_policy.policy_reason = 'requested_tafsir_capability_not_allowed'
            return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)
        if quran_source is None or not can_mix_sources(quran_source, resolved_tafsir_source):
            tafsir_policy.allowed = False
            tafsir_policy.included = False
            tafsir_policy.selected_source_id = resolved_tafsir_source.source_id
            tafsir_policy.selected_source_ids = [source.source_id for source in resolved_tafsir_sources]
            tafsir_policy.policy_reason = 'quran_tafsir_composition_blocked'
            return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    tafsir_policy.selected_source_ids = [source.source_id for source in resolved_tafsir_sources]
    tafsir_policy.selected_source_id = tafsir_policy.selected_source_ids[0] if tafsir_policy.selected_source_ids else None
    tafsir_policy.allowed = True
    tafsir_policy.included = True
    tafsir_policy.policy_reason = 'selected_multiple' if len(tafsir_policy.selected_source_ids) > 1 else 'selected'
    return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)
