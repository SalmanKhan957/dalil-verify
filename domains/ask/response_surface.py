from __future__ import annotations

from typing import Any

# Canonical public answer fields intentionally surfaced at the top level on /ask and
# /ask/explain. These are the contract fields clients should treat as the source of truth.
CANONICAL_TOP_LEVEL_ANSWER_FIELDS: tuple[str, ...] = (
    'answer_mode',
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
    'debug',
)

# These fields are duplicated into the nested legacy `result` envelope strictly for
# compatibility during the later response-contract / deprecation tranche.
DUPLICATED_RESULT_FIELDS: tuple[str, ...] = CANONICAL_TOP_LEVEL_ANSWER_FIELDS + ('error',)

# These fields remain available only inside the legacy nested `result` envelope for
# backward compatibility and are intentionally excluded from the canonical top-level
# Ask and Explain answer surfaces.
LEGACY_RESULT_ONLY_FIELDS: tuple[str, ...] = (
    'quran_span',
    'verifier_result',
    'quote_payload',
    'hadith_entry',
)

RESULT_METADATA_FIELDS: tuple[str, ...] = ('ok', 'query', 'route_type', 'action_type')

LEGACY_RESULT_ALLOWED_FIELDS: tuple[str, ...] = RESULT_METADATA_FIELDS + DUPLICATED_RESULT_FIELDS + LEGACY_RESULT_ONLY_FIELDS

EXPLAIN_SURFACE_FIELDS: tuple[str, ...] = (
    'ok',
    'query',
    'answer_mode',
    'route_type',
    'action_type',
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
    'debug',
    'error',
)


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
            'conversation': 'Canonical surfaced follow-up anchors for compatible clients; currently advisory for runtime follow-up behavior.',
        },
    }


def extract_answer_surface(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}

    payload: dict[str, Any] = {}
    for field in CANONICAL_TOP_LEVEL_ANSWER_FIELDS:
        if field in result:
            payload[field] = result.get(field)

    return payload


def build_legacy_result_payload(result: dict[str, Any] | None) -> dict[str, Any] | None:
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
        'route_type': str(route.get('route_type') or result_dict.get('route_type') or 'unsupported_for_now'),
        'action_type': str(route.get('action_type') or result_dict.get('action_type') or 'unknown'),
        'route': route,
        'result': build_legacy_result_payload(result_dict),
        'error': result_dict.get('error'),
    }
    payload.update(extract_answer_surface(result_dict))
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
    explain_payload.setdefault('route_type', 'unsupported_for_now')
    explain_payload.setdefault('action_type', 'unknown')
    explain_payload.setdefault('citations', [])
    explain_payload.setdefault('tafsir_support', [])
    explain_payload.setdefault('partial_success', False)
    explain_payload.setdefault('warnings', [])
    return explain_payload
