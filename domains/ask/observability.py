from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Request

from infrastructure.config.settings import settings


def make_request_id(request: Request | None = None) -> str:
    header_value = None
    if request is not None:
        header_value = request.headers.get('x-request-id') or request.headers.get('x-dalil-request-id')
    normalized = str(header_value or '').strip()
    return normalized or f'dalil-{uuid4().hex[:16]}'


class Timer:
    def __init__(self) -> None:
        self._started = perf_counter()

    def elapsed_ms(self) -> float:
        return round((perf_counter() - self._started) * 1000.0, 3)


def _safe_query_normalization(route: dict[str, Any]) -> dict[str, Any] | None:
    normalization = route.get('query_normalization')
    if not isinstance(normalization, dict):
        return None
    allowed = {
        'backend',
        'changed',
        'confidence',
        'normalization_type',
        'did_change_meaning',
        'safe_for_routing',
        'used_hosted_model',
        'attempted_hosted_model',
        'model',
        'hosted_model',
        'hosted_fallback_reason',
        'hosted_error_class',
        'normalized_query',
    }
    return {key: normalization.get(key) for key in allowed if key in normalization}


def attach_observability(
    *,
    payload: dict[str, Any],
    request_id: str,
    request_contract_version: str,
    session_key: str,
    hydrated_request_context: dict[str, Any] | None,
    timings_ms: dict[str, float],
    debug_requested: bool,
) -> dict[str, Any]:
    if not settings.observability_enabled:
        return payload

    orchestration = payload.get('orchestration')
    if not isinstance(orchestration, dict):
        orchestration = {}
        payload['orchestration'] = orchestration

    diagnostics = orchestration.get('diagnostics')
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        orchestration['diagnostics'] = diagnostics

    diagnostics['request_id'] = request_id
    diagnostics['request_contract_version'] = request_contract_version
    diagnostics['surface_contract_version'] = settings.response_surface_contract_version
    diagnostics['timings_ms'] = dict(timings_ms)
    diagnostics['feature_flags'] = {
        'observability_enabled': bool(settings.observability_enabled),
        'legacy_result_envelope_enabled': bool(settings.response_include_legacy_result),
        'query_normalization_backend': settings.query_normalization_backend,
        'renderer_backend': settings.renderer_backend,
        'anchor_store_backend': settings.anchor_store_backend,
        'anchor_store_ttl_seconds': int(settings.anchor_store_ttl_seconds),
        'release_mode': settings.release_mode,
        'startup_validation_strict': bool(settings.startup_validation_strict),
    }
    diagnostics['context'] = {
        'anchor_session_key': session_key,
        'anchor_resolution_mode': str((hydrated_request_context or {}).get('_anchor_resolution_mode') or 'none'),
        'hydrated_anchor_count': len(list((hydrated_request_context or {}).get('anchor_refs') or [])),
    }
    normalization = _safe_query_normalization(payload.get('route') if isinstance(payload.get('route'), dict) else {})
    if normalization is not None:
        diagnostics['query_normalization'] = normalization

    if debug_requested or settings.response_debug_default:
        existing_debug = payload.get('debug') if isinstance(payload.get('debug'), dict) else {}
        payload['debug'] = {
            **existing_debug,
            'request_id': request_id,
            'timings_ms': dict(timings_ms),
            'query_normalization': normalization,
            'feature_flags': diagnostics['feature_flags'],
            'hadith_retrieval': _extract_hadith_retrieval_debug(orchestration),
        }
    return payload


def _extract_hadith_retrieval_debug(orchestration: dict[str, Any]) -> dict[str, Any] | None:
    """Promote the Bukhari retrieval internals into the public debug block.

    When a user sets ``debug: true`` on the /ask request, they want enough
    information to diagnose abstains and mis-routes without SSH access.
    Specifically, the three fields that turned a silent OpenSearch outage
    into an unreproducible mystery on the topical-hadith branch:

        topic_resolution — which leaf the resolver picked and why
        bm25_error       — OpenSearch BM25 lane exception string (empty on success)
        knn_error        — OpenSearch kNN lane exception string
        retrieval_origin — which pipeline ran (BM25-only vs hybrid)
        anchor_gate      — pass/fail counts from the word-boundary gate

    Returns None when no hadith retrieval happened for the request.
    """
    if not isinstance(orchestration, dict):
        return None
    diag = orchestration.get('diagnostics')
    if not isinstance(diag, dict):
        return None
    shadow = diag.get('topical_v2_shadow')
    if not isinstance(shadow, dict):
        return None
    debug_block = shadow.get('debug')
    if not isinstance(debug_block, dict):
        return {'abstain': shadow.get('abstain'), 'warnings': shadow.get('warnings')}
    cg = debug_block.get('candidate_generation') if isinstance(debug_block.get('candidate_generation'), dict) else {}

    result: dict[str, Any] = {
        'abstain': shadow.get('abstain'),
        'abstain_reason': shadow.get('abstain_reason'),
        'warnings': shadow.get('warnings'),
        'selected_refs': shadow.get('selected_refs'),
        'retrieval_path': cg.get('retrieval_path'),
        'retrieval_origin': cg.get('retrieval_origin'),
        'topic_resolution': cg.get('topic_resolution'),
        'strict_bm25_hits': cg.get('strict_bm25_hits'),
        'strict_knn_hits': cg.get('strict_knn_hits'),
        'relaxed_bm25_hits': cg.get('relaxed_bm25_hits'),
        'relaxed_knn_hits': cg.get('relaxed_knn_hits'),
        'rrf_combined_count': cg.get('rrf_combined_count'),
        'anchor_gate': cg.get('anchor_gate'),
        'anchor_gate_applied': cg.get('anchor_gate_applied'),
        'candidate_count': cg.get('candidate_count'),
        'top_refs': cg.get('top_refs'),
        'bm25_error': cg.get('bm25_error'),
        'knn_error': cg.get('knn_error'),
    }
    # Keep only keys with non-None values so the debug block stays compact.
    return {k: v for k, v in result.items() if v is not None}
