from domains.ask.planner import build_ask_plan
from domains.ask.planner_types import EvidenceDomain, EvidenceRequirement, ResponseMode


def test_planner_builds_topical_hadith_plan() -> None:
    plan = build_ask_plan('Any hadith about intention?')
    assert plan.response_mode == ResponseMode.TOPICAL_HADITH
    assert plan.selected_domains == [EvidenceDomain.HADITH]
    assert plan.hadith_plan is not None
    assert plan.hadith_plan.params['retrieval_mode'] == 'topical_v2_shadow'
    assert plan.topical_query == 'intention'
    assert EvidenceRequirement.HADITH_LEXICAL_RETRIEVAL in plan.evidence_requirements
    assert EvidenceRequirement.HADITH_TOPICAL_V2_CANDIDATE_GENERATION in plan.evidence_requirements


def test_planner_builds_topical_multi_source_plan() -> None:
    plan = build_ask_plan('What does Islam say about patience?')
    assert plan.response_mode == ResponseMode.TOPICAL_MULTI_SOURCE
    assert plan.tafsir_plan is not None
    assert plan.hadith_plan is not None
    assert plan.selected_domains == [EvidenceDomain.TAFSIR, EvidenceDomain.HADITH]
    assert plan.topical_query == 'patience'
    assert EvidenceRequirement.TAFSIR_LEXICAL_RETRIEVAL in plan.evidence_requirements
    assert EvidenceRequirement.HADITH_LEXICAL_RETRIEVAL in plan.evidence_requirements


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
