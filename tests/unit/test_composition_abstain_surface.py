from domains.answer_engine.composition_builder import build_composition_packet
from domains.answer_engine.evidence_pack import EvidencePack
from domains.ask.planner_types import AskPlan, ResponseMode, TerminalState


def test_followup_rejection_uses_clean_abstain_message_not_stale_answer_text() -> None:
    plan = AskPlan(
        query='Give me ahadith about this',
        route_type='unsupported_for_now',
        action_type='unknown',
        response_mode=ResponseMode.ABSTAIN,
        terminal_state=TerminalState.ABSTAIN,
        followup_rejected=True,
        followup_reason='followup_requires_new_query_boundary',
        active_scope_summary={
            'domains': ['quran', 'tafsir'],
            'quran_ref': 'quran:2:255',
            'quran_span_ref': 'quran:2:255',
            'tafsir_source_ids': ['tafsir:tafheem-al-quran-en'],
            'comparative_tafsir_source_ids': ['tafsir:tafheem-al-quran-en', 'tafsir:ibn-kathir-en'],
            'current_tafsir_source_id': 'tafsir:tafheem-al-quran-en',
        },
    )
    evidence = EvidencePack(query=plan.query, route_type=plan.route_type, action_type=plan.action_type)

    composition = build_composition_packet(
        plan=plan,
        evidence=evidence,
        answer_text='Focusing just on Tafheem for Quran 2:255, it explains that ...',
        quran_support=None,
        hadith_support=None,
        tafsir_support=[],
        source_policy=None,
        conversation={'followup_ready': True, 'anchors': [{'canonical_ref': 'quran:2:255', 'source_domain': 'quran'}]},
    )

    abstention = composition.get('abstention') or {}
    assert abstention.get('reason_code') == 'followup_requires_new_query_boundary'
    assert 'changes the question boundary' in str(abstention.get('safe_user_message') or '').lower()
    assert 'Focusing just on Tafheem' not in str(abstention.get('safe_user_message') or '')


def test_hadith_scope_rejection_uses_hadith_specific_wording() -> None:
    plan = AskPlan(
        query='What about the next verse',
        route_type='policy_restricted_request',
        action_type='unknown',
        response_mode=ResponseMode.ABSTAIN,
        terminal_state=TerminalState.ABSTAIN,
        followup_rejected=True,
        followup_reason='followup_span_not_available',
        active_scope_summary={
            'domains': ['hadith'],
            'hadith_ref': 'hadith:sahih-al-bukhari-en:7',
            'hadith_source_id': 'hadith:sahih-al-bukhari-en',
        },
    )
    evidence = EvidencePack(query=plan.query, route_type=plan.route_type, action_type=plan.action_type)

    composition = build_composition_packet(
        plan=plan,
        evidence=evidence,
        answer_text=None,
        quran_support=None,
        hadith_support=None,
        tafsir_support=[],
        source_policy=None,
        conversation={'followup_ready': True, 'anchors': [{'canonical_ref': 'hadith:sahih-al-bukhari-en:7', 'source_domain': 'hadith'}]},
    )

    abstention = composition.get('abstention') or {}
    assert abstention.get('reason_code') == 'followup_span_not_available'
    assert 'hadith thread' in str(abstention.get('safe_user_message') or '').lower()
    assert 'current verse directly' not in str(abstention.get('safe_user_message') or '').lower()
