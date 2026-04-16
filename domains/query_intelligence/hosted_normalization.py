from __future__ import annotations

import re

from domains.query_intelligence.models import QueryNormalizationResult
from domains.query_intelligence.normalization import normalize_user_query
from infrastructure.clients.openai_query_normalizer import normalize_with_openai
from infrastructure.config.settings import settings

_LATIN_RE = re.compile(r'[A-Za-z]')
_DIGIT_RE = re.compile(r'\d+')


def _digit_signature(text: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in _DIGIT_RE.finditer(text or ''))


def _deterministic_result(
    raw_query: str,
    normalized_query: str,
    *,
    notes: str = '',
    attempted_hosted_model: bool = False,
    hosted_model: str | None = None,
    hosted_fallback_reason: str | None = None,
    hosted_error_class: str | None = None,
) -> QueryNormalizationResult:
    return QueryNormalizationResult(
        raw_query=raw_query,
        normalized_query=normalized_query,
        backend='deterministic',
        changed=normalized_query != raw_query,
        confidence=1.0,
        normalization_type='identity' if normalized_query == raw_query else 'canonicalization',
        did_change_meaning=False,
        safe_for_routing=True,
        notes=notes,
        model=None,
        used_hosted_model=False,
        attempted_hosted_model=attempted_hosted_model,
        hosted_model=hosted_model,
        hosted_fallback_reason=hosted_fallback_reason,
        hosted_error_class=hosted_error_class,
    )


def _should_attempt_hosted_normalization(raw_query: str) -> bool:
    if str(getattr(settings, 'query_normalization_backend', 'deterministic') or 'deterministic').strip().lower() != 'openai':
        return False
    if not settings.openai_api_key.strip():
        return False
    if not raw_query or len(raw_query) > int(settings.query_normalization_max_input_chars):
        return False
    return _LATIN_RE.search(raw_query) is not None


def normalize_query_for_routing(query: str | None) -> QueryNormalizationResult:
    raw_query = str(query or '')
    deterministic = normalize_user_query(raw_query)
    fallback = _deterministic_result(raw_query, deterministic)

    if not deterministic:
        return fallback
    if not _should_attempt_hosted_normalization(raw_query):
        return fallback

    hosted = normalize_with_openai(raw_query=raw_query, deterministic_baseline=deterministic)
    hosted_model = str(hosted.get('model') or settings.query_normalization_model)
    hosted_ok = bool(hosted.get('ok')) if 'ok' in hosted else bool(hosted.get('normalized_query'))

    if not hosted_ok:
        return _deterministic_result(
            raw_query,
            deterministic,
            notes=str(hosted.get('fallback_reason') or 'hosted_unavailable'),
            attempted_hosted_model=True,
            hosted_model=hosted_model,
            hosted_fallback_reason=str(hosted.get('fallback_reason') or 'hosted_unavailable'),
            hosted_error_class=str(hosted.get('error_class') or 'unknown_hosted_error'),
        )

    candidate = normalize_user_query(str(hosted.get('normalized_query') or ''))
    if not candidate:
        return _deterministic_result(
            raw_query,
            deterministic,
            notes='hosted_empty_candidate',
            attempted_hosted_model=True,
            hosted_model=hosted_model,
            hosted_fallback_reason='hosted_empty_candidate',
            hosted_error_class='empty_normalized_query',
        )

    if bool(hosted.get('did_change_meaning')):
        return _deterministic_result(
            raw_query,
            deterministic,
            notes='hosted_flagged_meaning_change',
            attempted_hosted_model=True,
            hosted_model=hosted_model,
            hosted_fallback_reason='hosted_flagged_meaning_change',
            hosted_error_class='meaning_change_flagged',
        )

    if float(hosted.get('confidence') or 0.0) < float(settings.query_normalization_min_confidence):
        return _deterministic_result(
            raw_query,
            deterministic,
            notes='hosted_low_confidence',
            attempted_hosted_model=True,
            hosted_model=hosted_model,
            hosted_fallback_reason='hosted_low_confidence',
            hosted_error_class='low_confidence',
        )

    if _digit_signature(raw_query) != _digit_signature(candidate):
        return _deterministic_result(
            raw_query,
            deterministic,
            notes='hosted_digit_signature_mismatch',
            attempted_hosted_model=True,
            hosted_model=hosted_model,
            hosted_fallback_reason='hosted_digit_signature_mismatch',
            hosted_error_class='digit_signature_mismatch',
        )

    return QueryNormalizationResult(
        raw_query=raw_query,
        normalized_query=candidate,
        backend='openai',
        changed=candidate != raw_query,
        confidence=float(hosted.get('confidence') or 0.0),
        normalization_type=str(hosted.get('normalization_type') or 'mixed'),
        did_change_meaning=False,
        safe_for_routing=True,
        notes=str(hosted.get('notes') or '').strip(),
        model=hosted_model,
        used_hosted_model=True,
        attempted_hosted_model=True,
        hosted_model=hosted_model,
    )
