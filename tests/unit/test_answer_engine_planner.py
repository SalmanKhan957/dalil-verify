from services.answer_engine.plan_types import AbstentionReason, EvidenceDomain, EvidenceRequirement, ResponseMode
from services.answer_engine.planner import build_ask_plan



def test_build_ask_plan_for_explicit_reference_with_tafsir() -> None:
    plan = build_ask_plan("Tafsir of Surah Ikhlas")

    assert plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR
    assert plan.requires_quran_reference_resolution is True
    assert plan.resolved_quran_ref is not None
    assert plan.resolved_quran_ref["canonical_source_id"] == "quran:112:1-4"
    assert plan.selected_domains == [EvidenceDomain.QURAN, EvidenceDomain.TAFSIR]
    assert EvidenceRequirement.QURAN_SPAN in plan.evidence_requirements
    assert EvidenceRequirement.TAFSIR_OVERLAP in plan.evidence_requirements



def test_build_ask_plan_for_arabic_quote_verification_only() -> None:
    plan = build_ask_plan("Is this from the Quran: بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ")

    assert plan.requires_quran_verification is True
    assert plan.response_mode == ResponseMode.VERIFICATION_ONLY
    assert plan.selected_domains == [EvidenceDomain.QURAN]



def test_build_ask_plan_abstains_when_reference_cannot_resolve() -> None:
    plan = build_ask_plan("Explain 115:1")

    assert plan.should_abstain is True
    assert plan.abstain_reason == AbstentionReason.NO_RESOLVED_REFERENCE
    assert plan.response_mode == ResponseMode.ABSTAIN
