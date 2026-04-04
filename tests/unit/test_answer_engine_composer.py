from services.answer_engine.composer import compose_explain_answer
from services.answer_engine.evidence_pack import EvidencePack, QuranEvidence, TafsirEvidence
from services.answer_engine.plan_types import EvidenceDomain, ResponseMode, AnswerPlan, SourceInvocationPlan
from services.tafsir.types import TafsirOverlapHit



def _tafsir_hit() -> TafsirOverlapHit:
    return TafsirOverlapHit(
        section_id=84552,
        canonical_section_id="tafsir:ibn-kathir-en:84552",
        work_id=1,
        source_id="tafsir:ibn-kathir-en",
        display_name="Tafsir Ibn Kathir (English)",
        citation_label="Tafsir Ibn Kathir",
        surah_no=112,
        ayah_start=1,
        ayah_end=4,
        anchor_verse_key="112:1",
        quran_span_ref="112:1-4",
        coverage_mode="inferred_from_empty_followers",
        coverage_confidence=0.95,
        text_plain="Allah is One and Unique.",
        text_html="<p>Allah is One and Unique.</p>",
        overlap_ayah_count=4,
        exact_span_match=True,
        contains_query_span=True,
        query_contains_section=True,
        span_width=4,
        anchor_distance=0,
    )



def test_compose_explain_answer_with_quran_and_tafsir() -> None:
    plan = AnswerPlan(
        query="Tafsir of Surah Ikhlas",
        route_type="explicit_quran_reference",
        action_type="explain",
        response_mode=ResponseMode.QURAN_WITH_TAFSIR,
        quran_plan=SourceInvocationPlan(domain=EvidenceDomain.QURAN),
        tafsir_plan=SourceInvocationPlan(domain=EvidenceDomain.TAFSIR),
        eligible_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        selected_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        use_tafsir=True,
        tafsir_requested=True,
    )
    evidence = EvidencePack(
        query="Tafsir of Surah Ikhlas",
        route_type="explicit_quran_reference",
        action_type="explain",
        quran=QuranEvidence(
            citation_string="Quran 112:1-4",
            canonical_source_id="quran:112:1-4",
            surah_no=112,
            ayah_start=1,
            ayah_end=4,
            surah_name_en="Al-Ikhlas",
            surah_name_ar="الإخلاص",
            arabic_text="قُلْ هُوَ اللَّهُ أَحَدٌ",
            translation_text="Say: He is Allah, the One.",
            translation_source_id="quran:towards-understanding-en",
            raw={},
        ),
        tafsir=[TafsirEvidence(hit=_tafsir_hit())],
    )

    result = compose_explain_answer(plan, evidence)

    assert result["ok"] is True
    assert "In Tafsir Ibn Kathir" in result["answer_text"]
    assert result["quran_support"]["citation_string"] == "Quran 112:1-4"
    assert result["tafsir_support"][0]["display_text"] == "Tafsir Ibn Kathir on Quran 112:1-4"
    assert len(result["citations"]) == 2
