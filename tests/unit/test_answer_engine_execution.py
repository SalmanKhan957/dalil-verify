from domains.answer_engine.execution import execute_plan
from domains.ask.planner_types import EvidenceDomain, EvidenceRequirement, ResponseMode, AnswerPlan, SourceInvocationPlan
from domains.answer_engine.evidence_pack import QuranEvidence, TafsirEvidence
from domains.tafsir.types import TafsirOverlapHit



def _quran_evidence() -> QuranEvidence:
    return QuranEvidence(
        citation_string="Quran 112:1-4",
        canonical_source_id="quran:112:1-4",
        quran_source_id="quran:tanzil-simple",
        surah_no=112,
        ayah_start=1,
        ayah_end=4,
        surah_name_en="Al-Ikhlas",
        surah_name_ar="الإخلاص",
        arabic_text="قُلْ هُوَ اللَّهُ أَحَدٌ",
        translation_text="Say: He is Allah, the One.",
        translation_source_id="quran:towards-understanding-en",
        raw={"citation_string": "Quran 112:1-4"},
    )



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



def test_execute_plan_assembles_quran_and_tafsir(monkeypatch) -> None:
    import domains.answer_engine.execution as execution_module
    from domains.answer_engine.domain_invocation import QuranInvocationEvidence, TafsirInvocationEvidence

    plan = AnswerPlan(
        query="Tafsir of Surah Ikhlas",
        route_type="explicit_quran_reference",
        action_type="explain",
        response_mode=ResponseMode.QURAN_WITH_TAFSIR,
        eligible_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        selected_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        requires_quran_reference_resolution=True,
        resolved_quran_ref={"resolved": True, "canonical_source_id": "quran:112:1-4"},
        use_tafsir=True,
        evidence_requirements=[EvidenceRequirement.QURAN_SPAN, EvidenceRequirement.TAFSIR_OVERLAP],
        quran_plan=SourceInvocationPlan(domain=EvidenceDomain.QURAN),
        tafsir_plan=SourceInvocationPlan(domain=EvidenceDomain.TAFSIR, params={"source_id": "tafsir:ibn-kathir-en", "limit": 3}),
        tafsir_requested=True,
    )

    monkeypatch.setattr(
        execution_module,
        "invoke_quran_domain",
        lambda *args, **kwargs: QuranInvocationEvidence(
            quran=_quran_evidence(),
            resolution={"canonical_source_id": "quran:112:1-4"},
        ),
    )
    monkeypatch.setattr(
        execution_module,
        "invoke_tafsir_domain",
        lambda *args, **kwargs: TafsirInvocationEvidence(
            tafsir=[TafsirEvidence(hit=_tafsir_hit())],
        ),
    )

    evidence = execute_plan(plan)

    assert evidence.quran is not None
    assert evidence.quran.citation_string == "Quran 112:1-4"
    assert len(evidence.tafsir) == 1
    assert evidence.selected_domains == ["quran", "tafsir"]
