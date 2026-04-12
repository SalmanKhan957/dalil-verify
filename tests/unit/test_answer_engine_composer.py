from domains.answer_engine.composer import compose_explain_answer
from domains.answer_engine.evidence_pack import EvidencePack, QuranEvidence, TafsirEvidence
from domains.ask.planner_types import EvidenceDomain, ResponseMode, AskPlan as AnswerPlan, DomainInvocation as SourceInvocationPlan
from domains.tafsir.types import TafsirOverlapHit



def _tafsir_hit() -> TafsirOverlapHit:
    return TafsirOverlapHit(
        section_id=84552,
        canonical_section_id='tafsir:ibn-kathir-en:84552',
        work_id=1,
        source_id='tafsir:ibn-kathir-en',
        display_name='Tafsir Ibn Kathir (English)',
        citation_label='Tafsir Ibn Kathir',
        surah_no=112,
        ayah_start=1,
        ayah_end=4,
        anchor_verse_key='112:1',
        quran_span_ref='112:1-4',
        coverage_mode='inferred_from_empty_followers',
        coverage_confidence=0.95,
        text_plain='Which was revealed in Makkah The Reason for the Revelation of this Surah and its Virtues Imam Ahmad recorded from Ubayy bin Ka`b that the idolators said to the Prophet , "O Muhammad! Tell us the lineage of your Lord." So Allah revealed ...',
        text_html='<p>Allah is One and Unique.</p>',
        overlap_ayah_count=4,
        exact_span_match=True,
        contains_query_span=True,
        query_contains_section=True,
        span_width=4,
        anchor_distance=0,
    )



def test_compose_explain_answer_with_quran_and_tafsir_prefers_clean_translation_led_answer() -> None:
    plan = AnswerPlan(
        query='Tafsir of Surah Ikhlas',
        route_type='explicit_quran_reference',
        action_type='explain',
        response_mode=ResponseMode.QURAN_WITH_TAFSIR,
        quran_plan=SourceInvocationPlan(domain=EvidenceDomain.QURAN),
        tafsir_plan=SourceInvocationPlan(domain=EvidenceDomain.TAFSIR),
        eligible_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        selected_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        use_tafsir=True,
        tafsir_requested=True,
    )
    evidence = EvidencePack(
        query='Tafsir of Surah Ikhlas',
        route_type='explicit_quran_reference',
        action_type='explain',
        quran=QuranEvidence(
            citation_string='Quran 112:1-4',
            canonical_source_id='quran:112:1-4',
            quran_source_id='quran:tanzil-simple',
            surah_no=112,
            ayah_start=1,
            ayah_end=4,
            surah_name_en='Al-Ikhlas',
            surah_name_ar='الإخلاص',
            arabic_text='قُلْ هُوَ اللَّهُ أَحَدٌ',
            translation_text='Say: He is Allah, the One.',
            translation_source_id='quran:towards-understanding-en',
            raw={},
        ),
        tafsir=[TafsirEvidence(hit=_tafsir_hit())],
    )

    result = compose_explain_answer(plan, evidence)

    assert result['ok'] is True
    assert result['answer_text'] == (
        'Quran 112:1-4 says: Say: He is Allah, the One. '
        'Retrieved commentary from Tafsir Ibn Kathir is attached below.'
    )
    assert result['quran_support']['citation_string'] == 'Quran 112:1-4'
    assert result['tafsir_support'][0]['display_text'] == 'Tafsir Ibn Kathir on Quran 112:1-4'
    assert len(result['citations']) == 2



def _tafheem_hit() -> TafsirOverlapHit:
    return TafsirOverlapHit(
        section_id=99001,
        canonical_section_id='tafsir:tafheem-al-quran-en:99001',
        work_id=2,
        source_id='tafsir:tafheem-al-quran-en',
        display_name='Tafheem al-Quran',
        citation_label='Tafheem al-Quran',
        surah_no=112,
        ayah_start=1,
        ayah_end=4,
        anchor_verse_key='112:1',
        quran_span_ref='112:1-4',
        coverage_mode='anchor_only',
        coverage_confidence=0.91,
        text_plain='This surah establishes absolute divine oneness.',
        text_html='<p>This surah establishes absolute divine oneness.</p>',
        overlap_ayah_count=4,
        exact_span_match=True,
        contains_query_span=True,
        query_contains_section=True,
        span_width=4,
        anchor_distance=0,
    )


