from domains.conversation.followup_capabilities import FollowupAction, derive_followup_capabilities
from domains.conversation.session_state import ActiveScope, ConversationAnchorSet, SessionState


def test_quran_tafsir_capabilities_are_derived() -> None:
    state = SessionState(
        followup_ready=True,
        anchors=ConversationAnchorSet(refs=["quran:2:255"], domains=["quran", "tafsir"]),
        scope=ActiveScope(
            domains=["quran", "tafsir"],
            quran_ref="quran:2:255",
            quran_span_ref="quran:2:255",
            tafsir_source_ids=["tafsir:tafheem-al-quran-en", "tafsir:ibn-kathir-en"],
        ),
    )

    result = derive_followup_capabilities(state).sorted()
    action_types = [item.action_type for item in result]

    assert FollowupAction.FOCUS_SOURCE in action_types
    assert FollowupAction.SIMPLIFY in action_types
    assert FollowupAction.REPEAT_EXACT_TEXT in action_types


def test_hadith_capabilities_are_derived() -> None:
    state = SessionState(
        followup_ready=True,
        anchors=ConversationAnchorSet(refs=["hadith:sahih-al-bukhari-en:7"], domains=["hadith"]),
        scope=ActiveScope(
            domains=["hadith"],
            hadith_ref="hadith:sahih-al-bukhari-en:7",
            hadith_source_id="hadith:sahih-al-bukhari-en",
        ),
    )

    result = derive_followup_capabilities(state).sorted()
    action_types = [item.action_type for item in result]

    assert FollowupAction.SUMMARIZE_HADITH in action_types
    assert FollowupAction.EXTRACT_HADITH_LESSON in action_types
