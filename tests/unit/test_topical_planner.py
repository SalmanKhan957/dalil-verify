from domains.ask.planner import build_ask_plan
from domains.ask.planner_types import AbstentionReason, EvidenceDomain, EvidenceRequirement, ResponseMode


def test_planner_abstains_for_topical_hadith_plan_when_public_lane_is_disabled() -> None:
    plan = build_ask_plan('Any hadith about intention?')
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.should_abstain is True
    assert plan.abstain_reason == AbstentionReason.POLICY_RESTRICTED
    assert plan.selected_domains == []
    assert plan.hadith_plan is None
    assert plan.topical_query == 'intention'
    assert plan.source_policy.hadith is not None
    assert plan.source_policy.hadith.policy_reason == 'topical_hadith_temporarily_disabled'


def test_planner_abstains_for_topical_tafsir_plan_when_public_lane_is_disabled() -> None:
    plan = build_ask_plan('What does the Quran say about patience?')
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.should_abstain is True
    assert plan.abstain_reason == AbstentionReason.POLICY_RESTRICTED
    assert plan.selected_domains == []
    assert plan.tafsir_plan is None
    assert plan.topical_query == 'patience'
    assert plan.source_policy.tafsir is not None
    assert plan.source_policy.tafsir.policy_reason == 'topical_tafsir_temporarily_disabled'


def test_planner_keeps_public_mixed_source_topics_restricted() -> None:
    plan = build_ask_plan('What does Islam say about patience?')
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.should_abstain is True
    assert plan.tafsir_plan is None
    assert plan.hadith_plan is None
    assert plan.selected_domains == []
    assert plan.route_type == 'policy_restricted_request'
    assert 'public_mixed_source_topic_requires_future_planner' in plan.notes


def test_planner_keeps_explicit_quran_precedence_over_topical() -> None:
    plan = build_ask_plan('Explain 2:255')
    assert plan.response_mode in {ResponseMode.QURAN_EXPLANATION, ResponseMode.QURAN_WITH_TAFSIR}
    assert plan.quran_plan is not None
    assert plan.hadith_plan is None


def test_planner_blocks_topical_hadith_when_request_mode_is_explicit_lookup_only() -> None:
    plan = build_ask_plan(
        'Any hadith about intention?',
        source_controls={'hadith': {'mode': 'explicit_lookup_only', 'collection_ids': ['hadith:sahih-al-bukhari-en']}},
    )
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.hadith_plan is None
    assert plan.source_policy.hadith is not None
    assert plan.source_policy.hadith.request_mode == 'explicit_lookup_only'
    assert plan.source_policy.hadith.mode_enforced is True
    assert plan.source_policy.hadith.policy_reason == 'hadith_mode_blocks_topical_retrieval'


def test_planner_keeps_debug_shadow_plan_for_disabled_topical_hadith() -> None:
    plan = build_ask_plan('Any hadith about intention?', debug=True)
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.should_abstain is True
    assert plan.hadith_plan is not None
    assert plan.hadith_plan.params['retrieval_mode'] == 'topical_v2_shadow'
    assert plan.hadith_plan.params['shadow_only'] is True
    assert EvidenceRequirement.HADITH_LEXICAL_RETRIEVAL in plan.evidence_requirements
    assert EvidenceRequirement.HADITH_TOPICAL_V2_CANDIDATE_GENERATION in plan.evidence_requirements
