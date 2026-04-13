from __future__ import annotations

from domains.answer_engine.conversational_renderer import render_bounded_conversational_answer


def test_render_quran_explanation_uses_explanatory_marker_without_tafsir() -> None:
    payload = {
        "route_type": "explicit_quran_reference",
        "composition": {
            "composition_mode": "quran_explanation",
            "resolved_scope": {"span_label": "Quran 1:1-7"},
            "source_bundles": [
                {
                    "domain": "quran",
                    "focused_extract": "In the name of Allah, the Merciful, the Compassionate. Praise be to Allah, the Lord of the entire universe.",
                }
            ],
            "followup": {"suggested_followups": []},
        },
    }

    rendered = render_bounded_conversational_answer(
        payload=payload,
        fallback_answer_text="Quran 1:1-7 says: In the name of Allah.",
    )

    assert rendered["render_mode"] == "quran_explanation"
    assert rendered["answer_text"].startswith("In summary,")
    assert "teaches:" in rendered["answer_text"]
