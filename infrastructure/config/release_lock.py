from __future__ import annotations

import copy
import importlib.util
from typing import Any

from infrastructure.config.settings import Settings, settings

_ALLOWED_RELEASE_MODES = {'development', 'staging', 'production'}
_ALLOWED_RENDERER_BACKENDS = {'deterministic', 'openai'}
_ALLOWED_QUERY_NORMALIZATION_BACKENDS = {'deterministic', 'openai'}
_ALLOWED_ANCHOR_STORE_BACKENDS = {'memory', 'sqlite', 'redis'}

STARTUP_VALIDATION_INFO: dict[str, Any] = {
    'checked': False,
    'release_mode': None,
    'strict': False,
    'error_count': 0,
    'warning_count': 0,
    'issues': [],
}


def _issue(*, severity: str, code: str, message: str) -> dict[str, str]:
    return {'severity': severity, 'code': code, 'message': message}


def _clean(value: object) -> str:
    return str(value or '').strip().lower()


def build_release_posture(config: Settings = settings) -> dict[str, Any]:
    return {
        'release_mode': _clean(getattr(config, 'release_mode', 'development')) or 'development',
        'startup_validation_strict': bool(getattr(config, 'startup_validation_strict', False)),
        'observability_enabled': bool(getattr(config, 'observability_enabled', False)),
        'response_include_legacy_result': bool(getattr(config, 'response_include_legacy_result', False)),
        'response_debug_default': bool(getattr(config, 'response_debug_default', False)),
        'response_surface_contract_version': str(getattr(config, 'response_surface_contract_version', '') or ''),
        'query_normalization_backend': _clean(getattr(config, 'query_normalization_backend', 'deterministic')) or 'deterministic',
        'renderer_backend': _clean(getattr(config, 'renderer_backend', 'deterministic')) or 'deterministic',
        'anchor_store_backend': _clean(getattr(config, 'anchor_store_backend', 'memory')) or 'memory',
        'public_topical_tafsir_enabled': bool(getattr(config, 'public_topical_tafsir_enabled', False)),
        'public_topical_hadith_enabled': bool(getattr(config, 'public_topical_hadith_enabled', False)),
        'openai_api_key_present': bool(str(getattr(config, 'openai_api_key', '') or '').strip()),
    }


def collect_startup_validation_issues(config: Settings = settings) -> list[dict[str, str]]:
    posture = build_release_posture(config)
    issues: list[dict[str, str]] = []
    release_mode = posture['release_mode']

    if release_mode not in _ALLOWED_RELEASE_MODES:
        issues.append(_issue(severity='error', code='invalid_release_mode', message=f"Unsupported DALIL_RELEASE_MODE '{release_mode}'."))

    if posture['renderer_backend'] not in _ALLOWED_RENDERER_BACKENDS:
        issues.append(_issue(severity='error', code='invalid_renderer_backend', message=f"Unsupported DALIL_RENDERER_BACKEND '{posture['renderer_backend']}'."))
    if posture['query_normalization_backend'] not in _ALLOWED_QUERY_NORMALIZATION_BACKENDS:
        issues.append(_issue(severity='error', code='invalid_query_normalization_backend', message=f"Unsupported DALIL_QUERY_NORMALIZATION_BACKEND '{posture['query_normalization_backend']}'."))
    if posture['anchor_store_backend'] not in _ALLOWED_ANCHOR_STORE_BACKENDS:
        issues.append(_issue(severity='error', code='invalid_anchor_store_backend', message=f"Unsupported DALIL_ANCHOR_STORE_BACKEND '{posture['anchor_store_backend']}'."))

    if posture['query_normalization_backend'] == 'openai' and not posture['openai_api_key_present']:
        issues.append(_issue(severity='error', code='missing_openai_api_key_for_query_normalization', message='OPENAI_API_KEY is required when DALIL_QUERY_NORMALIZATION_BACKEND=openai.'))
    if posture['renderer_backend'] == 'openai' and not posture['openai_api_key_present']:
        issues.append(_issue(severity='error', code='missing_openai_api_key_for_renderer', message='OPENAI_API_KEY is required when DALIL_RENDERER_BACKEND=openai.'))

    if posture['anchor_store_backend'] == 'redis' and importlib.util.find_spec('redis') is None:
        severity = 'error' if release_mode == 'production' else 'warning'
        issues.append(_issue(severity=severity, code='redis_backend_package_missing', message='DALIL_ANCHOR_STORE_BACKEND=redis but the redis package is not installed.'))

    if release_mode in {'staging', 'production'} and posture['anchor_store_backend'] == 'memory':
        severity = 'error' if release_mode == 'production' else 'warning'
        issues.append(_issue(severity=severity, code='memory_anchor_store_not_production_safe', message='Memory anchor store is not suitable for bounded continuity beyond local development.'))

    if release_mode == 'production':
        if not posture['observability_enabled']:
            issues.append(_issue(severity='error', code='observability_disabled_in_production', message='DALIL_OBSERVABILITY_ENABLED must be true in production mode.'))
        if posture['response_debug_default']:
            issues.append(_issue(severity='error', code='debug_default_enabled_in_production', message='DALIL_RESPONSE_DEBUG_DEFAULT must be false in production mode.'))
        if posture['response_include_legacy_result']:
            issues.append(_issue(severity='error', code='legacy_result_enabled_in_production', message='DALIL_RESPONSE_INCLUDE_LEGACY_RESULT must be false in production mode.'))
        if posture['query_normalization_backend'] != 'openai':
            issues.append(_issue(severity='error', code='hosted_query_normalization_required_for_production', message='Production mode requires DALIL_QUERY_NORMALIZATION_BACKEND=openai for messy-query robustness.'))
        if posture['public_topical_tafsir_enabled']:
            issues.append(_issue(severity='error', code='topical_tafsir_not_in_current_mvp', message='DALIL_PUBLIC_TOPICAL_TAFSIR_ENABLED must remain false for the current bounded MVP production lock.'))

        if not posture['response_surface_contract_version']:
            issues.append(_issue(severity='error', code='missing_response_surface_contract_version', message='DALIL_RESPONSE_SURFACE_CONTRACT_VERSION must be set in production mode.'))

    return issues


def refresh_startup_validation_info(config: Settings = settings) -> dict[str, Any]:
    global STARTUP_VALIDATION_INFO
    posture = build_release_posture(config)
    issues = collect_startup_validation_issues(config)
    strict = bool(getattr(config, 'startup_validation_strict', False)) or posture['release_mode'] == 'production'
    STARTUP_VALIDATION_INFO = {
        'checked': True,
        'release_mode': posture['release_mode'],
        'strict': strict,
        'error_count': sum(1 for item in issues if item['severity'] == 'error'),
        'warning_count': sum(1 for item in issues if item['severity'] == 'warning'),
        'issues': issues,
        'release_posture': posture,
    }
    return copy.deepcopy(STARTUP_VALIDATION_INFO)


def get_startup_validation_info() -> dict[str, Any]:
    if not STARTUP_VALIDATION_INFO.get('checked'):
        return refresh_startup_validation_info()
    return copy.deepcopy(STARTUP_VALIDATION_INFO)


def validate_startup_configuration(config: Settings = settings) -> dict[str, Any]:
    info = refresh_startup_validation_info(config)
    if info['strict'] and info['error_count'] > 0:
        joined = '; '.join(issue['message'] for issue in info['issues'] if issue['severity'] == 'error')
        raise RuntimeError(joined)
    return info