def test_compose_explain_answer_supports_source_separated_comparative_tafsir() -> None:
    plan = AnswerPlan(
        query='Tafsir of Surah Ikhlas',
        route_type='explicit_quran_reference',
        action_type='explain',
        response_mode=ResponseMode.QURAN_WITH_TAFSIR,
        quran_plan=SourceInvocationPlan(domain=EvidenceDomain.QURAN),
        tafsir_plan=SourceInvocationPlan(domain=EvidenceDomain.TAFSIR, params={'source_ids': ['tafsir:ibn-kathir-en', 'tafsir:tafheem-al-quran-en']}),
        eligible_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        selected_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        use_tafsir=True,
        tafsir_requested=True,
    )
    evidence = EvidencePack(
        query='Tafsir of Surah Ikhlas',
        route_type='explicit_quran_reference',
        action_type='explain',
        quran=QuranEvidence(
            citation_string='Quran 112:1-4',
            canonical_source_id='quran:112:1-4',
            quran_source_id='quran:tanzil-simple',
            surah_no=112,
            ayah_start=1,
            ayah_end=4,
            surah_name_en='Al-Ikhlas',
            surah_name_ar='الإخلاص',
            arabic_text='قُلْ هُوَ اللَّهُ أَحَدٌ',
            translation_text='Say: He is Allah, the One.',
            translation_source_id='quran:towards-understanding-en',
            raw={},
        ),
        tafsir=[TafsirEvidence(hit=_tafsir_hit()), TafsirEvidence(hit=_tafheem_hit())],
    )

    result = compose_explain_answer(plan, evidence)

    assert result['answer_text'] == (
        'Quran 112:1-4 says: Say: He is Allah, the One. '
        'Retrieved commentary from Tafsir Ibn Kathir and Tafheem al-Quran is attached below.'
    )
    assert [item['source_id'] for item in result['tafsir_support']] == [
        'tafsir:ibn-kathir-en',
        'tafsir:tafheem-al-quran-en',
    ]


def test_compose_explain_answer_prefers_actual_translation_source_in_public_surface() -> None:
    plan = AnswerPlan(
        query='2:255',
        route_type='explicit_quran_reference',
        action_type='explain',
        response_mode=ResponseMode.QURAN_WITH_TAFSIR,
        quran_plan=SourceInvocationPlan(domain=EvidenceDomain.QURAN),
        tafsir_plan=SourceInvocationPlan(domain=EvidenceDomain.TAFSIR),
        eligible_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        selected_domains=[EvidenceDomain.QURAN, EvidenceDomain.TAFSIR],
        use_tafsir=True,
        tafsir_requested=True,
        quran_work_source_id='quran:tanzil-simple',
        translation_work_source_id='quran:towards-understanding-en',
    )
    evidence = EvidencePack(
        query='2:255',
        route_type='explicit_quran_reference',
        action_type='explain',
        quran=QuranEvidence(
            citation_string='Quran 2:255',
            canonical_source_id='quran:2:255',
            quran_source_id='quran:tanzil-simple',
            surah_no=2,
            ayah_start=255,
            ayah_end=255,
            surah_name_en='al-baqarah',
            surah_name_ar='البقرة',
            arabic_text='...',
            translation_text='Allah: the Everlasting...',
            translation_source_id='quran:towards-understanding-en',
            raw={},
        ),
        tafsir=[TafsirEvidence(hit=_tafsir_hit())],
    )

    result = compose_explain_answer(plan, evidence)

    assert result['quran_support']['translation_source_id'] == 'quran:towards-understanding-en'
    assert result['quran_source_selection']['selected_quran_translation_source_id'] == 'quran:towards-understanding-en'
