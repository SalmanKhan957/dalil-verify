from types import SimpleNamespace

from domains.ask.planner_types import ResponseMode, TerminalState
from domains.answer_engine.composition_builder import build_composition_packet


def test_composition_policy_uses_bounded_source_grounded_public_scope_even_for_explicit_hadith() -> None:
    plan = SimpleNamespace(
        query='Explain Bukhari 7',
        route_type='explicit_hadith_reference',
        action_type='explain',
        response_mode=ResponseMode.HADITH_EXPLANATION,
        terminal_state=TerminalState.ANSWERED,
        route={'route_type': 'explicit_hadith_reference', 'action_type': 'explain'},
        clarify_prompt=None,
        clarify_topics=[],
        request_preferences={},
    )
    evidence = SimpleNamespace(selected_domains=['hadith'], response_mode='hadith_explanation', verifier_result=None)
    hadith_support = {
        'canonical_ref': 'hadith:sahih-al-bukhari-en:7',
        'collection_source_id': 'hadith:sahih-al-bukhari-en',
        'collection_slug': 'sahih-al-bukhari-en',
        'english_narrator': 'Narrated Ibn `Abbas:',
        'english_text': 'Some hadith text.',
        'reference_url': 'https://example.test',
    }
    source_policy = {'hadith': {'public_response_scope': 'bounded_public_explicit_and_explain'}}

    composition = build_composition_packet(
        plan=plan,
        evidence=evidence,
        answer_text='Explanation',
        quran_support=None,
        hadith_support=hadith_support,
        tafsir_support=[],
        source_policy=source_policy,
        conversation={'followup_ready': True, 'anchors': [{'canonical_ref': 'hadith:sahih-al-bukhari-en:7'}]},
    )

    assert composition['policy']['public_scope'] == 'bounded_source_grounded'
    assert composition['policy']['source_public_scope'] == 'bounded_public_explicit_and_explain'



def test_composition_followups_use_actual_tafsir_display_names() -> None:
    plan = SimpleNamespace(
        query='Explain Surah Al-Ikhlas',
        route_type='explicit_quran_reference',
        action_type='explain',
        response_mode=ResponseMode.QURAN_WITH_TAFSIR,
        terminal_state=TerminalState.ANSWERED,
        route={'route_type': 'explicit_quran_reference', 'action_type': 'explain'},
        clarify_prompt=None,
        clarify_topics=[],
        request_preferences={},
    )
    evidence = SimpleNamespace(selected_domains=['quran', 'tafsir'], response_mode='quran_with_tafsir', verifier_result=None)
    quran_support = {
        'citation_string': 'Quran 112:1-4',
        'surah_no': 112,
        'ayah_start': 1,
        'ayah_end': 4,
        'canonical_source_id': 'quran:112:1-4',
        'quran_source_id': 'quran:tanzil-simple',
        'translation_text': 'Say: He is Allah, One.',
    }
    tafsir_support = [
        {'source_id': 'tafsir:ibn-kathir-en', 'canonical_section_id': 'tafsir:ibn-kathir-en:1', 'display_name': 'Ibn Kathir', 'excerpt': 'IK excerpt'},
        {'source_id': 'tafsir:maarif-al-quran-en', 'canonical_section_id': 'tafsir:maarif-al-quran-en:1', 'display_name': "Ma'arif al-Qur'an", 'excerpt': 'MQ excerpt'},
    ]

    composition = build_composition_packet(
        plan=plan,
        evidence=evidence,
        answer_text='Explanation',
        quran_support=quran_support,
        hadith_support=None,
        tafsir_support=tafsir_support,
        source_policy={},
        conversation={'followup_ready': True, 'anchors': [{'canonical_ref': 'quran:112:1-4'}]},
    )

    source_specific = composition['followup']['source_specific_followups_supported']
    assert 'What does Ibn Kathir say?' in source_specific
    assert "What does Ma'arif al-Qur'an say?" in source_specific
    assert 'What does Tafheem say?' not in source_specific
