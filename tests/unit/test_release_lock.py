from __future__ import annotations

from types import SimpleNamespace

from infrastructure.config.release_lock import build_release_posture, collect_startup_validation_issues, refresh_startup_validation_info


def _config(**overrides):
    base = dict(
        release_mode='development',
        startup_validation_strict=False,
        observability_enabled=True,
        response_include_legacy_result=False,
        response_debug_default=False,
        response_surface_contract_version='ask.surface.v1',
        query_normalization_backend='deterministic',
        renderer_backend='deterministic',
        anchor_store_backend='memory',
        public_topical_tafsir_enabled=False,
        public_topical_hadith_enabled=False,
        openai_api_key='',
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_release_posture_surfaces_expected_flags() -> None:
    posture = build_release_posture(_config(release_mode='staging', anchor_store_backend='sqlite'))
    assert posture['release_mode'] == 'staging'
    assert posture['anchor_store_backend'] == 'sqlite'


def test_production_requires_hosted_query_normalization_and_clean_contract() -> None:
    issues = collect_startup_validation_issues(_config(release_mode='production', anchor_store_backend='sqlite'))
    codes = {item['code'] for item in issues}
    assert 'hosted_query_normalization_required_for_production' in codes
    assert 'missing_openai_api_key_for_query_normalization' not in codes


def test_production_openai_backend_requires_api_key() -> None:
    issues = collect_startup_validation_issues(
        _config(release_mode='production', query_normalization_backend='openai', anchor_store_backend='sqlite')
    )
    codes = {item['code'] for item in issues}
    assert 'missing_openai_api_key_for_query_normalization' in codes


def test_refresh_startup_validation_info_marks_production_strict() -> None:
    info = refresh_startup_validation_info(
        _config(release_mode='production', query_normalization_backend='openai', openai_api_key='x', anchor_store_backend='sqlite')
    )
    assert info['checked'] is True
    assert info['strict'] is True
