from domains.conversation.followup_resolver import resolve_followup
from domains.conversation.session_state import ActiveScope, ConversationAnchorSet, SessionState


def test_followup_rejects_target_source_not_in_current_scope() -> None:
    state = SessionState(
        followup_ready=True,
        scope=ActiveScope(domains=['quran', 'tafsir'], quran_ref='quran:112:1-4', quran_span_ref='quran:112:1-4', tafsir_source_ids=['tafsir:tafheem-al-quran-en']),
        anchors=ConversationAnchorSet(refs=['quran:112:1-4'], domains=['quran', 'tafsir']),
    )
    result = resolve_followup("What does Ma'arif say?", state)
    assert result.matched is False
    assert result.rejected is True
    assert result.reason == 'followup_target_source_not_in_scope'


def test_followup_rejects_missing_anchor_when_required() -> None:
    state = SessionState(followup_ready=False)
    result = resolve_followup('Show the exact wording again', state)
    assert result.matched is False


def test_followup_rejects_cross_domain_jump_from_hadith_to_tafsir() -> None:
    state = SessionState(
        followup_ready=True,
        scope=ActiveScope(domains=['hadith'], hadith_ref='hadith:sahih-al-bukhari-en:7', hadith_source_id='hadith:sahih-al-bukhari-en'),
        anchors=ConversationAnchorSet(refs=['hadith:sahih-al-bukhari-en:7'], domains=['hadith']),
    )
    result = resolve_followup('What does Tafheem say?', state)
    assert result.rejected is True
    assert result.reason == 'followup_target_source_not_in_scope'


def test_followup_rejects_out_of_scope_generic_topic_followup() -> None:
    state = SessionState(
        followup_ready=True,
        scope=ActiveScope(domains=['quran'], quran_ref='quran:2:255', quran_span_ref='quran:2:255'),
        anchors=ConversationAnchorSet(refs=['quran:2:255'], domains=['quran']),
    )
    result = resolve_followup('Summarize this hadith', state)
    assert result.rejected is True
    assert result.reason == 'followup_action_not_supported_for_scope'
