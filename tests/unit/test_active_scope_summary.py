from domains.conversation.session_state import ActiveScope, ConversationAnchorSet, SessionState


def test_active_scope_summary_contains_quran_span_and_tafsir_sources() -> None:
    state = SessionState(
        followup_ready=True,
        scope=ActiveScope(domains=['quran', 'tafsir'], quran_ref='quran:2:255-256', quran_span_ref='quran:2:255-256', tafsir_source_ids=['tafsir:tafheem-al-quran-en']),
        anchors=ConversationAnchorSet(refs=['quran:2:255-256'], domains=['quran', 'tafsir']),
    )
    summary = state.active_scope_summary()
    assert summary['quran_span_ref'] == 'quran:2:255-256'
    assert summary['tafsir_source_ids'] == ['tafsir:tafheem-al-quran-en']


def test_active_scope_summary_contains_explicit_hadith_ref() -> None:
    state = SessionState(scope=ActiveScope(domains=['hadith'], hadith_ref='hadith:sahih-al-bukhari-en:7', hadith_source_id='hadith:sahih-al-bukhari-en'))
    summary = state.active_scope_summary()
    assert summary['hadith_ref'] == 'hadith:sahih-al-bukhari-en:7'


def test_active_scope_summary_omits_unavailable_fields_cleanly() -> None:
    summary = SessionState().active_scope_summary()
    assert summary['quran_ref'] is None
    assert summary['hadith_ref'] is None
