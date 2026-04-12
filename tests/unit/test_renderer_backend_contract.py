from __future__ import annotations

from domains.answer_engine.conversational_renderer import render_bounded_conversational_answer


def test_deterministic_renderer_emits_followup_suggestions() -> None:
    payload = {
        'route_type': 'explicit_quran_reference',
        'composition': {
            'composition_mode': 'quran_with_tafsir',
            'resolved_scope': {'span_label': 'Quran 112:1-4'},
            'followup': {
                'suggested_followups': ['Compare that with Tafheem', 'Explain the second verse more simply'],
            },
            'source_bundles': [
                {'domain': 'quran', 'focused_extract': 'Say: He is Allah, One.'},
                {"domain": "tafsir", "display_name": "Tafsir Ibn Kathir", "focused_extract": "It explains Allah's oneness and uniqueness."},
            ],
        },
    }

    rendered = render_bounded_conversational_answer(payload=payload, fallback_answer_text='fallback')

    assert rendered['render_mode'] == 'quran_with_tafsir'
    assert rendered['renderer_backend'] == 'deterministic'
    assert rendered['followup_suggestions'] == ['Compare that with Tafheem', 'Explain the second verse more simply']


def test_openai_backend_falls_back_to_deterministic_when_client_returns_none(monkeypatch) -> None:
    from domains.answer_engine import conversational_renderer as cr

    monkeypatch.setattr(cr.settings, 'renderer_backend', 'openai')
    monkeypatch.setattr(cr.settings, 'openai_api_key', 'test-key')
    monkeypatch.setattr(cr, 'render_with_openai', lambda **kwargs: None)

    payload = {
        'route_type': 'explicit_quran_reference',
        'composition': {
            'composition_mode': 'quran_explanation',
            'resolved_scope': {'span_label': 'Quran 112:1-4'},
            'source_bundles': [
                {'domain': 'quran', 'focused_extract': 'Say: He is Allah, One.'},
            ],
            'followup': {'suggested_followups': []},
        },
    }

    rendered = render_bounded_conversational_answer(payload=payload, fallback_answer_text='fallback')

    assert rendered['renderer_backend'] == 'deterministic'
    assert rendered['answer_text']
