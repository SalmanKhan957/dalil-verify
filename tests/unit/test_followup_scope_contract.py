from domains.conversation.followup_resolver import resolve_followup
from domains.conversation.session_state import SessionState


def _state() -> SessionState:
    return SessionState.from_payload(
        {
            'scope': {
                'domains': ['quran', 'tafsir'],
                'quran_ref': 'quran:2:255',
                'quran_span_ref': 'quran:2:255-256',
                'tafsir_source_ids': ['tafsir:tafheem-al-quran-en'],
                'comparative_tafsir_source_ids': [
                    'tafsir:tafheem-al-quran-en',
                    'tafsir:ibn-kathir-en',
                    'tafsir:maarif-al-quran-en',
                ],
                'current_tafsir_source_id': 'tafsir:tafheem-al-quran-en',
            },
            'anchors': {'refs': ['quran:2:255'], 'domains': ['quran', 'tafsir']},
            'followup_ready': True,
        }
    )


def test_relative_quran_navigation_uses_current_focus_not_second_verse_hack() -> None:
    resolved = resolve_followup('What about the next verse?', _state())
    assert resolved.matched is True
    assert resolved.action_type == 'navigate_next_verse'
    assert resolved.target_ref == 'quran:2:256'


def test_comparative_tafsir_scope_survives_after_single_source_focus() -> None:
    resolved = resolve_followup('What does Ibn Kathir say?', _state())
    assert resolved.matched is True
    assert resolved.action_type == 'focus_source'
    assert resolved.target_source_id == 'tafsir:ibn-kathir-en'


def test_quran_thread_broad_source_shift_is_rejected_cleanly() -> None:
    resolved = resolve_followup('Give me ahadith about this', _state())
    assert resolved.matched is False
    assert resolved.rejected is True
    assert resolved.reason == 'followup_requires_new_query_boundary'


def test_resolve_followup_matches_explain_that_in_simple_words_alias() -> None:
    from domains.conversation.followup_resolver import resolve_followup
    from domains.conversation.session_state import ActiveScope, ConversationAnchorSet, SessionState

    state = SessionState(
        followup_ready=True,
        scope=ActiveScope(
            domains=['quran', 'tafsir'],
            quran_ref='quran:2:255',
            quran_span_ref='quran:2:255',
            comparative_tafsir_source_ids=['tafsir:tafheem-al-quran-en', 'tafsir:ibn-kathir-en'],
        ),
        anchors=ConversationAnchorSet(refs=['quran:2:255'], domains=['quran']),
    )

    resolved = resolve_followup('Explain that in simple words', state)

    assert resolved.matched is True
    assert resolved.action_type == 'simplify'
    assert resolved.reason == 'simplify_followup'
