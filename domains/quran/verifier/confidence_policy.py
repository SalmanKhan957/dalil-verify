from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def apply_verifier_confidence_policy(
    response: dict[str, Any],
    *,
    debug_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Conservative post-build confidence hardening for public verifier responses.

    Purpose:
    - prevent fragile exact/high claims from slipping through on weak evidence
    - keep giant exact-path claims strict and reproducible
    - expose a compact policy audit block for debug / release gating
    """
    response = dict(response or {})
    best_match = dict(response.get('best_match') or {})
    if not best_match:
        policy = {
            'version': 'v1',
            'applied': True,
            'action': 'no_best_match',
            'reasons': ['no_best_match'],
        }
        return response, policy

    scoring = best_match.get('scoring_breakdown') or {}
    coverage = _to_float(scoring.get('token_coverage') or best_match.get('token_coverage'))
    score = _to_float(best_match.get('score'))
    window_size = _to_int(best_match.get('window_size'))
    retrieval_engine = best_match.get('retrieval_engine') or ((debug_payload or {}).get('analytics') or {}).get('passage_retrieval_engine')
    preferred_lane = response.get('preferred_lane') or 'none'
    status = response.get('match_status') or 'Cannot assess'
    confidence = response.get('confidence') or 'low'

    reasons: list[str] = []
    action = 'kept'

    if preferred_lane == 'passage' and retrieval_engine == 'giant_exact_anchor' and status == 'Exact match found':
        if window_size < 5:
            response['match_status'] = 'Close / partial match found'
            response['confidence'] = 'medium'
            reasons.append('giant_exact_window_below_minimum')
            action = 'demoted'
        elif coverage < 99.5:
            response['match_status'] = 'Close / partial match found'
            response['confidence'] = 'medium'
            reasons.append('giant_exact_token_coverage_below_strict_threshold')
            action = 'demoted'
        elif score < 90.0:
            response['match_status'] = 'Close / partial match found'
            response['confidence'] = 'medium'
            reasons.append('giant_exact_score_below_strict_threshold')
            action = 'demoted'
        else:
            reasons.append('giant_exact_strict_verified')

    if preferred_lane == 'passage' and retrieval_engine == 'surah_span_exact' and status == 'Exact match found' and action == 'kept':
        if window_size < 5 or coverage < 98.0 or score < 85.0:
            response['confidence'] = 'medium'
            reasons.append('surah_span_exact_evidence_softened')
            action = 'confidence_softened'
        else:
            reasons.append('surah_span_exact_verified')

    if preferred_lane == 'ayah' and status == 'Exact match found' and action == 'kept':
        if score < 85.0:
            response['confidence'] = 'medium'
            reasons.append('ayah_exact_score_softened')
            action = 'confidence_softened'
        else:
            reasons.append('ayah_exact_verified')

    if confidence == 'high' and response.get('confidence') == 'high' and status != 'Exact match found':
        response['confidence'] = 'medium'
        reasons.append('non_exact_high_confidence_softened')
        action = 'confidence_softened'

    policy = {
        'version': 'v1',
        'applied': True,
        'action': action,
        'reasons': reasons or ['no_change'],
        'preferred_lane': preferred_lane,
        'retrieval_engine': retrieval_engine,
        'score': score,
        'token_coverage': coverage,
        'window_size': window_size,
    }
    return response, policy
