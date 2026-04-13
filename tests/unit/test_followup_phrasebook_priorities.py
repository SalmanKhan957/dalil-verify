from domains.conversation.followup_capabilities import FollowupAction, FollowupCapability, FollowupCapabilitySet
from domains.conversation.followup_phrasebook import render_suggested_followups


def test_phrasebook_orders_focus_source_above_generic_simplify_when_multiple_sources_present() -> None:
    payload = FollowupCapabilitySet(capabilities=[
        FollowupCapability(action_type=FollowupAction.SIMPLIFY, target_domain='quran', priority=40),
        FollowupCapability(action_type=FollowupAction.FOCUS_SOURCE, target_domain='tafsir', target_source_id='tafsir:tafheem-al-quran-en', phrase_params={'source_label': 'Tafheem'}, priority=10),
    ])
    suggestions = render_suggested_followups(payload)
    assert suggestions[0] == 'What does Tafheem say?'


def test_phrasebook_limits_suggestions_to_current_capabilities() -> None:
    payload = FollowupCapabilitySet(capabilities=[
        FollowupCapability(action_type=FollowupAction.SUMMARIZE_HADITH, target_domain='hadith', priority=10),
        FollowupCapability(action_type=FollowupAction.EXTRACT_HADITH_LESSON, target_domain='hadith', priority=20),
        FollowupCapability(action_type=FollowupAction.REPEAT_EXACT_TEXT, target_domain='hadith', priority=30),
        FollowupCapability(action_type=FollowupAction.SIMPLIFY, target_domain='quran', priority=40),
        FollowupCapability(action_type=FollowupAction.FOCUS_SECOND_VERSE, target_domain='quran', priority=50),
    ])
    suggestions = render_suggested_followups(payload, limit=4)
    assert len(suggestions) == 4
