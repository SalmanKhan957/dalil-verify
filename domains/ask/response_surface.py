from __future__ import annotations

from typing import Any

# These fields remain available inside the legacy nested `result` envelope for
# backward compatibility, but they are intentionally excluded from the canonical
# top-level Ask and Explain answer surfaces.
LEGACY_RESULT_ONLY_FIELDS: tuple[str, ...] = (
    'quran_span',
    'verifier_result',
    'quote_payload',
)

ANSWER_SURFACE_FIELDS: tuple[str, ...] = (
    'answer_mode',
    'answer_text',
    'citations',
    'quran_support',
    'tafsir_support',
    'resolution',
    'partial_success',
    'warnings',
    'quran_source_selection',
    'source_policy',
    'debug',
)


def extract_answer_surface(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}

    payload: dict[str, Any] = {}
    for field in ANSWER_SURFACE_FIELDS:
        if field in result:
            payload[field] = result.get(field)

    return payload


def build_ask_response_payload(
    *,
    query: str,
    route: dict[str, Any],
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    result_dict = result or {}

    payload: dict[str, Any] = {
        'ok': bool(result_dict.get('ok')),
        'query': query,
        'route_type': str(route.get('route_type') or result_dict.get('route_type') or 'unsupported_for_now'),
        'action_type': str(route.get('action_type') or result_dict.get('action_type') or 'unknown'),
        'route': route,
        'result': result,
        'error': result_dict.get('error'),
    }
    payload.update(extract_answer_surface(result_dict))
    return payload


EXPLAIN_SURFACE_FIELDS: tuple[str, ...] = (
    'ok',
    'query',
    'answer_mode',
    'route_type',
    'action_type',
    'answer_text',
    'citations',
    'quran_support',
    'tafsir_support',
    'resolution',
    'partial_success',
    'warnings',
    'quran_source_selection',
    'source_policy',
    'debug',
    'error',
)


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
