from domains.conversation.state_hydrator import hydrate_session_state, hydrate_session_state_from_request_context



def test_hydrate_session_state_round_trip_payload() -> None:
    payload = {
        'route_type': 'explicit_quran_reference',
        'answer_mode': 'quran_with_tafsir',
        'terminal_state': 'answered',
        'quran_support': {'canonical_source_id': 'quran:112:1-4'},
        'tafsir_support': [
            {'source_id': 'tafsir:tafheem-al-quran-en'},
            {'source_id': 'tafsir:ibn-kathir-en'},
        ],
        'conversation': {
            'followup_ready': True,
            'turn_id': 'turn123',
            'anchors': [
                {'canonical_ref': 'quran:112:1-4', 'source_domain': 'quran'},
                {'canonical_ref': 'tafsir:tafheem-al-quran-en:112:1', 'source_domain': 'tafsir'},
            ],
        },
        'citations': [{'canonical_ref': 'quran:112:1-4', 'source_id': 'quran:tanzil-simple'}],
    }
    state = hydrate_session_state(payload, request_context={'conversation_id': 'conv1'})
    hydrated = hydrate_session_state_from_request_context({'_hydrated_session_state': state.to_payload()})

    assert hydrated.conversation_id == 'conv1'
    assert hydrated.scope.quran_ref == 'quran:112:1-4'
    assert hydrated.scope.tafsir_source_ids == ['tafsir:tafheem-al-quran-en', 'tafsir:ibn-kathir-en']
    assert hydrated.supports_followups() is True
