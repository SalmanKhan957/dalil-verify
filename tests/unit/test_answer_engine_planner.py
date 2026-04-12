from domains.ask.planner_types import AbstentionReason, EvidenceDomain, EvidenceRequirement, ResponseMode
from domains.ask.planner import build_ask_plan
from domains.ask.route_types import AskRouteType



def test_build_ask_plan_for_explicit_reference_with_tafsir() -> None:
    plan = build_ask_plan('Tafsir of Surah Ikhlas')

    assert plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR
    assert plan.requires_quran_reference_resolution is True
    assert plan.resolved_quran_ref is not None
    assert plan.resolved_quran_ref['canonical_source_id'] == 'quran:112:1-4'
    assert plan.selected_domains == [EvidenceDomain.QURAN, EvidenceDomain.TAFSIR]
    assert EvidenceRequirement.QURAN_SPAN in plan.evidence_requirements
    assert EvidenceRequirement.TAFSIR_OVERLAP in plan.evidence_requirements
    assert plan.source_policy is not None
    assert plan.source_policy.tafsir.included is True
    assert plan.source_policy.tafsir.request_origin == 'query_intent'
    assert plan.source_policy.tafsir.policy_reason == 'selected_multiple'



def test_build_ask_plan_for_arabic_quote_verification_only() -> None:
    plan = build_ask_plan('Is this from the Quran: بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ')

    assert plan.requires_quran_verification is True
    assert plan.response_mode == ResponseMode.VERIFICATION_ONLY
    assert plan.selected_domains == [EvidenceDomain.QURAN]
    assert plan.source_policy is not None
    assert plan.source_policy.tafsir.included is False
    assert plan.source_policy.tafsir.policy_reason == 'route_not_eligible_for_tafsir'



def test_build_ask_plan_abstains_when_reference_cannot_resolve() -> None:
    plan = build_ask_plan('Explain 115:1')

    assert plan.should_abstain is True
    assert plan.abstain_reason == AbstentionReason.NO_RESOLVED_REFERENCE
    assert plan.response_mode == ResponseMode.ABSTAIN





def test_build_ask_plan_quran_explain_defaults_to_tafsir() -> None:
    plan = build_ask_plan('Explain 2:255')

    assert plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR
    assert plan.selected_domains == [EvidenceDomain.QURAN, EvidenceDomain.TAFSIR]
    assert plan.use_tafsir is True
    assert plan.tafsir_requested is True
    assert plan.source_policy is not None
    assert plan.tafsir_explicit is True
    assert plan.source_policy.tafsir.request_origin == 'explicit_flag'

def test_build_ask_plan_explicit_flag_false_suppresses_tafsir_intent() -> None:
    plan = build_ask_plan('Tafsir of Surah Ikhlas', include_tafsir=False)

    assert plan.response_mode == ResponseMode.QURAN_EXPLANATION
    assert plan.quran_plan is not None
    assert plan.tafsir_plan is None
    assert plan.selected_domains == [EvidenceDomain.QURAN]
    assert plan.use_tafsir is False
    assert plan.tafsir_requested is False
    assert plan.tafsir_explicit is False
    assert EvidenceRequirement.TAFSIR_OVERLAP not in plan.evidence_requirements
    assert 'tafsir_suppressed_by_request' in plan.notes
    assert plan.source_policy is not None
    assert plan.source_policy.tafsir.request_origin == 'explicit_suppression'
    assert plan.source_policy.tafsir.policy_reason == 'suppressed_by_request'



def test_build_ask_plan_for_arabic_quote_with_tafsir_intent() -> None:
    plan = build_ask_plan('فَبِأَيِّ آلَاءِ رَبِّكُمَا تُكَذِّبَانِ tafsir')

    assert plan.requires_quran_verification is True
    assert plan.response_mode == ResponseMode.VERIFICATION_THEN_EXPLAIN
    assert plan.selected_domains == [EvidenceDomain.QURAN, EvidenceDomain.TAFSIR]
    assert plan.use_tafsir is True
    assert plan.tafsir_requested is True
    assert plan.source_policy is not None
    assert plan.source_policy.tafsir.request_origin == 'query_intent'
    assert plan.source_policy.tafsir.policy_reason == 'selected_multiple'
    assert EvidenceRequirement.TAFSIR_OVERLAP in plan.evidence_requirements



def test_build_ask_plan_for_explicit_hadith_reference() -> None:
    plan = build_ask_plan('Bukhari 2')

    assert plan.response_mode == ResponseMode.HADITH_TEXT
    assert plan.hadith_plan is not None
    assert plan.resolved_hadith_citation is not None
    assert plan.resolved_hadith_citation.canonical_ref == 'hadith:sahih-al-bukhari-en:2'
    assert plan.selected_domains == [EvidenceDomain.HADITH]
    assert EvidenceRequirement.HADITH_CITATION_LOOKUP in plan.evidence_requirements
    assert plan.source_policy is not None
    assert plan.source_policy.hadith is not None
    assert plan.source_policy.hadith.policy_reason == 'explicit_citation_lookup_selected'


def test_build_ask_plan_for_anchored_quran_followup() -> None:
    plan = build_ask_plan(
        'What about the second verse?',
        request_context={'anchor_refs': ['quran:112:1-4']},
    )

    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_QURAN.value
    assert plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR
    assert plan.requires_quran_reference_resolution is True
    assert plan.resolved_quran_ref is not None
    assert plan.resolved_quran_ref['canonical_source_id'] == 'quran:112:2'
    assert plan.selected_domains == [EvidenceDomain.QURAN, EvidenceDomain.TAFSIR]


def test_build_ask_plan_for_anchored_tafsir_followup() -> None:
    plan = build_ask_plan(
        'What does Tafheem say?',
        request_context={
            'anchor_refs': [
                'quran:112:1-4',
                'tafsir:ibn-kathir-en:84552',
                'tafsir:maarif-al-quran-en:112:1',
                'tafsir:tafheem-al-quran-en:112:1',
            ]
        },
    )

    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value
    assert plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR
    assert plan.use_tafsir is True
    assert plan.tafsir_plan is not None
    assert plan.tafsir_plan.params['source_ids'] == ['tafsir:tafheem-al-quran-en']
    assert plan.resolved_quran_ref is not None
    assert plan.resolved_quran_ref['canonical_source_id'] == 'quran:112:1-4'


def test_build_ask_plan_for_anchored_hadith_followup() -> None:
    plan = build_ask_plan(
        'Summarize this hadith',
        request_context={'anchor_refs': ['hadith:sahih-al-bukhari-en:7']},
    )

    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value
    assert plan.response_mode == ResponseMode.HADITH_EXPLANATION
    assert plan.hadith_plan is not None
    assert plan.resolved_hadith_citation is not None
    assert plan.resolved_hadith_citation.canonical_ref == 'hadith:sahih-al-bukhari-en:7'
