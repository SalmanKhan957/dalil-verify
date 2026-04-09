from domains.ask.planner_types import AbstentionReason, EvidenceDomain, EvidenceRequirement, ResponseMode
from domains.ask.planner_lite import build_answer_plan


def test_build_answer_plan_adds_tafsir_for_tafsir_intent() -> None:
    plan = build_answer_plan("Tafsir of Surah Ikhlas")

    assert plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR
    assert plan.quran_plan is not None
    assert plan.quran_plan.domain == EvidenceDomain.QURAN
    assert plan.tafsir_plan is not None
    assert plan.tafsir_plan.domain == EvidenceDomain.TAFSIR
    assert plan.allow_composition is True
    assert EvidenceRequirement.TAFSIR_OVERLAP in plan.evidence_requirements


def test_build_answer_plan_keeps_plain_reference_quran_only() -> None:
    plan = build_answer_plan("What does 112:1-4 say?")

    assert plan.quran_plan is not None
    assert plan.tafsir_plan is None
    assert plan.allow_composition is False
    assert plan.response_mode == ResponseMode.QURAN_EXPLANATION


def test_build_answer_plan_abstains_for_topical_hadith_requests_when_public_lane_is_disabled() -> None:
    plan = build_answer_plan("Give me hadith about patience")

    assert plan.should_abstain is True
    assert plan.abstain_reason == AbstentionReason.POLICY_RESTRICTED
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.hadith_plan is None


def test_build_answer_plan_keeps_debug_shadow_plan_for_disabled_topical_hadith() -> None:
    plan = build_answer_plan('Give me hadith about patience', debug=True)

    assert plan.should_abstain is True
    assert plan.abstain_reason == AbstentionReason.POLICY_RESTRICTED
    assert plan.response_mode == ResponseMode.ABSTAIN
    assert plan.hadith_plan is not None
    assert plan.hadith_plan.params['shadow_only'] is True
