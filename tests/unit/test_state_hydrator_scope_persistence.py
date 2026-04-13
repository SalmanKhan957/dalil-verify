from domains.conversation.session_state import SessionState
from domains.conversation.state_hydrator import hydrate_session_state


def test_hydrator_preserves_thread_comparative_scope_while_updating_view_focus() -> None:
    previous = SessionState.from_payload(
        {
            'scope': {
                'domains': ['quran', 'tafsir'],
                'quran_ref': 'quran:2:255',
                'quran_span_ref': 'quran:2:255-256',
                'tafsir_source_ids': [
                    'tafsir:ibn-kathir-en',
                    'tafsir:maarif-al-quran-en',
                    'tafsir:tafheem-al-quran-en',
                ],
                'comparative_tafsir_source_ids': [
                    'tafsir:ibn-kathir-en',
                    'tafsir:maarif-al-quran-en',
                    'tafsir:tafheem-al-quran-en',
                ],
            },
            'anchors': {'refs': ['quran:2:255-256'], 'domains': ['quran', 'tafsir']},
            'followup_ready': True,
        }
    )
    payload = {
        'route_type': 'anchored_followup_tafsir',
        'answer_mode': 'quran_with_tafsir',
        'quran_support': {'canonical_source_id': 'quran:2:255'},
        'tafsir_support': [
            {'source_id': 'tafsir:tafheem-al-quran-en'},
        ],
        'conversation': {
            'followup_ready': True,
            'anchors': [
                {'canonical_ref': 'quran:2:255', 'source_domain': 'quran'},
                {'canonical_ref': 'tafsir:tafheem-al-quran-en:2:255', 'source_domain': 'tafsir'},
            ],
        },
    }

    hydrated = hydrate_session_state(payload, request_context={'_hydrated_session_state': previous.to_payload()})

    assert hydrated.scope.quran_ref == 'quran:2:255'
    assert hydrated.scope.quran_span_ref == 'quran:2:255-256'
    assert hydrated.scope.current_tafsir_source_id == 'tafsir:tafheem-al-quran-en'
    assert hydrated.scope.comparative_tafsir_source_ids == [
        'tafsir:tafheem-al-quran-en',
        'tafsir:ibn-kathir-en',
        'tafsir:maarif-al-quran-en',
    ]
