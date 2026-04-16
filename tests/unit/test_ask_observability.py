from __future__ import annotations

from types import SimpleNamespace

from domains.ask.observability import attach_observability


def test_attach_observability_sets_request_id_and_flags(monkeypatch) -> None:
    payload = {
        'route': {
            'query_normalization': {
                'backend': 'openai',
                'normalized_query': 'what does ibn kathir say about surah al-baqarah',
                'used_hosted_model': True,
            }
        },
        'orchestration': {},
        'debug': None,
    }
    hydrated = {'anchor_refs': ['quran:2:1-286'], '_anchor_resolution_mode': 'hydrated_latest'}
    enriched = attach_observability(
        payload=payload,
        request_id='dalil-test-1',
        request_contract_version='ask.vnext',
        session_key='implicit:test',
        hydrated_request_context=hydrated,
        timings_ms={'total': 12.5},
        debug_requested=True,
    )
    diagnostics = enriched['orchestration']['diagnostics']
    assert diagnostics['request_id'] == 'dalil-test-1'
    assert diagnostics['feature_flags']['observability_enabled'] is True
    assert diagnostics['query_normalization']['backend'] == 'openai'
    assert enriched['debug']['request_id'] == 'dalil-test-1'
