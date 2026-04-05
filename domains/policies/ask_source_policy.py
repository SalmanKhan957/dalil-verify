from __future__ import annotations

from domains.ask.route_types import AskActionType, AskRouteType
from domains.ask.source_policy_types import AskSourcePolicyDecision, QuranSourcePolicyDecision, TafsirSourcePolicyDecision
from domains.policies.source_eligibility import can_mix_sources
from shared.schemas.source_record import SourceRecord

_TAFSIR_ELIGIBLE_ROUTE_TYPES = {AskRouteType.EXPLICIT_QURAN_REFERENCE.value, AskRouteType.ARABIC_QURAN_QUOTE.value}


def build_quran_source_policy(*, requested_text_source_id: str | None, requested_translation_source_id: str | None, selected_text_source_id: str | None, selected_translation_source_id: str | None, text_source_origin: str | None, translation_source_origin: str | None) -> QuranSourcePolicyDecision:
    allowed = bool(selected_text_source_id)
    return QuranSourcePolicyDecision(allowed=allowed, included=allowed, policy_reason='selected' if allowed else 'missing_selected_quran_source', requested_text_source_id=requested_text_source_id, requested_translation_source_id=requested_translation_source_id, selected_text_source_id=selected_text_source_id, selected_translation_source_id=selected_translation_source_id, text_source_origin=text_source_origin, translation_source_origin=translation_source_origin)


def _is_tafsir_route_eligible(*, route_type: str, action_type: str) -> bool:
    if route_type not in _TAFSIR_ELIGIBLE_ROUTE_TYPES:
        return False
    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        return action_type != AskActionType.VERIFY_SOURCE.value
    return True


def evaluate_ask_source_policy(*, route_type: str, action_type: str, include_tafsir: bool | None, tafsir_intent_detected: bool, requested_tafsir_source_id: str | None, quran_source: SourceRecord | None, requested_quran_text_source_id: str | None, requested_quran_translation_source_id: str | None, selected_quran_text_source_id: str | None, selected_quran_translation_source_id: str | None, quran_text_source_origin: str | None, quran_translation_source_origin: str | None, database_url: str | None = None) -> AskSourcePolicyDecision:
    quran_policy = build_quran_source_policy(requested_text_source_id=requested_quran_text_source_id, requested_translation_source_id=requested_quran_translation_source_id, selected_text_source_id=selected_quran_text_source_id, selected_translation_source_id=selected_quran_translation_source_id, text_source_origin=quran_text_source_origin, translation_source_origin=quran_translation_source_origin)
    tafsir_policy = TafsirSourcePolicyDecision()

    if not _is_tafsir_route_eligible(route_type=route_type, action_type=action_type):
        tafsir_policy.policy_reason = 'route_not_eligible_for_tafsir'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)
    if include_tafsir is False:
        tafsir_policy.request_origin = 'explicit_suppression'
        tafsir_policy.policy_reason = 'suppressed_by_request'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)
    if include_tafsir is True:
        tafsir_policy.requested = True
        tafsir_policy.request_origin = 'explicit_flag'
        tafsir_policy.requested_source_id = requested_tafsir_source_id
    elif tafsir_intent_detected:
        tafsir_policy.requested = True
        tafsir_policy.request_origin = 'query_intent'
    else:
        tafsir_policy.policy_reason = 'not_requested'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)

    if quran_source is None:
        tafsir_policy.policy_reason = 'missing_quran_source'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)
    from domains.source_registry.registry import resolve_tafsir_source_for_explain
    selected_tafsir = resolve_tafsir_source_for_explain(requested_tafsir_source_id if tafsir_policy.request_origin == 'explicit_flag' else None, database_url=database_url)
    if selected_tafsir is None:
        tafsir_policy.policy_reason = 'tafsir_source_not_enabled'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)

    tafsir_policy.selected_source_id = selected_tafsir.source_id
    if not can_mix_sources(quran_source, selected_tafsir):
        tafsir_policy.policy_reason = 'quran_tafsir_composition_blocked'
        return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)

    tafsir_policy.allowed = True
    tafsir_policy.included = True
    tafsir_policy.policy_reason = 'selected'
    return AskSourcePolicyDecision(quran=quran_policy, tafsir=tafsir_policy)
