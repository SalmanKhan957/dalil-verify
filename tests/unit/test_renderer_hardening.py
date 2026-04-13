from __future__ import annotations

from domains.answer_engine.conversational_renderer import render_bounded_conversational_answer
from domains.answer_engine.render_modes import render_quran_with_tafsir


def test_render_quran_with_tafsir_prefers_meaning_summary_and_source_points() -> None:
    composition = {
        'resolved_scope': {'span_label': 'Quran 112:1-4'},
        'answer_seed': {
            'lead_text': "Surah Al-Ikhlas teaches Allah's absolute oneness. Retrieved commentary is attached below.",
            'meaning_summary': "This passage affirms Allah's absolute oneness, His self-sufficiency, and that nothing is comparable to Him.",
        },
        'source_bundles': [
            {
                'domain': 'tafsir',
                'source_id': 'tafsir:ibn-kathir-en',
                'display_name': 'Tafsir Ibn Kathir',
                'summary_point': "This surah answers people who asked about Allah and makes clear that none is equal to Him.",
                'focused_extract': "The Virtue of the Surah ...",
            },
            {
                'domain': 'tafsir',
                'source_id': 'tafsir:maarif-al-quran-en',
                'display_name': "Ma'arif al-Qur'an",
                'summary_point': "It highlights Allah's oneness, self-sufficiency, and freedom from lineage.",
            },
        ],
        'comparative': {
            'distinct_emphases': [
                {'source_id': 'tafsir:ibn-kathir-en', 'points': ["This surah answers people who asked about Allah and makes clear that none is equal to Him."]},
                {'source_id': 'tafsir:maarif-al-quran-en', 'points': ["It highlights Allah's oneness, self-sufficiency, and freedom from lineage."]},
            ]
        },
        'rendering': {'verbosity': 'standard'},
        'followup': {'suggested_followups': ['Compare this with Ma\'arif']},
    }

    rendered = render_quran_with_tafsir(composition, fallback=None)

    assert rendered is not None
    assert rendered.startswith("This passage affirms Allah's absolute oneness")
    assert 'attached below' not in rendered.lower()
    assert 'Tafsir Ibn Kathir emphasizes that this surah answers people who asked about Allah' in rendered
    assert "Ma'arif al-Qur'an highlights that it highlights Allah's oneness" in rendered


def test_render_quran_explanation_uses_meaning_summary_when_available() -> None:
    payload = {
        'route_type': 'explicit_quran_reference',
        'composition': {
            'composition_mode': 'quran_explanation',
            'resolved_scope': {'span_label': 'Quran 1:1-7'},
            'answer_seed': {
                'meaning_summary': 'This surah begins with praise of Allah, affirms worship and reliance on Him alone, and asks Him for guidance on the straight path.',
            },
            'source_bundles': [
                {'domain': 'quran', 'focused_extract': 'All praise be to Allah, the Lord of the worlds...'}
            ],
            'followup': {'suggested_followups': ['Explain this more simply']},
        },
    }

    rendered = render_bounded_conversational_answer(payload=payload, fallback_answer_text='Quran 1:1-7 says: All praise be to Allah.')
    assert rendered['render_mode'] == 'quran_explanation'
    assert 'praise of Allah' in rendered['answer_text']
    assert 'straight path' in rendered['answer_text']
    assert rendered['followup_suggestions'] == ['Explain this more simply']


def test_render_quran_with_tafsir_does_not_use_mechanical_language() -> None:
    payload = {
        'route_type': 'explicit_quran_reference',
        'composition': {
            'composition_mode': 'quran_with_tafsir',
            'resolved_scope': {'span_label': 'Quran 2:255'},
            'answer_seed': {
                'lead_text': 'Quran 2:255 says: Allah is the Ever-Living. Retrieved commentary is attached below.',
                'meaning_summary': "This verse affirms Allah's absolute oneness, perfect life, complete sovereignty, and limitless knowledge over all creation.",
            },
            'source_bundles': [
                {'domain': 'quran', 'focused_extract': 'Allah: the Everlasting, the Sustainer of the whole Universe...'},
                {'domain': 'tafsir', 'source_id': 'tafsir:ibn-kathir-en', 'display_name': 'Tafsir Ibn Kathir', 'summary_point': 'Ayat al-Kursi has exceptional virtue and is described as the greatest Ayah in the Book of Allah.'},
                {'domain': 'tafsir', 'source_id': 'tafsir:maarif-al-quran-en', 'display_name': "Ma'arif al-Qur'an", 'summary_point': "The verse gathers Allah's oneness, living sovereignty, and complete knowledge in one passage."},
                {'domain': 'tafsir', 'source_id': 'tafsir:tafheem-al-quran-en', 'display_name': 'Tafheem al-Quran', 'summary_point': 'All godhead and sovereign rule belong to Allah alone, and nothing shares His authority.'},
            ],
            'comparative': {
                'distinct_emphases': [
                    {'source_id': 'tafsir:ibn-kathir-en', 'points': ['Ayat al-Kursi has exceptional virtue and is described as the greatest Ayah in the Book of Allah.']},
                    {'source_id': 'tafsir:maarif-al-quran-en', 'points': ["The verse gathers Allah's oneness, living sovereignty, and complete knowledge in one passage."]},
                    {'source_id': 'tafsir:tafheem-al-quran-en', 'points': ['All godhead and sovereign rule belong to Allah alone, and nothing shares His authority.']},
                ]
            },
            'followup': {'suggested_followups': ['What does Tafheem say here?']},
        },
    }
    rendered = render_bounded_conversational_answer(payload=payload, fallback_answer_text='Retrieved commentary is attached below.')
    assert 'attached below' not in rendered['answer_text'].lower()
    assert 'per-source emphasis' not in rendered['answer_text'].lower()
    assert rendered['answer_text'].startswith("This verse affirms Allah's absolute oneness")
    assert 'tafsir ibn kathir emphasizes that ayat al-kursi has exceptional virtue' in rendered['answer_text'].lower()
