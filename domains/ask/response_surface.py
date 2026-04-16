from __future__ import annotations

from typing import Any

from infrastructure.config.settings import settings

CANONICAL_TOP_LEVEL_ANSWER_FIELDS: tuple[str, ...] = (
    'answer_mode',
    'terminal_state',
    'answer_text',
    'citations',
    'quran_support',
    'hadith_support',
    'tafsir_support',
    'resolution',
    'partial_success',
    'warnings',
    'quran_source_selection',
    'source_policy',
    'orchestration',
    'conversation',
    'composition',
    'debug',
)
DUPLICATED_RESULT_FIELDS: tuple[str, ...] = CANONICAL_TOP_LEVEL_ANSWER_FIELDS + ('error',)
LEGACY_RESULT_ONLY_FIELDS: tuple[str, ...] = ('quran_span', 'verifier_result', 'quote_payload', 'hadith_entry')
RESULT_METADATA_FIELDS: tuple[str, ...] = ('ok', 'query', 'route_type', 'action_type')
LEGACY_RESULT_ALLOWED_FIELDS: tuple[str, ...] = RESULT_METADATA_FIELDS + DUPLICATED_RESULT_FIELDS + LEGACY_RESULT_ONLY_FIELDS
EXPLAIN_SURFACE_FIELDS: tuple[str, ...] = (
    'ok', 'query', 'answer_mode', 'terminal_state', 'route_type', 'action_type', 'answer_text', 'citations',
    'quran_support', 'hadith_support', 'tafsir_support', 'resolution', 'partial_success', 'warnings',
    'quran_source_selection', 'source_policy', 'orchestration', 'conversation', 'composition', 'debug', 'error',
)
DEFAULT_CANONICAL_VALUES: dict[str, Any] = {
    'answer_mode': None,
    'terminal_state': None,
    'answer_text': None,
    'citations': [],
    'quran_support': None,
    'hadith_support': None,
    'tafsir_support': [],
    'resolution': None,
    'partial_success': False,
    'warnings': [],
    'quran_source_selection': None,
    'source_policy': None,
    'orchestration': None,
    'conversation': None,
    'composition': None,
    'debug': None,
}


def describe_response_surfaces() -> dict[str, Any]:
    return {
        'canonical_top_level_fields': list(CANONICAL_TOP_LEVEL_ANSWER_FIELDS),
        'legacy_result_allowed_fields': list(LEGACY_RESULT_ALLOWED_FIELDS),
        'duplicated_result_fields': list(DUPLICATED_RESULT_FIELDS),
        'legacy_result_only_fields': list(LEGACY_RESULT_ONLY_FIELDS),
        'notes': {
            'top_level_answer': 'Canonical public answer surface for /ask and /ask/explain.',
            'result': 'Legacy compatibility envelope retained temporarily; not the canonical truth layer.',
            'source_policy': 'Canonical source-selection / capability truth layer.',
            'quran_source_selection': 'Legacy compatibility object; source_policy.quran is the truth layer for source-origin semantics.',
            'orchestration': 'Canonical introspection contract for planner/evidence/debugging.',
            'conversation': 'Canonical surfaced follow-up anchors for compatible clients. Narrow anchored follow-up is active when anchors are supplied or hydrated from the current conversation/session.',
            'composition': 'Canonical LLM-facing composition packet for bounded source-grounded answer rendering.',
            'surface_contract_version': settings.response_surface_contract_version,
            'legacy_result_enabled': settings.response_include_legacy_result,
        },
    }


def _infer_terminal_state(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return 'abstain'
    terminal_state = payload.get('terminal_state')
    if isinstance(terminal_state, str) and terminal_state.strip():
        return terminal_state.strip()
    answer_mode = str(payload.get('answer_mode') or '').strip()
    error = payload.get('error')
    if answer_mode == 'clarify':
        return 'clarify'
    if answer_mode == 'abstain' or error is not None or payload.get('ok') is False:
        return 'abstain'
    return 'answered'


def extract_answer_surface(result: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(DEFAULT_CANONICAL_VALUES)
    if isinstance(result, dict):
        for field in CANONICAL_TOP_LEVEL_ANSWER_FIELDS:
            if field in result:
                payload[field] = result.get(field)
    return payload


def build_legacy_result_payload(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not settings.response_include_legacy_result:
        return None
    if not isinstance(result, dict):
        return None
    legacy_payload: dict[str, Any] = {}
    for field in LEGACY_RESULT_ALLOWED_FIELDS:
        if field in result:
            legacy_payload[field] = result.get(field)
    return legacy_payload


def build_ask_response_payload(*, query: str, route: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
    result_dict = result or {}
    payload: dict[str, Any] = {
        'ok': bool(result_dict.get('ok')),
        'query': query,
        'route_type': str(route.get('route_type') or result_dict.get('route_type') or 'policy_restricted_request'),
        'action_type': str(route.get('action_type') or result_dict.get('action_type') or 'unknown'),
        'route': route,
        'result': build_legacy_result_payload(result_dict),
        'error': result_dict.get('error'),
    }
    payload.update(extract_answer_surface(result_dict))
    payload['terminal_state'] = _infer_terminal_state(payload)
    return payload


def build_explain_response_payload_from_ask_payload(ask_payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = ask_payload or {}
    explain_payload: dict[str, Any] = {}
    for field in EXPLAIN_SURFACE_FIELDS:
        if field in payload:
            explain_payload[field] = payload.get(field)
    explain_payload.setdefault('ok', False)
    explain_payload.setdefault('query', payload.get('query') if isinstance(payload, dict) else None)
    explain_payload.setdefault('answer_mode', None)
    explain_payload.setdefault('terminal_state', _infer_terminal_state(payload if isinstance(payload, dict) else None))
    explain_payload.setdefault('route_type', 'policy_restricted_request')
    explain_payload.setdefault('action_type', 'unknown')
    explain_payload.setdefault('citations', [])
    explain_payload.setdefault('tafsir_support', [])
    explain_payload.setdefault('partial_success', False)
    explain_payload.setdefault('warnings', [])
    return explain_payload
