from __future__ import annotations

from domains.ask.response_surface import (
    CANONICAL_TOP_LEVEL_ANSWER_FIELDS,
    LEGACY_RESULT_ALLOWED_FIELDS,
    LEGACY_RESULT_ONLY_FIELDS,
    build_ask_response_payload,
    describe_response_surfaces,
)
from infrastructure.config.settings import settings


def test_build_ask_response_payload_constrains_legacy_result_envelope() -> None:
    result = {
        'ok': True,
        'query': '112:1-2',
        'route_type': 'explicit_quran_reference',
        'action_type': 'explain',
        'answer_mode': 'quran_text',
        'answer_text': 'Quran 112:1-2 says: Say: He is Allah, the One.',
        'citations': [],
        'quran_support': {'citation_string': 'Quran 112:1-2'},
        'tafsir_support': [],
        'resolution': {'canonical_source_id': 'quran:112:1-2'},
        'partial_success': False,
        'warnings': [],
        'quran_source_selection': {'selected_quran_text_source_id': 'quran:tanzil-simple'},
        'source_policy': {'quran': {'domain': 'quran'}},
        'orchestration': {'request': {'query': '112:1-2'}},
        'conversation': {'followup_ready': True, 'anchors': []},
        'debug': None,
        'error': None,
        'quran_span': {'citation_string': 'Quran 112:1-2'},
        'verifier_result': {'match_status': 'matched'},
        'quote_payload': 'قُلْ هُوَ اللَّهُ أَحَدٌ',
        'hadith_entry': None,
        'private_internal': {'should_not': 'escape'},
    }
    payload = build_ask_response_payload(query='112:1-2', route={'route_type': 'explicit_quran_reference', 'action_type': 'explain'}, result=result)
    from infrastructure.config.settings import settings


    if settings.response_include_legacy_result:
        assert payload['result'] is not None
        assert 'private_internal' not in payload['result']
        assert set(payload['result']).issubset(set(LEGACY_RESULT_ALLOWED_FIELDS))

        for field in LEGACY_RESULT_ONLY_FIELDS:
            assert field not in payload
            assert field in payload['result']
    else:
        assert payload['result'] is None

    # Canonical fields must always exist (independent of legacy envelope)
    for field in CANONICAL_TOP_LEVEL_ANSWER_FIELDS:
        assert field in payload


def test_response_surface_description_calls_out_canonical_vs_compatibility_layers() -> None:
    description = describe_response_surfaces()
    assert 'answer_text' in description['canonical_top_level_fields']
    assert 'quran_span' in description['legacy_result_only_fields']
    assert description['notes']['result'].startswith('Legacy compatibility envelope')
    assert description['notes']['surface_contract_version'] == settings.response_surface_contract_version
