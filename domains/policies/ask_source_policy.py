from __future__ import annotations

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
    list_enabled_capabilities,
    source_supports_capability,
)
from domains.source_registry.policies import can_mix_sources
from domains.source_registry.registry import resolve_hadith_collection_source, resolve_tafsir_source_for_explain
from shared.schemas.source_record import SourceRecord

_TAFSIR_ELIGIBLE_ROUTE_TYPES = {AskRouteType.EXPLICIT_QURAN_REFERENCE.value, AskRouteType.ARABIC_QURAN_QUOTE.value}


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


def _is_tafsir_route_eligible(*, route_type: str, action_type: str) -> bool:
    if route_type not in _TAFSIR_ELIGIBLE_ROUTE_TYPES:
        return False
    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        return action_type != AskActionType.VERIFY_SOURCE.value
    return True


def _evaluate_hadith_source_policy(*, requested_hadith_source_id: str | None, action_type: str, hadith_mode: str, database_url: str | None = None) -> HadithSourcePolicyDecision:
    selected_capability = SourceCapability.EXPLAIN_FROM_SOURCE.value if action_type == AskActionType.EXPLAIN.value else SourceCapability.EXPLICIT_LOOKUP.value
    policy = HadithSourcePolicyDecision(
        requested=True,
        request_origin='query_citation',
        requested_source_id=requested_hadith_source_id or 'hadith:sahih-al-bukhari-en',
        request_mode=hadith_mode,
        mode_enforced=True,
        selected_capability=selected_capability,
    )
    source = resolve_hadith_collection_source(requested_hadith_source_id, database_url=database_url, require_answer_approval=False)
    if source is None:
        policy.policy_reason = 'hadith_collection_not_registered_or_disabled'
        return policy
    policy.selected_source_id = source.source_id
    policy.available_capabilities = list_enabled_capabilities(source)
    policy.approved_for_answering = bool(source.approved_for_answering)
    policy.answer_capability = describe_hadith_answer_capability(source)
    if not source_supports_capability(source, selected_capability):
        policy.policy_reason = 'requested_hadith_capability_not_allowed'
        return policy
    policy.allowed = True
    policy.included = True
    if selected_capability == SourceCapability.EXPLAIN_FROM_SOURCE.value:
        policy.policy_reason = 'explicit_hadith_explain_selected'
    else:
        policy.policy_reason = 'explicit_citation_lookup_selected'
    return policy


def evaluate_ask_source_policy(*, route_type: str, action_type: str, include_tafsir: bool | None, tafsir_intent_detected: bool, requested_tafsir_source_id: str | None, quran_source: SourceRecord | None, requested_quran_text_source_id: str | None, requested_quran_translation_source_id: str | None, selected_quran_text_source_id: str | None, selected_quran_translation_source_id: str | None, quran_text_source_origin: str | None, quran_translation_source_origin: str | None, requested_hadith_source_id: str | None = None, hadith_mode: str = 'auto', database_url: str | None = None) -> AskSourcePolicyDecision:
    quran_capabilities = list_enabled_capabilities(quran_source)
    quran_selected_capability = _quran_selected_capability(route_type=route_type, action_type=action_type)

    if route_type == AskRouteType.EXPLICIT_HADITH_REFERENCE.value:
        quran_policy = build_quran_source_policy(
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
            available_capabilities=quran_capabilities,
        )
        tafsir_policy = TafsirSourcePolicyDecision(
            policy_reason='not_requested_for_route',
            selected_capability=None,
            available_capabilities=[],
        )
        hadith_policy = _evaluate_hadith_source_policy(
            requested_hadith_source_id=requested_hadith_source_id,
            action_type=action_type,
            hadith_mode=hadith_mode,
            database_url=database_url,
        )
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
    hadith_policy = HadithSourcePolicyDecision(policy_reason='not_requested_for_route', available_capabilities=[], request_mode=hadith_mode, mode_enforced=bool(hadith_mode))

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
        tafsir_policy.requested_source_id = requested_tafsir_source_id
    elif tafsir_intent_detected:
        tafsir_policy.requested = True
        tafsir_policy.request_origin = 'query_intent'
        tafsir_policy.requested_source_id = requested_tafsir_source_id
    else:
        tafsir_policy.policy_reason = 'not_requested'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    resolved_tafsir_source = resolve_tafsir_source_for_explain(tafsir_policy.requested_source_id, database_url=database_url)
    if resolved_tafsir_source is None:
        tafsir_policy.allowed = False
        tafsir_policy.included = False
        tafsir_policy.policy_reason = 'tafsir_source_not_enabled'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    tafsir_policy.available_capabilities = list_enabled_capabilities(resolved_tafsir_source)
    if not source_supports_capability(resolved_tafsir_source, SourceCapability.EXPLAIN_FROM_SOURCE.value):
        tafsir_policy.allowed = False
        tafsir_policy.included = False
        tafsir_policy.selected_source_id = resolved_tafsir_source.source_id
        tafsir_policy.policy_reason = 'requested_tafsir_capability_not_allowed'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    if quran_source is None or not can_mix_sources(quran_source, resolved_tafsir_source):
        tafsir_policy.allowed = False
        tafsir_policy.included = False
        tafsir_policy.selected_source_id = resolved_tafsir_source.source_id
        tafsir_policy.policy_reason = 'quran_tafsir_composition_blocked'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)

    tafsir_policy.selected_source_id = resolved_tafsir_source.source_id
    tafsir_policy.allowed = True
    tafsir_policy.included = True
    tafsir_policy.policy_reason = 'selected'
    return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy, hadith=hadith_policy)
