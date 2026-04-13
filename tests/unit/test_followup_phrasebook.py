from domains.conversation.followup_capabilities import FollowupAction, FollowupCapability, FollowupCapabilitySet
from domains.conversation.followup_phrasebook import render_suggested_followups



def test_followup_phrasebook_renders_from_capabilities() -> None:
    payload = FollowupCapabilitySet(capabilities=[
        FollowupCapability(action_type=FollowupAction.FOCUS_SOURCE, target_domain='tafsir', target_source_id='tafsir:tafheem-al-quran-en', phrase_params={'source_label': 'Tafheem'}, priority=10),
        FollowupCapability(action_type=FollowupAction.SIMPLIFY, target_domain='quran', priority=20),
    ])
    suggestions = render_suggested_followups(payload)
    assert suggestions == ['What does Tafheem say?', 'Say it more simply']
