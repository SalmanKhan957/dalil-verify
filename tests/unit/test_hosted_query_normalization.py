from __future__ import annotations

from domains.ask.classifier import classify_ask_query
from domains.query_intelligence.hosted_normalization import normalize_query_for_routing
from domains.query_intelligence.models import QueryNormalizationResult
from infrastructure.config.settings import settings


def test_hosted_query_normalization_falls_back_when_model_flags_meaning_change(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'query_normalization_backend', 'openai')
    monkeypatch.setattr(settings, 'openai_api_key', 'test-key')
    monkeypatch.setattr(
        'domains.query_intelligence.hosted_normalization.normalize_with_openai',
        lambda **kwargs: {
            'normalized_query': 'Explain Surah Al-Baqarah',
            'confidence': 0.94,
            'normalization_type': 'mixed',
            'did_change_meaning': True,
            'notes': 'unsafe broadening',
            'model': 'gpt-5.4-mini',
        },
    )

    result = normalize_query_for_routing('wht does ibnkathir say about surah al baqra')

    assert result.backend == 'deterministic'
    assert result.normalized_query == 'what does ibn kathir say about surah al-baqarah'
    assert result.notes == 'hosted_flagged_meaning_change'


def test_classifier_uses_hosted_query_normalization_result() -> None:
    normalization = QueryNormalizationResult(
        raw_query='wht does ibnkathir say about surah al baqra',
        normalized_query='What does Ibn Kathir say about Surah Al-Baqarah?',
        backend='openai',
        changed=True,
        confidence=0.91,
        normalization_type='mixed',
        did_change_meaning=False,
        safe_for_routing=True,
        notes='restored spacing and transliteration',
        model='gpt-5.4-mini',
        used_hosted_model=True,
    )

    route = classify_ask_query('wht does ibnkathir say about surah al baqra', normalization_result=normalization)

    assert route['route_type'] == 'explicit_quran_reference'
    assert route['reference_text'] == 'surah al-baqarah'
    assert route['secondary_intents'] == ['tafsir_request']
    assert route['query_normalization']['backend'] == 'openai'
    assert route['query_normalization']['normalized_query'] == 'What does Ibn Kathir say about Surah Al-Baqarah?'


def test_hosted_query_normalization_rejects_digit_drift(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'query_normalization_backend', 'openai')
    monkeypatch.setattr(settings, 'openai_api_key', 'test-key')
    monkeypatch.setattr(
        'domains.query_intelligence.hosted_normalization.normalize_with_openai',
        lambda **kwargs: {
            'normalized_query': 'Bukhari 27',
            'confidence': 0.88,
            'normalization_type': 'spacing',
            'did_change_meaning': False,
            'notes': 'added spacing',
            'model': 'gpt-5.4-mini',
        },
    )

    result = normalize_query_for_routing('Bukhari20')

    assert result.backend == 'deterministic'
    assert result.notes == 'hosted_digit_signature_mismatch'



def test_hosted_query_normalization_surfaces_fallback_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'query_normalization_backend', 'openai')
    monkeypatch.setattr(settings, 'openai_api_key', 'test-key')
    monkeypatch.setattr(
        'domains.query_intelligence.hosted_normalization.normalize_with_openai',
        lambda **kwargs: {
            'ok': False,
            'error_class': 'http_error',
            'fallback_reason': 'hosted_http_error',
            'model': 'gpt-5.4-mini',
        },
    )

    result = normalize_query_for_routing('wht does ibnkathir say about surah al baqra')

    assert result.backend == 'deterministic'
    assert result.attempted_hosted_model is True
    assert result.used_hosted_model is False
    assert result.hosted_model == 'gpt-5.4-mini'
    assert result.hosted_fallback_reason == 'hosted_http_error'
    assert result.hosted_error_class == 'http_error'
    assert result.to_payload()['attempted_hosted_model'] is True
    assert result.to_payload()['hosted_fallback_reason'] == 'hosted_http_error'
    assert result.to_payload()['hosted_error_class'] == 'http_error'
