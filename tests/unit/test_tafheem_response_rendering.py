from domains.answer_engine.composer import compose_explain_answer
from domains.answer_engine.evidence_pack import EvidencePack, QuranEvidence, TafsirEvidence
from domains.ask.planner_types import EvidenceDomain, ResponseMode, AskPlan as AnswerPlan, DomainInvocation as SourceInvocationPlan
from domains.tafsir.types import TafsirOverlapHit


def _tafheem_hit() -> TafsirOverlapHit:
    return TafsirOverlapHit(
        section_id=2255,
        canonical_section_id='tafsir:tafheem-al-quran-en:2:255',
        work_id=2,
        source_id='tafsir:tafheem-al-quran-en',
        display_name='Tafheem al-Quran',
        citation_label='Tafheem al-Quran',
        surah_no=2,
        ayah_start=255,
        ayah_end=255,
        anchor_verse_key='2:255',
        quran_span_ref='2:255',
        coverage_mode='anchor_only',
        coverage_confidence=0.9,
        text_plain='Allah, the Ever-Living, the Self-Subsisting by Whom all subsist...',
        text_html='Allah, the Ever-Living, the Self-Subsisting by Whom all subsist...',
        overlap_ayah_count=1,
        exact_span_match=True,
        contains_query_span=True,
        query_contains_section=True,
        span_width=1,
        anchor_distance=0,
        raw_json={
            'raw_text': (
                'Allah, the Ever-Living[[This affirms exclusive divine sovereignty.]] '
                'Neither slumber seizes Him[[This refutes anthropomorphic weakness.]]'
            ),
            'inline_note_count': 2,
        },
    )


def test_compose_explain_answer_surfaces_tafheem_commentary_not_stripped_gloss() -> None:
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
            surah_name_en='Al-Baqarah',
            surah_name_ar='البقرة',
            arabic_text='...',
            translation_text='Allah: the Everlasting...',
            translation_source_id='quran:towards-understanding-en',
            raw={},
        ),
        tafsir=[TafsirEvidence(hit=_tafheem_hit())],
    )

    result = compose_explain_answer(plan, evidence)

    assert result['ok'] is True
    support = result['tafsir_support'][0]
    assert support['rendering_mode'] == 'tafheem_commentary_reconstructed'
    assert support['inline_note_count'] == 2
    assert 'exclusive divine sovereignty' in support['excerpt']
    assert 'anthropomorphic weakness' in support['text_html']
